#!/usr/bin/env python3
"""
One-time migration from local SQLite (data/database/digest.db) to Supabase Postgres.
Requires DATABASE_URL in environment; no SQLite fallback.
"""

import os
import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, Iterable

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

# Local imports
from src.config.env import require_database_url
from src.database.sqlalchemy_models import Base, Feed, Episode, Digest


def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {k: row[k] for k in row.keys()}


def migrate_feeds(sqlite_conn: sqlite3.Connection, session: Session) -> int:
    sqlite_conn.row_factory = sqlite3.Row
    rows = sqlite_conn.execute("SELECT * FROM feeds").fetchall()
    count = 0
    for r in rows:
        d = row_to_dict(r)
        stmt = pg_insert(Feed).values(
            id=d.get("id"),
            feed_url=d.get("feed_url"),
            title=d.get("title"),
            description=d.get("description"),
            active=bool(d.get("active", 1)),
            consecutive_failures=d.get("consecutive_failures", 0),
            last_checked=d.get("last_checked"),
            last_episode_date=d.get("last_episode_date"),
            total_episodes_processed=d.get("total_episodes_processed", 0),
            total_episodes_failed=d.get("total_episodes_failed", 0),
            created_at=d.get("created_at") or datetime.utcnow(),
            updated_at=d.get("updated_at") or datetime.utcnow(),
        ).on_conflict_do_nothing(index_elements=[Feed.feed_url])
        session.execute(stmt)
        count += 1
    return count


def migrate_episodes(sqlite_conn: sqlite3.Connection, session: Session) -> int:
    import json

    sqlite_conn.row_factory = sqlite3.Row
    rows = sqlite_conn.execute("SELECT * FROM episodes").fetchall()
    count = 0
    for r in rows:
        d = row_to_dict(r)
        # Normalize JSON
        scores = None
        if d.get("scores"):
            try:
                scores = json.loads(d.get("scores"))
            except Exception:
                scores = None
        stmt = pg_insert(Episode).values(
            id=d.get("id"),
            episode_guid=d.get("episode_guid"),
            feed_id=d.get("feed_id"),
            title=d.get("title"),
            published_date=d.get("published_date"),
            audio_url=d.get("audio_url"),
            duration_seconds=d.get("duration_seconds"),
            description=d.get("description"),
            audio_path=d.get("audio_path"),
            audio_downloaded_at=d.get("audio_downloaded_at"),
            transcript_path=d.get("transcript_path"),
            transcript_generated_at=d.get("transcript_generated_at"),
            transcript_word_count=d.get("transcript_word_count"),
            chunk_count=d.get("chunk_count", 0),
            scores=scores,
            scored_at=d.get("scored_at"),
            status=d.get("status", "pending"),
            failure_count=d.get("failure_count", 0),
            failure_reason=d.get("failure_reason"),
            last_failure_at=d.get("last_failure_at"),
            created_at=d.get("created_at") or datetime.utcnow(),
            updated_at=d.get("updated_at") or datetime.utcnow(),
        ).on_conflict_do_nothing(index_elements=[Episode.episode_guid])
        session.execute(stmt)
        count += 1
    return count


def migrate_digests(sqlite_conn: sqlite3.Connection, session: Session) -> int:
    import json

    sqlite_conn.row_factory = sqlite3.Row
    rows = sqlite_conn.execute("SELECT * FROM digests").fetchall()
    count = 0
    for r in rows:
        d = row_to_dict(r)
        episode_ids = None
        if d.get("episode_ids"):
            try:
                episode_ids = json.loads(d.get("episode_ids"))
            except Exception:
                episode_ids = None
        stmt = pg_insert(Digest).values(
            id=d.get("id"),
            topic=d.get("topic"),
            digest_date=d.get("digest_date"),
            script_path=d.get("script_path"),
            script_word_count=d.get("script_word_count"),
            mp3_path=d.get("mp3_path"),
            mp3_duration_seconds=d.get("mp3_duration_seconds"),
            mp3_title=d.get("mp3_title"),
            mp3_summary=d.get("mp3_summary"),
            episode_ids=episode_ids,
            episode_count=d.get("episode_count", 0),
            average_score=d.get("average_score"),
            github_url=d.get("github_url"),
            published_at=d.get("published_at"),
            generated_at=d.get("generated_at") or datetime.utcnow(),
        ).on_conflict_do_nothing(constraint="uq_digests_topic_date")
        session.execute(stmt)
        count += 1
    return count


def main() -> None:
    load_dotenv()
    db_url = require_database_url()

    project_root = Path(__file__).resolve().parent.parent
    sqlite_path = project_root / "data" / "database" / "digest.db"
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite DB not found at {sqlite_path}")

    print("Connecting to Supabase Postgres...")
    engine = create_engine(db_url, future=True)

    # Create tables if they don't exist yet
    Base.metadata.create_all(engine)

    print(f"Reading from SQLite: {sqlite_path}")
    with sqlite3.connect(str(sqlite_path)) as sqlite_conn, Session(engine) as session:
        sqlite_conn.row_factory = sqlite3.Row
        # Preserve a single transaction for speed
        print("Migrating feeds...")
        n_feeds = migrate_feeds(sqlite_conn, session)
        print(f"  inserted/seen feeds: {n_feeds}")

        print("Migrating episodes...")
        n_eps = migrate_episodes(sqlite_conn, session)
        print(f"  inserted/seen episodes: {n_eps}")

        print("Migrating digests...")
        n_dig = migrate_digests(sqlite_conn, session)
        print(f"  inserted/seen digests: {n_dig}")

        session.commit()
        print("Migration complete.")


if __name__ == "__main__":
    main()

