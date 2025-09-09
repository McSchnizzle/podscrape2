# YouTube Transcript Digest System - Task List & Progress Tracker

## Overview
**Project**: YouTube Transcript Digest System  
**Total Duration**: 16 days across 8 phases  
**Start Date**: September 9, 2025  
**Current Status**: Phase 0 - Project Setup

---

## 📋 Phase Progress Overview

| Phase | Status | Start Date | End Date | Progress | Test Status |
|-------|--------|------------|----------|----------|-------------|
| Phase 0: Project Setup | 🔄 In Progress | Sep 9 | Sep 9 | 75% | ⏳ Pending |
| Phase 1: Foundation & Data Layer | ⏳ Planned | Sep 9 | Sep 10 | 0% | ⏳ Pending |
| Phase 2: Channel Management & Discovery | ⏳ Planned | Sep 11 | Sep 12 | 0% | ⏳ Pending |
| Phase 3: Transcript Processing | ⏳ Planned | Sep 13 | Sep 14 | 0% | ⏳ Pending |
| Phase 4: Content Scoring System | ⏳ Planned | Sep 15 | Sep 16 | 0% | ⏳ Pending |
| Phase 5: Script Generation | ⏳ Planned | Sep 17 | Sep 18 | 0% | ⏳ Pending |
| Phase 6: TTS & Audio Generation | ⏳ Planned | Sep 19 | Sep 20 | 0% | ⏳ Pending |
| Phase 7: Publishing Pipeline | ⏳ Planned | Sep 21 | Sep 22 | 0% | ⏳ Pending |
| Phase 8: Orchestration & Automation | ⏳ Planned | Sep 23 | Sep 24 | 0% | ⏳ Pending |

**Legend**: ⏳ Planned | 🔄 In Progress | ✅ Complete | ❌ Failed | 🧪 Testing

---

## Phase 0: Project Setup
**Goal**: Initialize project documentation and repository structure  
**Duration**: 1 day  
**Status**: 🔄 In Progress

### Tasks
- [x] **Task 0.1**: Delete old PRD.md and create project documentation structure
- [x] **Task 0.2**: Create comprehensive podscrape2-prd.md with full project specification
- [x] **Task 0.3**: Create tasklist.md with phase breakdown and progress tracking
- [ ] **Task 0.4**: Create readme.md with project overview and setup instructions
- [ ] **Task 0.5**: Initialize git repository and connect to GitHub (McSchnizzle/podscrape2)
- [ ] **Task 0.6**: Make initial commit with project documentation

### Testing Criteria
- [ ] All documentation files created and properly formatted
- [ ] Git repository connected to correct GitHub repo
- [ ] Initial commit successful with all documentation files
- [ ] Project structure ready for development

---

## Phase 1: Foundation & Data Layer
**Goal**: Establish core database and configuration management  
**Duration**: 2 days  
**Status**: ⏳ Planned

### Tasks
- [ ] **Task 1.1**: Create SQLite database schema with tables for episodes, channels, digests
- [ ] **Task 1.2**: Build database connection and migration system with proper error handling
- [ ] **Task 1.3**: Create configuration management system (channels.json, topics.json)
- [ ] **Task 1.4**: Set up comprehensive logging infrastructure and error handling framework
- [ ] **Task 1.5**: Create directory structure (transcripts/, completed-tts/, scripts/, logs/, database/)

### Testing Criteria
- [ ] Database schema created successfully with all required tables and indexes
- [ ] Database connection pool working with proper error handling
- [ ] Configuration files load and validate correctly
- [ ] Logging system captures all events to files with appropriate levels
- [ ] Directory structure created with proper permissions
- [ ] **Test Script**: `test_phase1.py` - Database CRUD operations, config loading, logging

---

## Phase 2: Channel Management & Discovery
**Goal**: YouTube channel management and video discovery  
**Duration**: 2 days  
**Status**: ⏳ Planned

### Tasks
- [ ] **Task 2.1**: Build YouTube channel ID resolution from URLs/names using youtube-dl or API
- [ ] **Task 2.2**: Create channel management CLI (add/remove/list channels) with validation
- [ ] **Task 2.3**: Implement video discovery for channels with filtering (duration >3min)
- [ ] **Task 2.4**: Add channel health monitoring and failure tracking system
- [ ] **Task 2.5**: Test with 2-3 sample channels and validate video discovery

