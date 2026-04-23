#!/usr/bin/env python3
"""
Debug-only pipeline monitor: runs the full orchestrator and emails you after each
phase completes (plus a final summary). Designed to survive SSH disconnect via
nohup. Not used by cron — cron uses run_pipeline_with_alerts.sh.

Usage:
    scripts/run_monitored_pipeline.sh              # standard args (--verbose --days-back 5 --limit 10)
    scripts/run_monitored_pipeline.sh --limit 3    # pass-through to orchestrator

Email config: reuses GMAIL_APP_PASSWORD + paulinpdx503@gmail.com from notify_failure.py.

Emits these emails per run:
  - [START]   when the pipeline begins
  - [PHASE N] at each phase completion (SUCCESS or FAILED)
  - [DONE]    final summary with phase timings + overall result

Each phase email includes:
  - phase name, duration, status
  - extracted metrics (episode counts, digests generated, etc. — phase-specific)
  - deduped notable log patterns (ERROR/WARNING/Traceback/FAIL, excluding HTTP-noise)
"""
from __future__ import annotations

import argparse
import os
import re
import smtplib
import socket
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

RECIPIENT = "paulinpdx503@gmail.com"
SENDER = "paulinpdx503@gmail.com"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
HOSTNAME = socket.gethostname()

# Phase boundary patterns (from pipeline.orchestrator logger)
PHASE_START = re.compile(r"pipeline\.orchestrator - INFO - PHASE (\d+): (.+?)(?:\s*$)")
PHASE_OK = re.compile(r"pipeline\.orchestrator - INFO - Phase completed successfully")
PIPELINE_DONE = re.compile(r"pipeline\.orchestrator - INFO - .*PIPELINE EXECUTION COMPLETE")
PIPELINE_FAIL = re.compile(r"pipeline\.orchestrator - (ERROR|WARNING) - .*PIPELINE FAILED")

# Notable patterns (with benign-noise filter)
NOTABLE_PATTERNS = re.compile(
    r"\b(ERROR|WARNING|Traceback|CRITICAL|FAILED|Failed)\b"
)
BENIGN_PATTERNS = re.compile(
    r"(urllib3\.connectionpool - DEBUG"
    r"|openai\._base_client - DEBUG"
    r"|httpcore\.(http11|connection) - DEBUG"
    r"|DEBUG - HTTP"
    r"|Retrying in "
    r"|retrying \d+/\d+)",
    re.IGNORECASE,
)

MAX_NOTABLE_LINES = 25


def send_email(subject: str, body: str) -> bool:
    """Send plaintext email via Gmail SMTP. Returns True on success."""
    password = os.environ.get("GMAIL_APP_PASSWORD")
    if not password:
        print(f"[monitor] GMAIL_APP_PASSWORD not set, skipping email: {subject}", file=sys.stderr)
        return False
    msg = MIMEMultipart()
    msg["From"] = SENDER
    msg["To"] = RECIPIENT
    msg["Subject"] = f"[{HOSTNAME}] {subject}"
    msg.attach(MIMEText(body, "plain"))
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as s:
            s.starttls()
            s.login(SENDER, password)
            s.send_message(msg)
        return True
    except Exception as e:
        print(f"[monitor] email send failed for {subject!r}: {e}", file=sys.stderr)
        return False


def fmt_dur(td) -> str:
    if td is None:
        return "unknown"
    if not hasattr(td, "total_seconds"):
        return str(td)
    total = int(td.total_seconds())
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:d}h {m:02d}m {s:02d}s" if h else f"{m:d}m {s:02d}s"


def fmt_time(dt) -> str:
    return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def scan_notable(lines):
    """Return a list of (count, trimmed_line) deduped notable events."""
    seen = Counter()
    for line in lines:
        if BENIGN_PATTERNS.search(line):
            continue
        if NOTABLE_PATTERNS.search(line):
            stripped = line.strip()
            # Trim leading timestamp prefix for better dedupe across runs
            trimmed = re.sub(r"^[0-9T:\-\s,]+ - ", "", stripped)
            seen[trimmed[:300]] += 1
    return seen.most_common(MAX_NOTABLE_LINES)


def phase_metrics(phase_num: int, text: str) -> dict[str, str]:
    """Extract simple metrics per phase from collected log text."""
    m: dict[str, str] = {}
    if phase_num == 1:  # Discovery
        for pat, key in [
            (r"Found (\d+) pending episodes", "pending_episodes"),
            (r"(\d+) new episodes discovered", "new_episodes"),
            (r"Episodes Found:\s*(\d+)", "episodes_found"),
        ]:
            match = re.search(pat, text)
            if match:
                m[key] = match.group(1)
    elif phase_num == 2:  # Audio
        for pat, key in [
            (r"Relevant episodes processed:\s*(\d+)", "relevant"),
            (r"Not relevant episodes processed:\s*(\d+)", "not_relevant"),
            (r"Total episodes evaluated:\s*(\d+)", "total_evaluated"),
            (r"Total rounds:\s*(\d+)", "parallel_rounds"),
        ]:
            match = re.search(pat, text)
            if match:
                m[key] = match.group(1)
    elif phase_num == 3:  # Digest
        for pat, key in [
            (r"Digests [Gg]enerated:\s*(\d+)", "digests_generated"),
            (r"Generated (\d+) digest", "digests_generated"),
        ]:
            match = re.search(pat, text)
            if match and "digests_generated" not in m:
                m["digests_generated"] = match.group(1)
    elif phase_num == 4:  # TTS
        for pat, key in [
            (r"Audio [Ff]iles [Gg]enerated:\s*(\d+)", "audio_files"),
            (r"Generated (\d+) audio", "audio_files"),
        ]:
            match = re.search(pat, text)
            if match and "audio_files" not in m:
                m["audio_files"] = match.group(1)
    elif phase_num == 5:  # Publishing
        match = re.search(r"Release.*?daily-(\d{4}-\d{2}-\d{2})", text)
        if match:
            m["release_tag"] = f"daily-{match.group(1)}"
        match = re.search(r"Uploaded (\d+) asset", text)
        if match:
            m["assets_uploaded"] = match.group(1)
    elif phase_num == 7:  # Dedup
        match = re.search(r"(\d+) groups?,\s*(\d+) arcs? merged", text)
        if match:
            m["dedup"] = f"{match.group(1)} groups / {match.group(2)} arcs merged"
    return m


