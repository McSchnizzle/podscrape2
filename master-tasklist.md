# RSS Podcast Digest System - Remaining Tasks

**Last Updated**: 2024-09-30 (v1.30)  
**Note**: All completed tasks have been moved to `COMPLETED_TASKS_SUMMARY.md`

## Overview

This document lists ONLY the remaining tasks that need to be completed. 

**Core Principle**: FAIL FAST, FAIL LOUD - No silent failures, no fallbacks that mask configuration issues.

**Testing Requirement**: For every task, we MUST have a way to test that it actually works.

---

## CRITICAL (P0) - Security & Breaking Issues: 1 ACTIVE

### 1. RSS Publishing Reliability & Performance Fix (IN PROGRESS)
- **Files**: `.github/workflows/validated-full-pipeline.yml`, `web_ui_hosted/app/api/rss/daily-digest/route.ts`, `scripts/run_publishing.py`
- **Issue**: Validated full pipeline creates GitHub releases but RSS feed never updates on podcast.paulrbrown.org
  - Root cause: Python script's git operations fail silently in subprocess
  - Current workaround: Run publishing-only workflow manually after full pipeline
  - Secondary issue: RSS updates require 2-4 minute Vercel full redeployments
- **Fix (Two Phases)**:
  - **Phase 1 (Quick Fix)**: Update validated-full-pipeline.yml to handle git operations explicitly in workflow (like publishing-only.yml does)
    - Copy proven git add/commit/push logic from publishing-only.yml
    - Update sleep timer to 120s for Vercel deployment
    - Add RSS verification step
  - **Phase 2 (Better Solution)**: Create dynamic Next.js API route for RSS feed
    - Create `/api/rss/daily-digest/route.ts` that queries Supabase database directly
    - Configure Vercel rewrite: `/daily-digest.xml` → `/api/rss/daily-digest`
    - Add Vercel edge caching (5 min cache, stale-while-revalidate)
    - Remove RSS file generation from publishing pipeline
    - Remove git commit/push operations for RSS files
    - Remove Vercel deployment wait times
- **Benefits**:
  - Immediate: Validated full pipeline works reliably without manual intervention
  - Long-term: Instant RSS updates (no deployment), always accurate (reads database), fast for users (20-50ms edge cache)
- **Priority**: CRITICAL - Core pipeline functionality broken
- **Status**: 🔄 In Progress

---

## HIGH (P1) - Core Functionality Issues: 2 REMAINING

### 1. --log Parameter in Orchestrator
- **File**: `run_full_pipeline_orchestrator.py`
- **Issue**: Pass log_file parameter to setup_phase_logging
- **Fix**: Remove redundant self.log_file assignment, test Web UI log file specification
- **Priority**: LOW - Feature enhancement
- **Status**: ❌ Not fixed

### 2. Missing Secrets in Workflow
- **Issue**: Use standard GITHUB_TOKEN instead of requiring GH_TOKEN
- **Fix**: Remove duplicate secret requirements, update secret validation
- **Priority**: LOW - Simplification
- **Status**: ❌ Not fixed

### 3. Retention Manager Initialization
- **File**: `src/publishing/retention_manager.py`
- **Issue**: Defer retention manager initialization until needed
- **Fix**: Add try/catch with graceful degradation, make GitHub CLI optional
- **Priority**: MEDIUM - Error handling
- **Status**: ❌ Not fixed

### 4. Parallel Audio Processing Robustness (P1 - URGENT)
- **Files**: `scripts/run_audio.py`, `src/database/models.py`
- **Issue**: Parallel processing fails with stuck 'processing' episodes and misleading worker counts
- **Fixes Implemented**:
  - Added automatic recovery for stuck 'processing' episodes at startup
  - Fixed worker count reporting to show actual workers used
  - Added periodic timeout protection during processing
  - Improved empty queue handling with helpful suggestions
  - Added better database connection management
- **Priority**: HIGH - Core functionality fix
- **Status**: ✅ Fixed (v1.35)

---

## MEDIUM (P2) - Performance & Optimization: 6 REMAINING

### 1. Batch API Requests
- **Files**: Audio generation, voice fetching, content scoring loops
- **Issue**: Individual API calls in loops instead of batching
- **Fix**: Implement request batching or connection pooling
- **Expected Gain**: Reduced API overhead and improved throughput
- **Status**: ❌ Not implemented

