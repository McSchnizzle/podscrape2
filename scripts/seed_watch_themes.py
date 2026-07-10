#!/usr/bin/env python3
"""Seed watch_themes (kanban: watch-themes daily emphasis, Paul 2026-07-10).

Re-creates the 4 curated themes lost in the Supabase deletion, plus a 5th
new theme scoped 'both' (weekly digest AND nightly daily-emphasis). Every
description below is written as a clear natural-language matcher prompt --
it's fed verbatim to the claude -p theme scanner (see
scan_episode_for_theme / scan_episodes_for_daily_emphasis in
src/watch/theme_scan.py) as "THEME: <name>\\n\\n<description>", so the
wording IS the matching instruction, not just a label.

Idempotent: skips any theme whose name already exists (case-insensitive
exact match). Safe to re-run.

Usage:
  python3 scripts/seed_watch_themes.py            # seed against configured DB
  python3 scripts/seed_watch_themes.py --dry-run   # print what would be inserted
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parent.parent / '.env')

from src.database.models import get_database_manager  # noqa: E402
from src.database.sqlalchemy_models import WatchTheme  # noqa: E402

logger = logging.getLogger("seed_watch_themes")

# (name, description, scope, sort_order)
THEMES: list[tuple[str, str, str, int]] = [
    (
        "AI impact on public company stock prices",
        "Coverage of AI's effect on public-company valuations and stock "
        "prices: quarterly-report disclosures that mention AI as a revenue "
        "driver or a risk factor, earnings calls where executives credit or "
        "blame AI for results, AI-driven stock rallies or selloffs, "
        "AI-related M&A or capital raises that move share price, and "
        "analyst commentary connecting AI developments to specific "
        "companies' market value.",
        "weekly",
        10,
    ),
    (
        "AI impact on politics and elections",
        "Coverage of AI as a factor in politics and elections: AI framed "
        "as a campaign issue, harm or backlash directed at candidates seen "
        "as anti-AI or pro-AI, AI industry political spending or lobbying, "
        "polling on public sentiment toward AI regulation, and any "
        "discussion of AI companies or AI policy shaping electoral "
        "outcomes.",
        "weekly",
        20,
    ),
    (
        "User hatred of Microsoft Copilot",
        "User backlash, complaints, or frustration specifically about "
        "Microsoft Copilot: negative reviews, viral complaints, "
        "comparisons unfavorable to Copilot versus competing assistants, "
        "reports of Copilot being forced into products users didn't want, "
        "or commentary describing active dislike or distrust of Copilot.",
        "weekly",
        30,
    ),
    (
        "Claude Code as defacto agentic coding product",
        "Evidence that Claude Code is becoming the default/reference "
        "agentic coding tool: developer preference or adoption data, "
        "benchmark comparisons favoring Claude Code, competitors "
        "explicitly copying its interface or workflow, enterprises "
        "building around it, or commentary describing it as the standard "
        "other agentic coding products are measured against.",
        "weekly",
        40,
    ),
    (
        "AI standards, governance, and industry consortiums",
        "Coverage relevant to standards-body and consortium professionals "
        "working on AI: formation or membership news for standards "
        "organizations, alliances, or industry consortiums addressing AI "
        "(the kind of audience that also tracks groups like the FIDO "
        "Alliance, USB-IF, or PCI-SIG); publication of specifications, "
        "interoperability standards, or working-group output related to "
        "AI; cross-industry collaboration on shared AI infrastructure or "
        "protocols; and AI governance frameworks that involve industry "
        "participation (not government-only regulation). Skip general AI "
        "policy stories that don't involve a standards body, consortium, "
        "or formal cross-industry working group.",
        "both",
        50,
    ),
]


def seed(dry_run: bool = False) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    db = get_database_manager()
    inserted = 0
    skipped = 0

    with db.get_session() as session:
        existing_names = {
            name.strip().lower()
            for (name,) in session.query(WatchTheme.name).all()
        }

        for name, description, scope, sort_order in THEMES:
            if name.strip().lower() in existing_names:
                logger.info(f"Skip (already exists): {name}")
                skipped += 1
                continue

            if dry_run:
                logger.info(f"Would insert: {name} (scope={scope}, sort_order={sort_order})")
                inserted += 1
                continue

            session.add(WatchTheme(
                name=name,
                description=description,
                active=True,
                sort_order=sort_order,
                scope=scope,
            ))
            logger.info(f"Inserted: {name} (scope={scope}, sort_order={sort_order})")
            inserted += 1

        if not dry_run:
            session.commit()

    logger.info(f"Done: {inserted} inserted, {skipped} skipped")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be inserted without writing")
    args = parser.parse_args()
    sys.exit(seed(dry_run=args.dry_run))
