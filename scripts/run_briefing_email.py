#!/usr/bin/env python3
"""
Phase 8: Creator Briefing Email

Emails the key stories behind tonight's published digest to the recipients in
web_settings (category creator_briefing). See src/publishing/creator_briefing.py.

Usage:
    python3 scripts/run_briefing_email.py                 # as the pipeline runs it
    python3 scripts/run_briefing_email.py --dry-run       # draft + render, no send
    python3 scripts/run_briefing_email.py --test --to someone@example.com
                                                          # preview edition, ignores the ledger
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from src.utils.phase_bootstrap import bootstrap_phase
bootstrap_phase()

from src.database.models import get_database_manager
from src.publishing import creator_briefing as cb
from src.utils.logging_config import setup_phase_logging

RENDER_DIR = project_root / "data" / "briefings"


def run_briefing_phase(dry_run: bool = False, test: bool = False, to: str = None,
                       digest_id: int = None, verbose: bool = False) -> dict:
    logger = setup_phase_logging("briefing", verbose=verbose, console_output=True).get_logger()
    start = datetime.now()
    result = {"phase": "briefing", "emails_sent": 0, "started_at": start.isoformat()}

    def finish(status: str, **extra):
        result.update(extra)
        result["status"] = status
        result["success"] = status != "error"
        result["duration_seconds"] = round((datetime.now() - start).total_seconds(), 2)
        return result

    try:
        settings = cb.BriefingSettings.load()
        recipients = cb.parse_recipients(to) if to else settings.recipients
        if not settings.enabled and not to:
            logger.info("Creator briefing disabled (creator_briefing.enabled = false); skipping")
            return finish("skipped", reason="disabled")
        if not recipients:
            raise cb.BriefingError("creator_briefing is enabled but creator_briefing.recipients is empty")
        if not dry_run and not os.environ.get("GMAIL_APP_PASSWORD"):
            raise cb.BriefingError("GMAIL_APP_PASSWORD is not set; cannot send the creator briefing")

        today = datetime.now(ZoneInfo("America/Los_Angeles")).date()
        with get_database_manager().get_session() as session:
            if digest_id is not None:
                from src.database.sqlalchemy_models import Digest
                digest = session.get(Digest, digest_id)
                if digest is None:
                    raise cb.BriefingError(f"digest {digest_id} not found")
            else:
                digest = cb.select_digest(session, today)
            if digest is None:
                logger.info(f"No published digest from the last {cb.MAX_DIGEST_AGE_DAYS} days; nothing to send")
                return finish("skipped", reason="no recent published digest")

            pending = recipients if (test or dry_run) else [
                r for r in recipients if not cb.already_sent(session, digest.id, r)
            ]
            if not pending:
                logger.info(f"Digest {digest.id} already briefed to every recipient; skipping")
                return finish("skipped", reason="already sent", digest_id=digest.id)

            material = cb.gather_material(session, digest)
            logger.info(f"Drafting briefing for digest {digest.id} ({digest.digest_date}): "
                        f"{len(material.arcs)} arcs, {len(material.episodes)} source episodes, model {settings.model}")

            from openai import OpenAI
            client = OpenAI(timeout=600)
            draft, surfaced = cb.draft_briefing(client, settings.model, material, settings.max_stories,
                                                reader=settings.recipient_name)
            if not surfaced:
                logger.warning("Web search surfaced no URLs; stories will carry search links only")
            links = cb.verify_sources(draft, surfaced)
            logger.info(f"Stories: {len(draft['stories'])}; source links kept {links.kept}, dropped {len(links.dropped)}")
            for url, why in links.dropped:
                logger.info(f"  dropped {url} ({why})")

            subject = f"[Preview] {draft['subject']}" if test else draft["subject"]
            html_body = cb.render_html(draft, material, preview=test, reader=settings.recipient_name)
            text_body = cb.render_text(draft, material, preview=test, reader=settings.recipient_name)

            RENDER_DIR.mkdir(parents=True, exist_ok=True)
            stem = f"{material.digest_date}-digest{digest.id}{'-preview' if test else ''}"
            (RENDER_DIR / f"{stem}.html").write_text(html_body, encoding="utf-8")
            (RENDER_DIR / f"{stem}.txt").write_text(text_body, encoding="utf-8")
            logger.info(f"Rendered to {RENDER_DIR / stem}.html")

            result.update(digest_id=digest.id, subject=subject, stories=len(draft["stories"]),
                          links_kept=links.kept, links_dropped=len(links.dropped),
                          rendered=str(RENDER_DIR / f"{stem}.html"))
            if dry_run:
                logger.info(f"DRY RUN: would send '{subject}' to {len(pending)} recipient(s)")
                return finish("success", dry_run=True)

            for recipient in pending:
                msg = cb.build_message(subject, html_body, text_body, recipient)
                cb.send_message(msg)
                cb.record_send(session, digest.id, recipient, subject, msg["Message-ID"],
                               len(draft["stories"]), is_test=test)
                result["emails_sent"] += 1
                logger.info(f"Sent briefing for digest {digest.id} to recipient {result['emails_sent']}/{len(pending)}")

        return finish("success")

    except Exception as e:
        logger.error(f"Creator briefing failed: {e}", exc_info=True)
        return finish("error", error=str(e))


def main():
    parser = argparse.ArgumentParser(description="Phase 8: Creator Briefing Email")
    parser.add_argument("--output-json", help="Output JSON file path (default: stdout)")
    parser.add_argument("--dry-run", action="store_true", help="Draft and render, do not send")
    parser.add_argument("--test", action="store_true",
                        help="Preview edition: [Preview] subject + banner, ignores and does not satisfy the send ledger")
    parser.add_argument("--to", help="Comma-separated recipients, overriding web_settings")
    parser.add_argument("--digest-id", type=int, help="Brief a specific digest instead of the newest")
    parser.add_argument("--limit", type=int, help="Accepted for orchestrator compatibility; unused")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    dry_run = args.dry_run or os.getenv("DRY_RUN", "").strip().lower() in {"1", "true", "yes", "on"}
    result = run_briefing_phase(dry_run=dry_run, test=args.test, to=args.to,
                                digest_id=args.digest_id, verbose=args.verbose)

    from src.utils.phase_output import write_phase_result
    write_phase_result(result, args.output_json)
    sys.exit(1 if result["status"] == "error" else 0)


if __name__ == "__main__":
    main()
