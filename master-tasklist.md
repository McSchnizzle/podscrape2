# RSS Podcast Digest System - Master Task List

## Overview

This document consolidates all outstanding tasks, bugs, and improvements for the RSS podcast digest system. Tasks are prioritized by urgency and impact.

**Core Principle**: FAIL FAST, FAIL LOUD - No silent failures, no fallbacks that mask configuration issues.

## CRITICAL (P0) - Security & Breaking Issues

### 1. Database Transaction Connection Bug ✅ FIXED
- **File**: `src/utils/error_handling.py:271-272`
- **Issue**: Unbound `conn` variable in `database_transaction` context manager
- **Status**: ✅ **FIXED** - Added `conn = None` initialization and `if conn:` check before rollback

### 2. Limit Check Ignores Zero
- **Files**: `scripts/run_tts.py:151`, `scripts/run_scoring.py:154`, `scripts/run_audio.py:169`
- **Issue**: `if self.limit:` condition treats `--limit 0` as falsy, processing all items instead of none
- **Evidence**: Zero is falsy in Python, so `--limit 0` doesn't slice the list
- **Fix**: Change to `if self.limit is not None:` before slicing
- **Status**: ❌ Not fixed

### 3. Voice Fetch Failure Cached Permanently
- **File**: `src/audio/voice_manager.py:90-93`
- **Issue**: Failed voice fetches set `_available_voices = []` permanently until refresh
- **Evidence**: Network errors cause empty list to be cached, preventing future fetches
- **Fix**: Set `_available_voices = None` on failure or implement retry mechanism
- **Status**: ❌ Not fixed

### 4. Command Injection Vulnerability in Publishing Workflow
- **File**: `.github/workflows/phase-publishing.yml`
- **Issue**: `eval "$COMMAND"` with direct command execution vulnerability
- **Fix**: Replace with direct command execution, pass arguments as array elements
- **Status**: ❌ Not fixed

### 5. JSON Output Parsing in Orchestrator
- **File**: `run_full_pipeline_orchestrator.py`
- **Issue**: Robust JSON parsing that handles multi-line output needed
- **Fix**: Accumulate potential JSON lines and parse complete objects
- **Status**: ❌ Not fixed

### 6. Git Push Race Conditions ✅ FIXED
- **Files**: `.github/workflows/validated-full-pipeline.yml`, `.github/workflows/publishing-only.yml`, `scripts/run_publishing.py`
- **Issue**: Concurrent workflows causing "fetch first" errors
- **Status**: ✅ **FIXED** - Added `git pull --rebase` before all pushes

### 7. Publishing Workflow File Copy Error ✅ FIXED
- **File**: `.github/workflows/publishing-only.yml`
- **Issue**: Trying to copy non-existent `data/rss/daily-digest.xml`
- **Status**: ✅ **FIXED** - Updated to use correct `web_ui_hosted/public/` path

### 8. Google Account Authentication Security
- **Issue**: Web UI needs authentication restricted to brownpr0@gmail.com only
- **Fix**: Implement Google OAuth with account restriction
- **Status**: ❌ Not implemented

## HIGH (P1) - Core Functionality Issues

### 1. Global Logger Access Vulnerability
- **File**: `src/utils/error_handling.py:236`
- **Issue**: `logger = globals()['logger']` throws KeyError if 'logger' not in scope
- **Fix**: Use `logger = logging.getLogger(__name__)` instead
- **Status**: ❌ Not fixed

### 2. File Encoding Inconsistency
- **File**: `tests/test_phase1.py:270`
- **Issue**: File opened without encoding while most files use UTF-8
- **Fix**: Add `encoding='utf-8'` to all file operations
- **Status**: ❌ Not fixed

### 3. Missing Subprocess Exception Handling
- **Files**: Multiple files using `subprocess.run()`
- **Issue**: Inconsistent handling of `FileNotFoundError` when external tools missing
- **Fix**: Add FileNotFoundError handling with clear error messages
- **Status**: ❌ Not fixed

### 4. Resource Leak in Audio Processing
- **File**: `src/podcast/audio_processor.py:509`
- **Issue**: Session only closed in destructor, not in exception paths
- **Fix**: Add explicit resource cleanup or use context managers
- **Status**: ❌ Not fixed

### 5. --log Parameter in Orchestrator
- **File**: `run_full_pipeline_orchestrator.py`
- **Issue**: Pass log_file parameter to setup_phase_logging
- **Fix**: Remove redundant self.log_file assignment, test Web UI log file specification
- **Status**: ❌ Not fixed

### 6. Publishing Workflow Parameter Handling
- **File**: `.github/workflows/phase-publishing.yml`
- **Issue**: Remove hardcoded `--days-back "30"` in publishing workflow
- **Fix**: Pass DAYS_BACK workflow input to publishing script
- **Status**: ❌ Not fixed

