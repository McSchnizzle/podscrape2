# Phase 5 Task List — Web UI Hosting & DNS Migration

## Phase 5 Status Summary ✅ 90% COMPLETE

**Major Achievements Completed**:
- ✅ **Complete feature parity**: 8/8 pages migrated to Next.js/Vercel with database integration
- ✅ **Settings Bridge**: Pipeline scripts read configuration from `web_settings` table
- ✅ **Topics Migration**: Complete topic instructions migrated from files to database
- ✅ **Multi-Topic Processing**: Verified all 3 topics process correctly (content scarcity resolved)
- ✅ **Performance Optimization**: 30-second API caching implemented
- ✅ **RSS Publishing**: Production feed serving at `podcast.paulrbrown.org/daily-digest.xml`

**Subphases Completed**: 5.0 ✅ | 5.1 ✅ | 5.2 ✅ | 5.3 ✅ | 5.4 ✅ | 5.5 ✅ | 5.6 ⚠️ Partial

## Critical Architecture Issue ⚠️ BLOCKING FULL CLOUD-NATIVE

### F. Transcript Database Migration 🔥 HIGH PRIORITY

**Problem**: Transcripts stored as files (`data/transcripts/`) create file system dependencies and deployment complexity.

**Current Architecture Issues**:
- File paths stored in `episodes.transcript_path` (VARCHAR 4096)
- Complex file management with `data/transcripts/` → `data/transcripts/digested/` moves
- GitHub Actions must manage file system state alongside database
- Backup complexity: database + file system
- File/database sync issues and missing file errors

**Solution**: Migrate transcript storage to database for cloud-native architecture.

**Technical Analysis**:
- ✅ **Supabase Capacity**: PostgreSQL TEXT fields support 1GB (current max transcript: 53K chars)
- ✅ **Performance**: Direct database queries faster than file I/O
- ✅ **Data Integrity**: ACID compliance, no file/database sync issues
- ✅ **Deployment**: No file system dependencies in GitHub Actions

**Database Schema Change**:
```sql
-- Add transcript content column
ALTER TABLE episodes ADD COLUMN transcript_content TEXT;

-- Keep transcript_path for backward compatibility during migration
-- transcript_path will be deprecated after migration complete
```

**Migration Strategy (5 Phases)**:

**Phase F.1: Schema Migration ⚠️ REQUIRED**
- Add `transcript_content TEXT` column to episodes table
- Create Alembic migration for schema change
- Deploy database schema update

**Phase F.2: Dual-Write Implementation ⚠️ REQUIRED**
- Update `scripts/run_audio.py` transcript generation to write both file AND database
- Update `Episode.update_transcript()` method to accept content parameter
- Ensure backward compatibility with existing file-based reads

**Phase F.3: Existing Data Migration ⚠️ REQUIRED**
- Create migration script to read all existing transcript files
- Populate `transcript_content` for episodes with `transcript_path`
- Verify data integrity (file content matches database content)
- Target: ~50 existing transcript files in `data/transcripts/` and `data/transcripts/digested/`

**Phase F.4: Code Migration ⚠️ REQUIRED**
- Update all transcript readers to use `episode.transcript_content` instead of file paths:
  - **Audio Phase**: `scripts/run_audio.py` (transcript generation and validation)
  - **Scoring Phase**: `scripts/run_scoring.py` (reading transcripts for AI scoring)
  - **Scoring Phase**: `src/scoring/content_scorer.py` (transcript file reading methods)
  - **Digest Phase**: `src/generation/script_generator.py` (reading transcripts for digest generation)
  - **Digest Phase**: `src/generation/configurable-script_generator.py` (reading transcripts for topic-specific digests)
  - **Utilities**: `rescore_episodes.py` (re-scoring existing episodes)
- Remove complex file movement logic in script generators (digested/ folder management)
- Simplify error handling (no missing file checks needed)
- Update pipeline phase validation to check database content instead of file existence

**Phase F.5: Cleanup ⚠️ REQUIRED**
- Remove `transcript_path` column and related code
- Remove `data/transcripts/` directory and .gitignore entries
- Update documentation and README references

