# Archived Migration Scripts

These scripts are historical one-time migration utilities that have already been executed.
They are preserved for reference only - DO NOT run them on production.

## Contents

### From Project Root:
- `migrate_add_digest_timestamp.py` - Added digest_timestamp column to digests table
- `migrate_transcripts_to_database.py` - Migrated transcript files to database storage

### From scripts/:
- `migrate_sqlite_to_pg.py` - Migrated SQLite database to PostgreSQL/Supabase
- `migrate_tasks_to_database.py` - Migrated tasks from JSON to database
- `migrate_topics_to_supabase.py` - Migrated topics configuration to Supabase

### From src/database/:
- `migrate_phase7.py` - Phase 7 migration utilities

## Notes

- All migrations have been applied to production Supabase database
- Schema changes are now managed via Alembic migrations: `alembic/versions/`
- Run `python3 -m alembic upgrade head` for current schema updates

## Archived Date
2025-12-20 (GitHub Issue #9: Consolidate data access on Supabase)
