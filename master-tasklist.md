# RSS Podcast Digest System - Remaining Tasks

**Last Updated**: 2025-10-03 (v1.51)
**Note**: All completed tasks have been moved to `COMPLETED_TASKS_SUMMARY.md`

## Overview

This document lists ONLY the remaining tasks that need to be completed. 

**Core Principle**: FAIL FAST, FAIL LOUD - No silent failures, no fallbacks that mask configuration issues.

**Testing Requirement**: For every task, we MUST have a way to test that it actually works.

---

## CRITICAL (P0) - Security & Breaking Issues: 0 REMAINING

**All P0 tasks completed!** 🎉

**Latest Completion (v1.51)**: 7-phase pipeline optimization & publishing bug fix
- Fixed TTS/Publishing directory mismatch
- Established dedicated Phase 6 for retention management
- Removed 221 lines of dead RSS code
- Implemented atomic TTS operations
- Added database state validation methods
- All 10 files modified successfully
- See `COMPLETED_TASKS_SUMMARY.md` Session 16 for details

---

## HIGH (P1) - Core Functionality Issues: 0 REMAINING

**All P1 tasks completed!** 🎉

---

## MEDIUM (P2) - Performance & Optimization: 0 REMAINING 🎉

**All P2 tasks completed!** 🎉

**Latest Completion (v1.52)**: Memory optimization for large transcripts
- Implemented incremental database writes per chunk
- Added `append_transcript_chunk()` and `finalize_transcript()` methods
- Modified OpenAI Whisper transcriber for memory-efficient mode
- Achieved O(1) constant memory usage regardless of transcript size
- See commit 22c1c8e for details

---

## LOW (P3) - Architecture & Nice-to-Have: 15 REMAINING

### 1. Database Connection Optimization
- **Files**: SQLAlchemy usage throughout codebase
- **Issue**: No evidence of connection pooling or prepared statements
- **Fix**: Implement connection pooling and compiled statement caching
- **Expected Gain**: Better database performance and resource usage
- **Priority**: LOW - System performs well currently, optimization not urgent
- **Status**: ❌ Not implemented

### 2. Vercel CLI Integration for RSS Updates
- **Current Issue**: RSS updates require git commits, causing race conditions
- **Proposed Solution**: Use Vercel CLI for direct deployment
- **Benefits**: No race conditions, faster updates, cleaner git history
- **Status**: ❌ Not implemented

### 3. Async/Await Adoption
- **Scope**: Entire codebase
- **Issue**: Synchronous code for I/O-bound operations
- **Fix**: Migrate I/O operations to async/await patterns
- **Expected Gain**: Better concurrency and resource utilization
- **Status**: ❌ Not implemented

### 4. Connection Pooling Implementation
- **Scope**: Database and HTTP connections
- **Issue**: No connection reuse optimization
- **Fix**: Implement connection pools for database and HTTP clients
- **Expected Gain**: Reduced connection overhead
- **Status**: ❌ Not implemented

### 5. Memory-Efficient Streaming
- **Scope**: Large file processing
- **Issue**: Memory usage scales with file size
- **Fix**: Implement streaming for large file operations
- **Expected Gain**: Constant memory usage regardless of file size
- **Status**: ❌ Not implemented

### 6. Voice Characteristics in Recommendations
- **File**: `src/audio/voice_manager.py:112-133`
- **Issue**: Computes voice gender lists but ignores them, assigns first 4 voices
- **Fix**: Map topics to appropriate voice gender categories, persist in topics.json
- **Expected Gain**: Better voice-topic matching, configurable per topic
- **Status**: ❌ Not implemented

### 7. Database Retention and Cleanup System
- **Goal**: Implement automated database cleanup to prevent database bloat
- **Implementation**: Delete episodes/digests based on configurable retention periods
- **Status**: 🔄 Partially implemented - needs completion

### 8. Topic-Specific RSS Feeds
- **Goal**: Replace single `daily-digest.xml` with topic-specific feeds
- **Implementation**: Generate separate RSS feeds for each topic
- **Benefits**: Users can subscribe to individual topics separately
- **Status**: ❌ Not implemented

### 9. Analytics & Metrics Dashboard
- **Goal**: Create comprehensive analytics dashboard for feed processing pipeline
- **Features**: Feed performance metrics, episode status distribution, topic coverage
- **Benefits**: Clear visibility into feed quality and processing efficiency
- **Status**: ❌ Not implemented

### 10. Structured Logging & Monitoring
- **Issue**: Add structured logging throughout, implement log rotation
- **Fix**: Add metrics collection, performance tracking, alerting for failures
- **Status**: ❌ Not implemented

### 11. Code Quality Improvements
- **Issue**: Remove unused imports, consolidate workflow duplication
- **Fix**: Standardize error handling, add pre-commit hooks
- **Status**: ❌ Not implemented

### 12. Testing & Validation
- **Issue**: Fix test environment issues
- **Fix**: Create comprehensive test suite with real RSS feeds
- **Status**: ❌ Not implemented

### 13. Enhanced Dashboard with Recent Run Details
- **Issue**: Dashboard lacks detailed information about recent pipeline run from GitHub logs
- **Fix**: Pull GitHub Action logs and display detailed run information
- **Expected Gain**: Better visibility into pipeline execution
- **Status**: ❌ Not implemented

### 14. Pipeline Phase Validation & Health Checks
- **Issue**: No systematic validation that each phase operates according to web settings
- **Fix**: Add health checks for each phase, validate against web settings
- **Expected Gain**: Proactive detection of configuration issues
- **Status**: ❌ Not implemented

### 15. Weekly Summary Digest
- **Issue**: No weekly aggregation of relevant episodes and trend analysis
- **Fix**: Create Sunday weekly summary digest with topic-based episode reviews
- **Expected Gain**: Weekly insights and trend analysis across topics
- **Status**: ❌ Not implemented

---

## Summary Statistics

### By Priority:
- **P0 (Critical)**: 0 remaining 🎉
- **P1 (High)**: 0 remaining 🎉
- **P2 (Medium)**: 0 remaining 🎉 (v1.52 memory optimization completed!)
- **P3 (Low)**: 15 remaining (architecture & nice-to-have)

### **Total Remaining**: 15 tasks

### Recently Completed (v1.52 - Session 17):
- **Memory Optimization for Large Transcripts** (P2)
  - Incremental database writes per chunk
  - O(1) constant memory usage
  - Files: models.py, openai_whisper_transcriber.py, run_audio.py

- **Remove MD File Fallback** (P3)
  - Database-first architecture enforced
  - Deleted digest_instructions/ directory
  - 59 lines of dead code removed
  - File: script_generator.py

- **Enhanced Logging** (P3)
  - Discovery phase summary with feed grouping
  - Audio phase summary with score breakdown
  - Files: run_discovery.py, run_audio.py

### Recommended Next Steps:
1. **P3 Priority**: Database retention and cleanup system (complete implementation)
2. **P3 Priority**: Database connection optimization (connection pooling - if needed)
3. **P3 Priority**: Enhanced Dashboard with Recent Run Details

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

*All completed tasks (16+ major items across 16 sessions) and intentionally skipped tasks (4 items) have been documented in `COMPLETED_TASKS_SUMMARY.md`*