### Testing Criteria
- [ ] Channel ID resolution works for various URL formats and channel names
- [ ] CLI commands function correctly for all channel management operations
- [ ] Video discovery filters correctly by duration and excludes shorts
- [ ] Channel health monitoring detects and tracks failures appropriately
- [ ] Sample channels added successfully with video discovery working
- [ ] **Test Script**: `test_phase2.py` - Channel resolution, CLI operations, video discovery

---

## Phase 3: Transcript Processing
**Goal**: Reliable transcript fetching and storage  
**Duration**: 2 days  
**Status**: ⏳ Planned

### Tasks
- [ ] **Task 3.1**: Implement youtube-transcript-api integration with error handling
- [ ] **Task 3.2**: Add retry logic (3 attempts) and comprehensive failure tracking
- [ ] **Task 3.3**: Create transcript storage system with unique filenames and database references
- [ ] **Task 3.4**: Build transcript quality validation and content verification
- [ ] **Task 3.5**: Test transcript fetching pipeline end-to-end with real videos

### Testing Criteria
- [ ] Transcript API integration successfully extracts transcripts from test videos
- [ ] Retry logic properly handles failures and marks episodes appropriately after 3 attempts
- [ ] Transcript files stored with correct naming convention and database references
- [ ] Quality validation identifies good vs poor quality transcripts
- [ ] End-to-end pipeline processes sample videos from setup to database storage
- [ ] **Test Script**: `test_phase3.py` - Transcript extraction, retry logic, storage validation

---

## Phase 4: Content Scoring System
**Goal**: GPT-5-mini powered relevancy scoring  
**Duration**: 2 days  
**Status**: ⏳ Planned

### Tasks
- [ ] **Task 4.1**: Implement GPT-5 Responses API integration following gpt5-implementation-learnings.md
- [ ] **Task 4.2**: Create JSON schema for structured topic scoring (0.0-1.0 scale)
- [ ] **Task 4.3**: Build batch scoring system for processing efficiency
- [ ] **Task 4.4**: Add score storage and retrieval system in database JSON fields
- [ ] **Task 4.5**: Test scoring accuracy with sample transcripts across all topics

### Testing Criteria
- [ ] GPT-5-mini Responses API correctly configured and returning valid responses
- [ ] JSON schema validation ensures structured scoring output format
- [ ] Batch processing handles multiple episodes efficiently without rate limit issues
- [ ] Scores properly stored in database and retrievable for query operations
- [ ] Scoring accuracy validated against manual review of sample transcripts
- [ ] **Test Script**: `test_phase4.py` - API integration, scoring accuracy, batch processing

---

## Phase 5: Script Generation
**Goal**: Topic-based script generation using GPT-5  
**Duration**: 2 days  
**Status**: ⏳ Planned

### Tasks
- [ ] **Task 5.1**: Load and parse topic instructions from digest_instructions/ directory
- [ ] **Task 5.2**: Implement episode filtering by score threshold (≥0.65) with topic grouping
- [ ] **Task 5.3**: Build script generation using GPT-5 with 25K word limit enforcement
- [ ] **Task 5.4**: Add "no content" day handling with appropriate messaging
- [ ] **Task 5.5**: Test with real topic instructions and scored episodes for quality validation

### Testing Criteria
- [ ] Topic instructions load correctly and are properly formatted for GPT-5 prompts
- [ ] Episode filtering accurately selects episodes meeting score threshold per topic
- [ ] Script generation produces coherent, topic-focused content within word limits
- [ ] "No content" scenarios handled gracefully with appropriate default messaging
- [ ] Generated scripts meet quality standards and follow topic instruction guidelines
- [ ] **Test Script**: `test_phase5.py` - Topic loading, filtering, script generation quality

---

## Phase 6: TTS & Audio Generation
**Goal**: Convert scripts to podcast-quality audio  
**Duration**: 2 days  
**Status**: ⏳ Planned

### Tasks
- [ ] **Task 6.1**: Integrate ElevenLabs API for high-quality TTS generation
- [ ] **Task 6.2**: Implement voice configuration per topic with settings management
- [ ] **Task 6.3**: Generate episode titles and summaries using GPT-5-nano
- [ ] **Task 6.4**: Add audio file naming with timestamps and topic identification
- [ ] **Task 6.5**: Future-proof architecture for music bed integration with existing assets