**Expected Benefits**:
- ✅ **Simplified codebase**: Remove 50+ lines of file management logic
- ✅ **Cloud-native**: No file system dependencies in workflows
- ✅ **Data integrity**: Atomic transcript + metadata updates
- ✅ **Better performance**: Database queries vs file I/O
- ✅ **Simplified backup**: Single database backup includes everything

**Implementation Files to Modify**:
```
Database:
- alembic/versions/new_migration.py (schema change)
- src/database/sqlalchemy_models.py (add transcript_content field)

Pipeline Scripts (ALL 3 PHASES):
- scripts/run_audio.py (AUDIO PHASE: dual-write during generation + validation)
- scripts/run_scoring.py (SCORING PHASE: read from database for AI scoring)
- src/scoring/content_scorer.py (SCORING PHASE: database content reading methods)
- src/generation/script_generator.py (DIGEST PHASE: read from database for digest generation)
- src/generation/configurable-script_generator.py (DIGEST PHASE: read from database for topic digests)

Migration Scripts:
- migrate_transcripts_to_database.py (new script)

Cleanup:
- Remove transcript_path references across codebase
- Update .gitignore and documentation
```

**Testing Requirements**:
- Verify transcript content preservation during migration
- **Test Audio Phase**: Transcript generation writes to database correctly
- **Test Scoring Phase**: AI content scoring reads from database instead of files
- **Test Digest Phase**: Script generation reads from database for all topics
- Test pipeline phase validation logic (check database content exists)
- Validate GitHub Actions workflows with new architecture (no file system dependencies)

## Completed Polish Items ✅

- ✅ **Episode Status Workflow**: Eliminated 'discovered' status orphan episodes and implemented FAIL FAST database configuration
  - Migrated 10 episodes from 'discovered' to 'pending' status with cleared transcript/score data
  - Updated Web UI to use 'pending' status instead of 'discovered' for episode resets
  - Removed fallback defaults in discovery script - pipeline now fails fast if database settings unavailable
  - Discovery phase automatically processes 'pending' episodes creating natural backlog system

## Remaining Polish Items

- ⚠️ **Transcript Database Migration**: Critical for full cloud-native architecture
- ⚠️ **Dynamic server usage warning**: /api/logs/stream route optimization
- ⚠️ Mobile device testing on iOS/Android for all pages

## Success Criteria for Phase 5 Completion

- ✅ Settings changes in hosted UI affect pipeline execution immediately
- ✅ All 3 topics generate digests daily via database configuration
- ✅ Episodes/Topics pages load in <2 seconds with caching
- ⚠️ **Transcripts stored in database with no file system dependencies**
- ⚠️ **Pipeline fully cloud-native with atomic data operations**

---

## Quick Implementation Prompt for Transcript Migration

**Context**: Phase 5 is 90% complete. The final critical task is migrating transcript storage from files to database for full cloud-native architecture.

**Goal**: Add `transcript_content TEXT` column to episodes table and migrate all transcript reading/writing to use database instead of file system.

**Key Requirements**:
1. **Schema**: Add `transcript_content TEXT` to episodes table via Alembic migration
2. **Audio Phase**: Update `scripts/run_audio.py` to write transcript to both file AND database during transition
3. **Scoring Phase**: Update `scripts/run_scoring.py` and `src/scoring/content_scorer.py` to read from database
4. **Digest Phase**: Update `src/generation/*.py` scripts to read from database for digest generation
5. **Data migration**: Script to populate `transcript_content` from existing ~50 transcript files
6. **Pipeline validation**: Update phase validation to check database content instead of file existence
7. **Cleanup**: Remove file-based logic and `transcript_path` column

**Critical Pipeline Impact**: ALL 3 MAIN PHASES (Audio, Scoring, Digest) must be updated to use database storage.

**Benefits**: Eliminates file system dependencies, simplifies codebase by 50+ lines, enables atomic operations, improves performance.

**Files**: See "Pipeline Scripts (ALL 3 PHASES)" section above for complete list.

**Current transcript sizes**: 20K-53K characters (well within PostgreSQL 1GB TEXT limit).