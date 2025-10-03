# RSS Podcast Digest System - Remaining Tasks

**Last Updated**: 2025-10-03 (v1.51)
**Note**: All completed tasks have been moved to `COMPLETED_TASKS_SUMMARY.md`

## Overview

This document lists ONLY the remaining tasks that need to be completed. 

**Core Principle**: FAIL FAST, FAIL LOUD - No silent failures, no fallbacks that mask configuration issues.

**Testing Requirement**: For every task, we MUST have a way to test that it actually works.

---

## CRITICAL (P0) - Security & Breaking Issues: 1 ACTIVE

### 🚨 ACTIVE: Pipeline Optimization & Publishing Bug Fix (v1.51)
**Started**: 2025-10-03 | **Status**: Phase 1 Complete ✅, Phases 2-7 In Progress

#### Root Cause (RESOLVED ✅)
- **Publishing Bug**: TTS wrote MP3s to `data/completed-tts/current/` but Publishing looked in `data/completed-tts/` with `-maxdepth 1`
- **Evidence**: Workflow run #18222688073 - TTS created 3 MP3s successfully, Publishing reported "No new MP3 files detected"
- **Impact**: 3 episodes from 2025-10-03 not published to RSS feed

#### Implementation Phases (7 total) - ALL COMPLETE ✅
- [x] **Phase 1** (60 min): Fix publishing bug - restore today's 3 episodes ⚡ **COMPLETE**
  - Fixed `audio_manager.py` to write directly to `data/completed-tts/` (removed `current/` subdirectory)
  - Fixed `metadata_generator.py` to use `digest.script_content` from database (database-first architecture)
  - Regenerated 3 MP3s with fixed paths: AI & Tech, Social Movements, Psychedelics
  - Published to GitHub release `daily-2025-10-03`
  - Validated RSS feed shows all 3 new episodes with correct URLs
- [x] **Phase 2** (30 min): Add retention phase - single source of cleanup truth ⚡ **COMPLETE**
  - Created `scripts/run_retention.py` as dedicated Phase 6
  - Removed retention from Discovery (run_discovery.py:157-174)
  - Removed retention from Publishing (run_publishing.py:724-730)
  - Added to GitHub Actions workflow as Phase 6 step
- [x] **Phase 3** (15 min): Remove dead RSS code (~220 lines) ⚡ **COMPLETE**
  - Removed `generate_rss_feed()`, `deploy_to_vercel()`, `commit_rss_to_main()` methods
  - Added explanatory comment (RSS now dynamic since v1.49)
- [x] **Phase 4** (45 min): Fix TTS atomicity - prevent future orphans ⚡ **COMPLETE**
  - Added MP3 validation before database commit
  - Added cleanup on failure in `complete_audio_processor.py`
  - Removed redundant `organize_audio_files()` section
- [x] **Phase 5** (10 min): Remove verify/repair - simplify publishing ⚡ **COMPLETE**
  - Removed redundant verification loop from `run_publishing.py`
  - Renumbered steps (4→3, 5→4)
- [x] **Phase 6** (30 min): Add state validation - catch corruption early ⚡ **COMPLETE**
  - Added `Episode.validate_state()` to `sqlalchemy_models.py`
  - Added `Digest.validate_state()`, `is_ready_for_tts()`, `is_ready_for_publishing()`
- [x] **Phase 7** (10 min): Update phase naming - documentation ⚡ **COMPLETE**
  - Added Phase 6 (Retention) to orchestrator and workflow
  - Updated argparse choices to include all 6 phases
  - Updated comments to reflect new architecture

#### Files Changed/To Change (10 total) - ALL COMPLETE ✅
- [x] `src/audio/audio_manager.py` - Removed current/ subdirectory logic ✅
- [x] `src/audio/metadata_generator.py` - Uses database content, not files ✅
- [x] `src/generation/script_generator.py` - Delete script files after database upload ✅
- [x] `src/audio/complete_audio_processor.py` - Atomic TTS with rollback ✅
- [x] `src/database/sqlalchemy_models.py` - State validation methods (Episode + Digest) ✅
- [x] `scripts/run_retention.py` - NEW - Dedicated retention phase with all 6 settings ✅
- [x] `scripts/run_discovery.py` - Removed retention cleanup ✅
- [x] `scripts/run_publishing.py` - Removed dead RSS code, verify/repair, cleanup ✅
- [x] `run_full_pipeline_orchestrator.py` - Added Phase 6, updated naming ✅
- [x] `.github/workflows/validated-full-pipeline.yml` - Added Phase 6 retention step ✅