### Testing Criteria
- [ ] ElevenLabs API integration produces clear, natural-sounding audio output
- [ ] Voice configuration system allows per-topic voice customization
- [ ] GPT-5-nano generates appropriate titles and summaries for episodes
- [ ] Audio files created with correct naming convention and timestamp information
- [ ] Audio quality suitable for mobile/Bluetooth playback (good bitrate and clarity)
- [ ] **Test Script**: `test_phase6.py` - TTS generation, voice config, audio quality validation

---

## Phase 7: Publishing Pipeline
**Goal**: GitHub and RSS feed management  
**Duration**: 2 days  
**Status**: ⏳ Planned

### Tasks
- [ ] **Task 7.1**: Build GitHub repository upload system with release management
- [ ] **Task 7.2**: Create RSS XML generation and updating with proper podcast metadata
- [ ] **Task 7.3**: Implement file retention system (7-day local, 14-day GitHub cleanup)
- [ ] **Task 7.4**: Test RSS feed validation and podcast client compatibility
- [ ] **Task 7.5**: Integrate with Vercel hosting for podcast.paulrbrown.org delivery

### Testing Criteria
- [ ] GitHub uploads successful with proper release creation and file management
- [ ] RSS XML validates against RSS 2.0 and podcast specification standards
- [ ] File retention system correctly removes old files according to policy
- [ ] RSS feed loads properly in major podcast clients (Apple Podcasts, Spotify, etc.)
- [ ] Vercel integration serves RSS feed correctly at podcast.paulrbrown.org/daily-digest2.xml
- [ ] **Test Script**: `test_phase7.py` - GitHub uploads, RSS validation, retention cleanup

---

## Phase 8: Orchestration & Automation
**Goal**: Complete daily automation pipeline  
**Duration**: 2 days  
**Status**: ⏳ Planned

### Tasks
- [ ] **Task 8.1**: Build main orchestrator with date logic (Monday 72hr vs 24hr lookback)
- [ ] **Task 8.2**: Add manual trigger support for specific dates and catch-up processing
- [ ] **Task 8.3**: Implement comprehensive error handling and recovery mechanisms
- [ ] **Task 8.4**: Create cron job setup and documentation for daily automation
- [ ] **Task 8.5**: End-to-end testing with real YouTube channels and full pipeline

### Testing Criteria
- [ ] Orchestrator correctly handles different lookback periods based on day of week
- [ ] Manual trigger allows processing of specific dates for debugging and catch-up
- [ ] Error handling gracefully manages API failures, rate limits, and edge cases
- [ ] Cron job setup documented and tested for reliable daily execution
- [ ] Full end-to-end pipeline processes real channels through to RSS feed publication
- [ ] **Test Script**: `test_phase8.py` - Full pipeline integration, error scenarios, automation

---

## 🧪 Testing Strategy

### Phase Testing Requirements
Each phase must include:
1. **Unit Tests**: Core functionality validation
2. **Integration Tests**: Component interaction validation  
3. **End-to-End Tests**: Complete workflow validation
4. **Performance Tests**: Speed and resource usage validation
5. **Error Handling Tests**: Failure scenario validation

### Success Criteria
- All tests pass with >95% reliability
- Performance meets specified requirements
- Error handling gracefully manages failure scenarios
- Integration points work correctly
- User can easily validate progress and direction

### Test Execution
```bash
# Run phase-specific tests
python test_phase1.py
python test_phase2.py
# ... etc

# Run full integration tests
python test_integration.py

# Run performance validation
python test_performance.py
```

---

## 📝 Progress Notes

### Phase 0 - Project Setup (Sep 9, 2025)
- ✅ Deleted old PRD.md successfully
- ✅ Created comprehensive podscrape2-prd.md with full project specification
- ✅ Created tasklist.md with detailed phase breakdown and progress tracking
- 🔄 Working on readme.md creation
- ⏳ Git repository initialization pending
- ⏳ Initial commit pending

### Future Phase Notes
*Notes will be added as phases are completed...*

---

**Last Updated**: September 9, 2025  
**Next Milestone**: Complete Phase 0 and begin Phase 1 Foundation & Data Layer