### 2. Remove Synchronous Sleep Calls
- **Files**: `src/audio/audio_generator.py:119,273` and others
- **Issue**: `time.sleep()` calls block entire process
- **Fix**: Replace with async/await patterns or token bucket rate limiting
- **Expected Gain**: Better resource utilization and responsiveness
- **Status**: ❌ Not implemented

### 3. Orchestrator Memory Management
- **File**: `run_full_pipeline_orchestrator.py`
- **Issue**: Implement rolling buffer for stdout_lines (keep last 100-200 lines)
- **Fix**: Stream large outputs directly to log file, add memory usage monitoring
- **Expected Gain**: Reduced memory usage for large outputs
- **Status**: ❌ Not implemented

### 4. Database Connection Optimization
- **Files**: SQLAlchemy usage throughout codebase
- **Issue**: No evidence of connection pooling or prepared statements
- **Fix**: Implement connection pooling and compiled statement caching
- **Expected Gain**: Better database performance and resource usage
- **Status**: ❌ Not implemented

### 5. Memory Optimization for Large Transcripts
- **Files**: Transcript processing code
- **Issue**: Large files read entirely into memory
- **Fix**: Implement streaming processing for large files
- **Expected Gain**: Reduced memory footprint for large transcripts
- **Status**: ❌ Not implemented

### 6. Remove Unnecessary Caching
- **Issue**: Remove Whisper cache from publishing workflow
- **Fix**: Audit other caches for actual usage, document what caches are needed
- **Expected Gain**: Cleaner workflows, less confusion
- **Status**: ❌ Not implemented

---

## LOW (P3) - Architecture & Nice-to-Have: 17 REMAINING

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

### 6. Simplify MP3 Storage - Remove 'current' Subdirectory
- **Files**: `src/audio/audio_manager.py`, `src/audio/complete_audio_processor.py`, `src/publishing/github_publisher.py`
- **Issue**: Unnecessary `data/completed-tts/current/` subdirectory adds complexity
- **Proposed Simplification**:
  - Store all MP3s directly in `data/completed-tts/` (no subdirectories)
  - Remove AudioManager.organize_audio_files() calls
  - Update GitHub publisher to look in base `completed-tts/` directory
- **Benefits**: Simpler architecture, fewer code paths, easier to maintain
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
- **P0 (Critical)**: 1 in progress (RSS publishing reliability)
- **P1 (High)**: 2 remaining (core functionality)
- **P2 (Medium)**: 6 remaining (performance & optimization)
- **P3 (Low)**: 18 remaining (architecture & nice-to-have)

### **Total Remaining**: 27 tasks (1 P0 in progress + 26 other tasks)

### **Session 11 Completed (v1.30)**:
- ✅ Fixed discovery phase duplicate episode creation bug (P0)
- ✅ Converted all timestamps from UTC to Pacific time (P0)
- ✅ Verified RSS generation timing fix (P0)
- ✅ Fixed publishing workflow parameter handling (P1)
- ✅ Fixed resource leak in audio processing with context managers (P1)
- ✅ Implemented parallel audio phase processing with smart backfill (P2)

### **Session 12 Completed (v1.35)**:
- ✅ Fixed parallel audio processing robustness issues (P1)
  - Added automatic recovery for stuck 'processing' episodes
  - Fixed misleading worker count reporting
  - Added periodic timeout protection
  - Improved empty queue handling
  - Enhanced database connection management

### **Session 13 In Progress (v1.48+)**:
- 🔄 RSS Publishing Reliability & Performance Fix (P0)
  - **Phase 1**: Quick fix for validated-full-pipeline.yml git operations
  - **Phase 2**: Dynamic RSS API route to eliminate deployment delays
  - Eliminates 2-4 minute deployment waits, provides instant updates
  - RSS always reflects current database state with edge caching

### Recommended Next Steps:
1. **P0 Priority (IN PROGRESS)**: RSS publishing reliability fix
2. **P1 Priority**: Fix --log parameter and workflow secret handling
3. **P2 Priority**: Batch API requests for better throughput

---

## Validation Commands

After completing fixes, run these commands to validate:

```bash
# Environment validation
python3 scripts/doctor.py

# Test suite validation
python3 -m pytest tests/ -v

# RSS feed validation
python3 src/publishing/rss_generator.py --validate web_ui_hosted/public/daily-digest.xml

# Pipeline test
# Manual trigger via GitHub Actions interface
```

---

*All completed tasks (15+ major items) have been documented in `COMPLETED_TASKS_SUMMARY.md`*