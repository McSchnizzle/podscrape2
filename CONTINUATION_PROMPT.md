# Continuation Prompt for Phase 1 Completion

## Context
You're continuing work on **Phase 1 of the move-online migration** for the podscrape2 RSS podcast digest system. This is a sophisticated Python application that processes RSS feeds → audio transcription → AI scoring → script generation → TTS → publishing.

## Current Status
- **Branch**: `feature/move-online`
- **Progress**: Phase 1 is 85% complete
- **Critical Blocker**: Supabase database needs to be created

## Architecture Overview
- **Database**: SQLite → Supabase Postgres migration in progress
- **Pipeline**: RSS feeds → Parakeet MLX transcription → GPT scoring → ElevenLabs TTS → GitHub Releases + Vercel RSS
- **Tech Stack**: Python 3, SQLAlchemy, Alembic, Flask (web UI), PostgreSQL (Supabase)

## Immediate Priorities

### 🚨 URGENT: Database Setup (CLI AUTHENTICATED!)
**Status**: Supabase CLI is authenticated! Existing project found: `dylqxfgdozwjvbiklnfn`

**IMMEDIATE ACTION** (should take <10 minutes):
1. **Link to existing project**: `supabase link --project-ref dylqxfgdozwjvbiklnfn --password "3Z@hoz8Njo14w5llsW"`
2. **Apply schema**: Copy SQL from `supabase_setup_instructions.md` and run:
   ```bash
   supabase db reset --debug
   # OR apply the SQL manually:
   # supabase db push
   ```
3. **Verify connection**: `python3 scripts/doctor.py` (should show ✅ DATABASE_URL connectivity)
4. **Run migration**: `alembic upgrade head`

### Key Files to Review
- `supabase_setup_instructions.md` - Complete SQL schema ready to deploy
- `PHASE1_PROGRESS.md` - Detailed progress report
- `move-online.md` - Updated with current progress checkmarks
- `scripts/doctor.py` - Environment validation (20/23 checks passing)

## Remaining Phase 1 Tasks

### High Priority (2-4 hours total)
1. **Database Connection** (30 min after Supabase setup)
   - Verify: `python3 scripts/doctor.py` shows "✅ DATABASE_URL connectivity"
   - Run migration: `alembic upgrade head`
   - Test data migration: `PYTHONPATH=src python3 scripts/migrate_sqlite_to_pg.py`

2. **Refactor Database Models** (2-3 hours)
   - **File**: `src/database/models.py`
   - **Goal**: Replace SQLite-specific code with SQLAlchemy sessions
   - **Key Changes**:
     - Replace `json_extract()` with `.scores->>topic`
     - Replace `date('now', '-7 days')` with `now() - interval '7 days'`
     - Use SQLAlchemy sessions instead of raw SQL
     - Keep SQLite fallback for offline dev

3. **Enhanced Pipeline CLI** (1-2 hours)
   - **File**: `run_full_pipeline.py`
   - **Add Flags**: `--dry-run`, `--limit N`, `--from-step`, `--to-step`
   - **Create Subcommands**: Individual commands for each phase

### Medium Priority
4. **Integration Tests** (2-3 hours)
   - Create pytest fixtures for pipeline phases
   - Mock external APIs (OpenAI, ElevenLabs)
   - Test idempotency and phase isolation

## Development Environment

### Quick Setup
```bash
# Activate environment
source .venv/bin/activate  # if using venv

# Install dependencies
python3 -m pip install -r requirements.txt

# Run environment check
python3 scripts/doctor.py

# Start development
bash scripts/bootstrap_local.sh
```

### Key Commands
```bash
# Environment validation
python3 scripts/doctor.py

# Pipeline testing (after DB setup)
python3 run_full_pipeline.py --phase discovery

# Database migration
alembic upgrade head

# Development server
bash scripts/run_web_ui.sh
```

## Technical Context

### Database Models (Already Created)
- **Location**: `src/database/sqlalchemy_models.py`
- **Tables**: `feeds`, `episodes`, `digests`
- **Features**: JSONB fields, proper indexes, Postgres-optimized

### Migration System (Ready)
- **Alembic Config**: `alembic.ini` configured for environment-based DATABASE_URL
- **Initial Migration**: `alembic/versions/1ad9f7f93530_initial_schema_creation.py`
- **Data Migration**: `scripts/migrate_sqlite_to_pg.py`

### Environment Management
- **Config**: `src/config/env.py` handles Supabase URL resolution
- **Validation**: `scripts/doctor.py` comprehensive environment check
- **Setup**: `scripts/bootstrap_local.sh` development environment

## Quality Standards
- **Testing**: Use real RSS feeds, no mocks (see CLAUDE.md)
- **Python**: Always use `python3` command (macOS compatibility)
- **Error Handling**: Graceful degradation, comprehensive logging
- **Documentation**: Update progress in move-online.md

## Success Criteria for Phase 1 Completion
1. ✅ Database connectivity working (`scripts/doctor.py` passes all checks)
2. ✅ SQLAlchemy models integrated with existing pipeline
3. ✅ Enhanced CLI flags implemented and tested
4. ✅ Integration tests created and passing
5. ✅ All move-online.md Phase 1 tasks marked complete

## Files to Focus On
- `src/database/models.py` - Database abstraction layer (needs SQLAlchemy refactor)
- `run_full_pipeline.py` - Main pipeline (needs additional CLI flags)
- `scripts/doctor.py` - Environment validation (working, needs DB connection)
- `move-online.md` - Progress tracking (keep updated)

## ⚡ Supabase CLI Ready!
**EXCELLENT NEWS**: Supabase CLI is authenticated and project exists!

**Quick Database Setup** (run these commands):
```bash
# 1. Link to the existing project
supabase link --project-ref dylqxfgdozwjvbiklnfn --password "3Z@hoz8Njo14w5llsW"

# 2. Check if schema needs to be applied
supabase db diff

# 3. Apply our schema (copy SQL from supabase_setup_instructions.md)
# Either reset the DB or apply SQL manually

# 4. Verify everything works
python3 scripts/doctor.py
alembic upgrade head
```

**Key Discovery**: The existing project `dylqxfgdozwjvbiklnfn` matches our .env configuration perfectly. The database just needs the schema applied.

Start by checking the database connectivity status and then proceed with the remaining implementation tasks!