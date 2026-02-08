#!/usr/bin/env python3
"""
Pipeline Failure Notification

Sends an email alert when the podcast pipeline fails.
Requires GMAIL_APP_PASSWORD in .env (generate at https://myaccount.google.com/apppasswords).
"""

import os
import sys
import smtplib
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path

# Configuration
RECIPIENT = "paulinpdx503@gmail.com"
SENDER = "paulinpdx503@gmail.com"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587


def send_failure_email(exit_code: int, log_tail: str = "", runtime: str = ""):
    """Send pipeline failure notification email."""
    password = os.environ.get("GMAIL_APP_PASSWORD")
    if not password:
        print("WARNING: GMAIL_APP_PASSWORD not set - cannot send failure notification")
        print("Generate one at: https://myaccount.google.com/apppasswords")
        return False

    hostname = socket.gethostname()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")

    subject = f"Podcast Pipeline FAILED on {hostname} ({timestamp})"

    body = f"""Podcast Pipeline Failure Alert
================================

Host: {hostname}
Time: {timestamp}
Exit Code: {exit_code}
Runtime: {runtime or 'unknown'}

Last 50 lines of output:
------------------------
{log_tail}

---
Check full logs: ssh et01 'tail -200 /home/pbrown/logs/podcast-cron.log'
Run manually: ssh et01 'cd /srv/projects/podcast-pipeline && . .venv/bin/activate && python3 run_full_pipeline_orchestrator.py --verbose'
"""

    msg = MIMEMultipart()
    msg["From"] = SENDER
    msg["To"] = RECIPIENT
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER, password)
            server.send_message(msg)
        print(f"Failure notification sent to {RECIPIENT}")
        return True
    except Exception as e:
        print(f"Failed to send notification email: {e}")
        return False


def send_success_email(runtime: str = "", digests: int = 0, episodes: int = 0):
    """Send pipeline success notification (optional, for daily confirmation)."""
    password = os.environ.get("GMAIL_APP_PASSWORD")
    if not password:
        return False

    hostname = socket.gethostname()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")

    subject = f"Podcast Pipeline OK - {digests} digest(s) ({timestamp})"
    body = f"""Pipeline completed successfully.

Host: {hostname}
Time: {timestamp}
Runtime: {runtime}
Episodes found: {episodes}
Digests generated: {digests}
"""

    msg = MIMEMultipart()
    msg["From"] = SENDER
    msg["To"] = RECIPIENT
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER, password)
            server.send_message(msg)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    # Called directly: send_failure with exit code as argument
    exit_code = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    log_tail = sys.argv[2] if len(sys.argv) > 2 else ""
    send_failure_email(exit_code, log_tail)
