#!/usr/bin/env python3
"""
Create a Postgres backup (pg_dump) using DATABASE_URL and write to data/backups.
Uploads would be handled by CI; this script focuses on producing the dump file.
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from src.config.env import require_database_url


def main() -> None:
    load_dotenv()
    db_url = require_database_url()
    # pg_dump expects a libpq-style URL without the SQLAlchemy driver suffix.
    pg_url = db_url.replace("postgresql+psycopg://", "postgresql://")

    out_dir = Path("data") / "backups"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"pg_dump_{ts}.sql"

    cmd = [
        "pg_dump",
        "--no-owner",
        "--no-privileges",
        "--format=plain",
        pg_url,
    ]

    print(f"Running pg_dump to {out_path}...")
    with open(out_path, "w", encoding="utf-8") as f:
        subprocess.run(cmd, check=True, stdout=f)
    print("Backup complete:", out_path)


if __name__ == "__main__":
    main()