### 7. Missing Secrets in Workflow
- **Issue**: Use standard GITHUB_TOKEN instead of requiring GH_TOKEN
- **Fix**: Remove duplicate secret requirements, update secret validation
- **Status**: ❌ Not fixed

### 8. Retention Manager Initialization
- **File**: `src/publishing/retention_manager.py`
- **Issue**: Defer retention manager initialization until needed
- **Fix**: Add try/catch with graceful degradation, make GitHub CLI optional
- **Status**: ❌ Not fixed

## MEDIUM (P2) - Performance & Optimization

### 1. Parallelize TTS Audio Generation
- **File**: `scripts/run_tts.py` (TTSRunner.generate_audio)
- **Issue**: Sequential audio generation creates bottleneck
- **Fix**: Use `concurrent.futures.ThreadPoolExecutor` respecting API rate limits
- **Expected Gain**: 40-70% time reduction for multiple digests
- **Status**: ❌ Not implemented

### 2. Cache Configuration Data
- **File**: `src/config/config_manager.py:41-55`
- **Issue**: Repeated JSON parsing on every configuration access
- **Fix**: Cache with file modification time checks and invalidation
- **Expected Gain**: Eliminate repeated disk I/O, faster configuration access
- **Status**: ❌ Not implemented

### 3. Batch API Requests
- **Files**: Audio generation, voice fetching, content scoring loops
- **Issue**: Individual API calls in loops instead of batching
- **Fix**: Implement request batching or connection pooling
- **Expected Gain**: Reduced API overhead and improved throughput
- **Status**: ❌ Not implemented

### 4. Remove Synchronous Sleep Calls
- **Files**: `src/audio/audio_generator.py:119,273` and others
- **Issue**: `time.sleep()` calls block entire process
- **Fix**: Replace with async/await patterns or token bucket rate limiting
- **Expected Gain**: Better resource utilization and responsiveness
- **Status**: ❌ Not implemented

### 5. Orchestrator Memory Management
- **File**: `run_full_pipeline_orchestrator.py`
- **Issue**: Implement rolling buffer for stdout_lines (keep last 100-200 lines)
- **Fix**: Stream large outputs directly to log file, add memory usage monitoring
- **Status**: ❌ Not implemented

### 6. Database Connection Optimization
- **Files**: SQLAlchemy usage throughout codebase
- **Issue**: No evidence of connection pooling or prepared statements
- **Fix**: Implement connection pooling and compiled statement caching
- **Expected Gain**: Better database performance and resource usage
- **Status**: ❌ Not implemented

### 7. Memory Optimization for Large Transcripts
- **Files**: Transcript processing code
- **Issue**: Large files read entirely into memory
- **Fix**: Implement streaming processing for large files
- **Expected Gain**: Reduced memory footprint for large transcripts
- **Status**: ❌ Not implemented

### 8. Remove Unnecessary Caching
- **Issue**: Remove Whisper cache from publishing workflow
- **Fix**: Audit other caches for actual usage, document what caches are needed
- **Status**: ❌ Not implemented

## LOW (P3) - Architecture & Nice-to-Have

### 1. Vercel CLI Integration for RSS Updates
- **Current Issue**: RSS updates require git commits, causing race conditions
- **Proposed Solution**: Use Vercel CLI for direct deployment
- **Implementation**:
  - Install Vercel CLI in GitHub Actions workflows
  - Use `vercel deploy --prod` to update just the RSS file
  - Keep git commits only for actual code changes
  - RSS updates happen directly via Vercel API
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

### 6. Database Retention and Cleanup System
- **Status**: ⚠️ IN PROGRESS (from move-online2.md Phase 6.5)
- **Goal**: Implement automated database cleanup to prevent database bloat
- **Implementation**: Delete episodes/digests based on configurable retention periods
- **Remaining Work**: Complete `_cleanup_database_records()` implementation
- **Status**: 🔄 Partially implemented

### 7. Topic-Specific RSS Feeds
- **Goal**: Replace single `daily-digest.xml` with topic-specific feeds
- **Implementation**: Generate separate RSS feeds for each topic
- **Benefits**: Users can subscribe to individual topics separately
- **Status**: ❌ Not implemented

### 8. Analytics & Metrics Dashboard
- **Goal**: Create comprehensive analytics dashboard for feed processing pipeline
- **Features**: Feed performance metrics, episode status distribution, topic coverage
- **Benefits**: Clear visibility into feed quality and processing efficiency
- **Status**: ❌ Not implemented

### 9. Structured Logging & Monitoring
- **Issue**: Add structured logging throughout, implement log rotation
- **Fix**: Add metrics collection, performance tracking, alerting for failures
- **Status**: ❌ Not implemented

### 10. Code Quality Improvements
- **Issue**: Remove unused imports, consolidate workflow duplication
- **Fix**: Standardize error handling, add pre-commit hooks
- **Status**: ❌ Not implemented