def build_phase_body(phase_num, phase_title, pstart, pend, status, lines):
    duration = pend - pstart
    text = "\n".join(lines)
    metrics = phase_metrics(phase_num, text)
    notable = scan_notable(lines)
    parts = [
        f"Phase {phase_num}: {phase_title}",
        f"Status:    {status}",
        f"Started:   {fmt_time(pstart)}",
        f"Finished:  {fmt_time(pend)}",
        f"Duration:  {fmt_dur(duration)}",
        "",
    ]
    if metrics:
        parts.append("Metrics:")
        for k, v in metrics.items():
            parts.append(f"  {k}: {v}")
        parts.append("")
    if notable:
        total = sum(c for _, c in [(n[1], n[0]) for n in notable])  # noqa
        parts.append(f"Notable log patterns ({len(notable)} unique, deduped):")
        for line, count in notable:
            parts.append(f"  [{count}x] {line}")
        parts.append("")
    else:
        parts.append("No notable errors/warnings detected.\n")
    return "\n".join(parts)


def main():
    parser = argparse.ArgumentParser(description="Monitored pipeline run with per-phase email notifications.")
    parser.add_argument("--days-back", default="5")
    parser.add_argument("--limit", default="10")
    parser.add_argument("--verbose", action="store_true", default=True)
    args, extra = parser.parse_known_args()

    project_dir = Path(__file__).resolve().parent.parent
    os.chdir(project_dir)

    cmd = [
        sys.executable,
        "run_full_pipeline_orchestrator.py",
        "--verbose",
        "--days-back", args.days_back,
        "--limit", args.limit,
    ] + extra

    start_time = datetime.now(timezone.utc)
    cmd_str = " ".join(cmd)
    start_body = (
        f"Monitored pipeline run starting.\n\n"
        f"Host:    {HOSTNAME}\n"
        f"When:    {fmt_time(start_time)}\n"
        f"Command: {cmd_str}\n\n"
        f"You'll receive an email as each phase completes, plus a final summary.\n"
        f"Expected runtime: ~1h-2h. If you stop seeing emails, check\n"
        f"  ssh et01 'tail -200 /home/pbrown/logs/monitored-pipeline-*.log'\n"
    )
    send_email("[START] Pipeline run starting", start_body)

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        text=True,
        cwd=project_dir,
    )

    current = None  # (num, title, start_time)
    phase_lines: list[str] = []
    phase_events: list[tuple] = []

    def finalize_phase(pnum, ptitle, pstart, pend, status):
        body = build_phase_body(pnum, ptitle, pstart, pend, status, phase_lines)
        subject = f"[PHASE {pnum}] {status}: {ptitle} ({fmt_dur(pend - pstart)})"
        send_email(subject, body)
        phase_events.append((pnum, ptitle, pstart, pend, status))

    assert proc.stdout is not None
    for line in proc.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()

        m_start = PHASE_START.search(line)
        if m_start:
            # If a previous phase is still open (e.g., missing "Phase completed" line),
            # close it as UNKNOWN before opening the next.
            if current:
                pnum, ptitle, pstart = current
                finalize_phase(pnum, ptitle, pstart, datetime.now(timezone.utc), "UNKNOWN (next phase started)")
            current = (int(m_start.group(1)), m_start.group(2).strip(), datetime.now(timezone.utc))
            phase_lines = [line]
            continue

        if current:
            phase_lines.append(line)

        if current and PHASE_OK.search(line):
            pnum, ptitle, pstart = current
            finalize_phase(pnum, ptitle, pstart, datetime.now(timezone.utc), "SUCCESS")
            current = None
            phase_lines = []
        elif current and PIPELINE_FAIL.search(line):
            pnum, ptitle, pstart = current
            finalize_phase(pnum, ptitle, pstart, datetime.now(timezone.utc), "FAILED")
            current = None
            phase_lines = []

    proc.wait()
    exit_code = proc.returncode
    end_time = datetime.now(timezone.utc)

    # Safety net: close any dangling phase
    if current:
        pnum, ptitle, pstart = current
        finalize_phase(pnum, ptitle, pstart, end_time, f"INCOMPLETE (process exited {exit_code})")

    # Final summary
    duration = end_time - start_time
    status = "SUCCESS" if exit_code == 0 else f"FAILED (exit {exit_code})"
    summary_lines = [
        f"Pipeline run {status}.",
        "",
        f"Started:        {fmt_time(start_time)}",
        f"Finished:       {fmt_time(end_time)}",
        f"Total runtime:  {fmt_dur(duration)}",
        "",
        "Phase timings:",
    ]
    for pnum, ptitle, pstart, pend, pstatus in phase_events:
        pdur = pend - pstart if pend else None
        summary_lines.append(f"  Phase {pnum} ({pstatus:>15}): {fmt_dur(pdur):>10}  {ptitle}")
    summary = "\n".join(summary_lines)
    send_email(f"[DONE] Pipeline {status} ({fmt_dur(duration)})", summary)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