#### Validation Checklist
- [x] Fix applied and 3 orphaned MP3s published ✅
- [x] RSS feed shows 3 new episodes for 2025-10-03 ✅
- [x] Retention manager uses all 6 web_settings values ✅
- [ ] Full pipeline test via GitHub Actions completes all 6 phases
- [ ] Database state validation methods tested
- [ ] Retention phase completes successfully in GitHub Actions

**Detailed Plan**: See comprehensive breakdown in plan mode output above

---

## HIGH (P1) - Core Functionality Issues: 0 REMAINING

**All P1 tasks completed!** 🎉

---

## MEDIUM (P2) - Performance & Optimization: 4 REMAINING

### 1. Orchestrator Memory Management
- **File**: `run_full_pipeline_orchestrator.py`
- **Issue**: Implement rolling buffer for stdout_lines (keep last 100-200 lines)
- **Fix**: Stream large outputs directly to log file, add memory usage monitoring
- **Expected Gain**: Reduced memory usage for large outputs
- **Status**: ❌ Not implemented

### 2. Database Connection Optimization
- **Files**: SQLAlchemy usage throughout codebase
- **Issue**: No evidence of connection pooling or prepared statements
- **Fix**: Implement connection pooling and compiled statement caching
- **Expected Gain**: Better database performance and resource usage
- **Status**: ❌ Not implemented

### 3. Memory Optimization for Large Transcripts
- **Files**: Transcript processing code
- **Issue**: Large files read entirely into memory
- **Fix**: Implement streaming processing for large files
- **Expected Gain**: Reduced memory footprint for large transcripts
- **Status**: ❌ Not implemented

### 4. Remove Unnecessary Caching
- **Issue**: Remove Whisper cache from publishing workflow
- **Fix**: Audit other caches for actual usage, document what caches are needed
- **Expected Gain**: Cleaner workflows, less confusion
- **Status**: ❌ Not implemented

---

## LOW (P3) - Architecture & Nice-to-Have: 16 REMAINING

### 1. Vercel CLI Integration for RSS Updates
- **Current Issue**: RSS updates require git commits, causing race conditions
- **Proposed Solution**: Use Vercel CLI for direct deployment
- **Benefits**: No race conditions, faster updates, cleaner git history
- **Status**: ❌ Not implemented

### 2. Async/Await Adoption
- **Scope**: Entire codebase
- **Issue**: Synchronous code for I/O-bound operations
- **Fix**: Migrate I/O operations to async/await patterns
- **Expected Gain**: Better concurrency and resource utilization
- **Status**: ❌ Not implemented

### 3. Connection Pooling Implementation
- **Scope**: Database and HTTP connections
- **Issue**: No connection reuse optimization
- **Fix**: Implement connection pools for database and HTTP clients
- **Expected Gain**: Reduced connection overhead
- **Status**: ❌ Not implemented

### 4. Memory-Efficient Streaming
- **Scope**: Large file processing
- **Issue**: Memory usage scales with file size
- **Fix**: Implement streaming for large file operations
- **Expected Gain**: Constant memory usage regardless of file size
- **Status**: ❌ Not implemented

### 5. Voice Characteristics in Recommendations
- **File**: `src/audio/voice_manager.py:112-133`
- **Issue**: Computes voice gender lists but ignores them, assigns first 4 voices
- **Fix**: Map topics to appropriate voice gender categories, persist in topics.json
- **Expected Gain**: Better voice-topic matching, configurable per topic
- **Status**: ❌ Not implemented

### 6. Remove MD File Fallback from Digest Generation
- **File**: `src/generation/script_generator.py:118-173`
- **Issue**: Script generator still has fallback logic to read from `digest_instructions/*.md` files
- **Current State**: Instructions already in database (`topics.instructions_md` field) with Script Lab as editor
- **Required Changes**:
  - Remove filesystem fallback logic (lines 146-173)
  - Keep only database instruction loading (lines 131-144)
  - Update logging to indicate database-only source
  - Delete `digest_instructions/` directory after migration verified
- **Benefits**: Single source of truth, simpler code, no file sync issues
- **Status**: ❌ Not implemented

### 7. Database Retention and Cleanup System
- **Goal**: Implement automated database cleanup to prevent database bloat
- **Implementation**: Delete episodes/digests based on configurable retention periods
- **Status**: 🔄 Partially implemented - needs completion

