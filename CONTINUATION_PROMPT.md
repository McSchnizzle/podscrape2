# Supabase Migration Continuation Prompt

## Current Status

✅ **COMPLETED** (as of commit adaf932):
- Main pipeline scripts (`run_full_pipeline.py`, `run_publishing_pipeline.py`) fully migrated to Supabase
- Web UI (`web_ui/app.py`) fully migrated - all ~30+ direct SQL calls converted to SQLAlchemy repositories
- Repository pattern implemented with comprehensive CRUD operations in `src/database/models.py`
- Additional repository methods added for complex web UI queries

## ✅ SUPABASE MIGRATION COMPLETED (as of commit a112c24)

**All utility scripts successfully migrated:**
1. ✅ **`rescore_episodes.py`** - Converted to use episode repository with get_by_status_list()
2. ✅ **`reset_latest_episode.py`** - Converted to use episode repository for status resets
3. ✅ **`demo_phase4.py`** - Migrated to use Feed/Episode models and repository pattern
4. ✅ **`test_new_digests.py`** - Converted to use get_scored_episodes_sample() method
5. ✅ **`run_full_pipeline.py`** - Removed SQLite imports, migrated to feed repository
6. ✅ **`run_publishing_pipeline.py`** - Removed database manager dependency
7. ✅ **`transcribe_episode.py`** - Migrated from archived rss_models to current repository pattern

**All SQLite references removed:**
- No more `import sqlite3` anywhere in codebase
- No more `execute_query`/`execute_update` calls
- All direct database calls replaced with repository methods

### Priority 2: Test Files
**Search pattern:** Files containing `sqlite3|get_db_connection|execute_query|execute_update|DatabaseManagerOld`

Use these commands to find remaining files:
```bash
grep -r "execute_query\|execute_update\|get_db_connection\|sqlite3" --include="*.py" . --exclude-dir=archive
grep -r "from.*models.*import.*get_database_manager" --include="*.py" . --exclude-dir=archive
```

### Priority 3: Validation
- Run all migrated scripts to ensure they work with Supabase
- Test Web UI functionality end-to-end
- Run any existing test suites

## 🔧 MIGRATION APPROACH

### For Utility Scripts:
1. **Import pattern**: Replace old imports with:
   ```python
   from database.models import get_feed_repo, get_episode_repo, get_digest_repo
   ```

2. **Repository usage**: Replace direct SQL with repository methods:
   ```python
   # OLD
   dbm = get_database_manager()
   rows = dbm.execute_query("SELECT * FROM episodes WHERE status = ?", (status,))

   # NEW
   episode_repo = get_episode_repo()
   episodes = episode_repo.get_by_status(status)
   ```

3. **Available repository methods** (see `src/database/models.py`):
   - **EpisodeRepository**: `get_by_status()`, `update_status()`, `update_scores()`, `get_by_id()`, etc.
   - **FeedRepository**: `get_by_url()`, `get_all()`, `create()`, etc.
   - **DigestRepository**: `get_by_date()`, `get_recent_digests()`, `create()`, etc.

### For Test Files:
1. Update database setup to use Supabase test database or fixtures
2. Replace old database patterns with repository calls
3. Ensure test isolation (tests should not interfere with production data)

## 🗄️ DATABASE CONTEXT

**Current setup:**
- **Database**: Supabase PostgreSQL via `DATABASE_URL` environment variable
- **Models**: SQLAlchemy models in `src/database/sqlalchemy_models.py`
- **Repositories**: Repository pattern in `src/database/models.py`
- **Schema**: Alembic migrations in `supabase/migrations/`

**Repository Factory Functions:**
```python
from database.models import get_database_manager, get_feed_repo, get_episode_repo, get_digest_repo

# Use these instead of direct database calls
feed_repo = get_feed_repo()
episode_repo = get_episode_repo()
digest_repo = get_digest_repo()
```

## 📋 REMAINING TASKS

**Phase 1a Supabase Migration: COMPLETE ✅**
- [x] Migrate `rescore_episodes.py` to repository pattern
- [x] Migrate `reset_latest_episode.py` to repository pattern
- [x] Migrate `demo_phase4.py` to repository pattern
- [x] Migrate `test_new_digests.py` to repository pattern
- [x] Migrate `run_full_pipeline.py` and `run_publishing_pipeline.py`
- [x] Migrate `transcribe_episode.py` to repository pattern
- [x] Remove all SQLite imports and direct database calls

**Remaining optional tasks:**
- [ ] Archive or migrate test files with old database patterns (low priority)
- [ ] Enable RLS (Row Level Security) on Supabase (security best practice)
- [ ] Update move-online.md Phase 1a to mark as complete

## 🚨 IMPORTANT NOTES

- **NO SQLite fallback needed** - full migration to Supabase/PostgreSQL
- **Repository methods handle all database operations** - no raw SQL needed for basic operations
- **Existing functionality must be preserved** - test thoroughly after migration
- **Archive obsolete files** - move them to `archive/` directory instead of deleting

## 💡 NEXT STEPS AFTER MIGRATION

Once migration is complete, the next phases in move-online.md are:
- Phase 1: Modularize Pipeline for Single-Phase Runs
- Phase 2: Storage and Artifact Strategy
- Phase 3: CI/CD setup
- Phase 4: Web UI Hosting + DNS

---

**Ready to continue the Supabase migration! Start with `rescore_episodes.py` and work through the remaining utility scripts.**