### 11. Testing & Validation
- **Issue**: Add orchestrator tests, fix test environment issues
- **Fix**: Create comprehensive test suite with real RSS feeds
- **Status**: ❌ Not implemented

### 12. Enhanced Dashboard with Recent Run Details
- **Issue**: Dashboard lacks detailed information about the most recent pipeline run from GitHub logs
- **Fix**: Pull GitHub Action logs and display detailed run information, phase-by-phase status, timing, and errors
- **Expected Gain**: Better visibility into pipeline execution and faster troubleshooting
- **Status**: ❌ Not implemented

### 13. Pipeline Phase Validation & Health Checks
- **Issue**: No systematic validation that each phase operates according to web settings and configuration
- **Fix**: Add health checks for each phase, validate against web settings, report configuration mismatches
- **Expected Gain**: Proactive detection of configuration issues and phase failures
- **Status**: ❌ Not implemented

### 14. Retention Policy Review & Implementation
- **Issue**: Episode and digest deletion policies need review and proper implementation
- **Fix**: Review current retention logic, implement configurable retention periods, add automated cleanup scheduling
- **Expected Gain**: Prevent database bloat and ensure predictable data lifecycle management
- **Status**: ❌ Not implemented

### 15. Enhanced Episode Pipeline Visibility
- **Issue**: Dashboard lacks visibility into episode processing stages
- **Fix**: Add metrics for discovered but unprocessed episodes, audio-processed but unscored episodes, scored but undigested episodes
- **Expected Gain**: Clear pipeline bottleneck identification and processing queue visibility
- **Status**: ❌ Not implemented

### 16. Feed Performance Analytics
- **Issue**: No visibility into which feeds generate the most irrelevant content or update frequency patterns
- **Fix**: Add metrics showing 'not relevant' episodes per feed, update frequency analysis, feed quality scoring
- **Expected Gain**: Data-driven feed management and quality optimization
- **Status**: ❌ Not implemented

### 17. Weekly Summary Digest
- **Issue**: No weekly aggregation of relevant episodes and trend analysis
- **Fix**: Create Sunday weekly summary digest with topic-based episode reviews and trend identification
- **Expected Gain**: Weekly insights and trend analysis across topics
- **Status**: ❌ Not implemented

### 18. TTS Script Warming Phase
- **Issue**: Generated digest scripts are generic and lack personalization for TTS output
- **Fix**: Add warming phase between digest and TTS that customizes scripts with specific TTS directions for more natural audio
- **Expected Gain**: Less robotic, more personalized audio output with better TTS guidance
- **Status**: ❌ Not implemented

## Completed Sessions (Historical)

- **Session 1**: ✅ COMPLETE (4/4 critical production issues resolved)
- **Session 2**: ✅ COMPLETE (3/3 high-priority testing infrastructure issues resolved)
- **Session 3**: ✅ COMPLETE (3/3 medium-priority code quality & reliability issues resolved)
- **Session 4**: ✅ COMPLETE (4/4 testing improvements & documentation tasks resolved)
- **Session 5**: ✅ COMPLETE (3/3 test consolidation and cleanup tasks resolved)

## Progress Summary

### Immediate Fixes Completed Today
- ✅ **Database transaction connection bug** - Fixed unbound variable issue
- ✅ **Git push race conditions** - Added `git pull --rebase` to all workflows
- ✅ **Publishing workflow file copy error** - Fixed obsolete file path references
- ✅ **Limit check ignores zero** - Fixed `if self.limit:` to `if self.limit is not None:` in 3 script files
- ✅ **Voice fetch failure caching** - Fixed permanent cache failure by setting `None` instead of empty list
- ✅ **Command injection vulnerability** - Already resolved (eval pattern not found in current code)
- ✅ **JSON parsing in orchestrator** - Improved multi-line JSON parsing with buffer accumulation
- ✅ **Google OAuth authentication** - Implemented Google OAuth with brownpr0@gmail.com restriction

### Critical Issues Remaining (P0): 0 items
🎉 **ALL P0 CRITICAL ISSUES RESOLVED**

### Next Priority Actions
1. Address P1 High priority issues (Global logger access, file encoding, subprocess exceptions)
2. Implement P2 performance optimizations (TTS parallelization, configuration caching)
3. Work on P3 feature enhancements (dashboard improvements, analytics, weekly summaries)

## Validation Commands

After completing fixes, run these commands to validate:

```bash
# Environment validation
python3 scripts/doctor.py

# Test suite validation
python3 -m pytest tests/ -v

# RSS feed validation
python3 src/publishing/rss_generator.py --validate web_ui_hosted/public/daily-digest.xml

# Pipeline test (check workflows don't fail with race conditions)
# Manual trigger via GitHub Actions interface
```

---

*Last Updated: 2025-01-26*
*Consolidated from hardening-tasklist.md, move-online2.md, and second-hardening.md*