### 8. Enhanced Discovery Phase Logging
- **File**: `scripts/run_discovery.py`
- **Issue**: No detailed summary of episodes added to database during discovery
- **Enhancement**: Add comprehensive logging at end of discovery phase
- **Format**: "Feed: [Feed Name] - Episode: [Episode Title]"
- **Benefits**: Better visibility into discovery effectiveness
- **Status**: ❌ Not implemented

### 9. Enhanced Audio Phase Processing Logging
- **File**: `scripts/run_audio.py`
- **Issue**: No detailed summary of episode processing results and scoring
- **Enhancement**: Add comprehensive logging at end of audio phase
- **Format**: "Episode: [Title] - Scores: [Topic1: 0.75, Topic2: 0.42] - Status: [scored/not_relevant]"
- **Benefits**: Better understanding of scoring results
- **Status**: ❌ Not implemented

### 10. Topic-Specific RSS Feeds
- **Goal**: Replace single `daily-digest.xml` with topic-specific feeds
- **Implementation**: Generate separate RSS feeds for each topic
- **Benefits**: Users can subscribe to individual topics separately
- **Status**: ❌ Not implemented

### 11. Analytics & Metrics Dashboard
- **Goal**: Create comprehensive analytics dashboard for feed processing pipeline
- **Features**: Feed performance metrics, episode status distribution, topic coverage
- **Benefits**: Clear visibility into feed quality and processing efficiency
- **Status**: ❌ Not implemented

### 12. Structured Logging & Monitoring
- **Issue**: Add structured logging throughout, implement log rotation
- **Fix**: Add metrics collection, performance tracking, alerting for failures
- **Status**: ❌ Not implemented

### 13. Code Quality Improvements
- **Issue**: Remove unused imports, consolidate workflow duplication
- **Fix**: Standardize error handling, add pre-commit hooks
- **Status**: ❌ Not implemented

### 14. Testing & Validation
- **Issue**: Add orchestrator tests, fix test environment issues
- **Fix**: Create comprehensive test suite with real RSS feeds
- **Status**: ❌ Not implemented

### 15. Enhanced Dashboard with Recent Run Details
- **Issue**: Dashboard lacks detailed information about recent pipeline run from GitHub logs
- **Fix**: Pull GitHub Action logs and display detailed run information
- **Expected Gain**: Better visibility into pipeline execution
- **Status**: ❌ Not implemented

### 16. Pipeline Phase Validation & Health Checks
- **Issue**: No systematic validation that each phase operates according to web settings
- **Fix**: Add health checks for each phase, validate against web settings
- **Expected Gain**: Proactive detection of configuration issues
- **Status**: ❌ Not implemented

### 17. Weekly Summary Digest
- **Issue**: No weekly aggregation of relevant episodes and trend analysis
- **Fix**: Create Sunday weekly summary digest with topic-based episode reviews
- **Expected Gain**: Weekly insights and trend analysis across topics
- **Status**: ❌ Not implemented

### 18. JSON Output Parsing Improvements
- **File**: `run_full_pipeline_orchestrator.py`
- **Issue**: Could improve multi-line JSON parsing robustness
- **Current State**: Already implements buffering and multi-line parsing (lines 189-280)
- **Note**: Less critical after v1.28 database-first architecture (phases don't depend on JSON)
- **Fix**: Add more robust error handling and edge case coverage
- **Priority**: LOW - Nice to have, already functional
- **Status**: ⚠️ Partially implemented

---

## Summary Statistics

### By Priority:
- **P0 (Critical)**: 0 remaining 🎉
- **P1 (High)**: 0 remaining 🎉
- **P2 (Medium)**: 4 remaining (performance & optimization)
- **P3 (Low)**: 16 remaining (architecture & nice-to-have)

### **Total Remaining**: 20 tasks

### Recommended Next Steps:
1. **P3 Priority**: Remove MD file fallback from digest generation (single source of truth)
2. **P3 Priority**: Database retention and cleanup system (complete implementation)
3. **P2 Priority**: Orchestrator memory management (rolling buffer for stdout_lines)
4. **P2 Priority**: Database connection optimization (connection pooling)

---

## Validation Commands

After completing fixes, run these commands to validate:

```bash
# Environment validation
python3 scripts/doctor.py

# Test suite validation
python3 -m pytest tests/ -v

# RSS feed validation (dynamic API)
curl -s https://podcast.paulrbrown.org/daily-digest.xml | head -20
curl -s https://podcast.paulrbrown.org/daily-digest.xml | grep generator

# Pipeline test
# Manual trigger via GitHub Actions interface
```

---

*All completed tasks (15+ major items) have been documented in `COMPLETED_TASKS_SUMMARY.md`*