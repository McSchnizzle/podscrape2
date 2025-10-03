# RSS Podcast Transcript Digest — Product Brief

**Production Status**: Fully operational v1.52 with 6-phase pipeline, PostgreSQL (Supabase), OpenAI Whisper, and Next.js Web UI.

An automated daily digest system that ingests podcast episodes from RSS feeds, transcribes audio using local OpenAI Whisper with memory-efficient incremental writes, scores content for topic relevancy, generates topic scripts from database-stored instructions, produces MP3s, and publishes via dynamic RSS API.

**Current Version**: v1.52 (October 2025)
**RSS Feed**: https://podcast.paulrbrown.org/daily-digest.xml (Dynamic API)

## What It Does (6-Phase Architecture)
1. **Discovery**: Find new episodes from configured RSS feeds with health monitoring
2. **Audio**: Download/chunk audio; transcribe with OpenAI Whisper (memory-efficient); score with GPT-5-mini
3. **Digest**: Generate topic-based scripts using GPT-5 and database-stored instructions
4. **TTS**: Create MP3s with ElevenLabs using topic-specific voices
5. **Publishing**: Upload to GitHub Releases; update database for dynamic RSS API
6. **Retention**: Automated cleanup of old MP3s, releases, logs, and database records
- **Management**: Next.js Web UI hosted at podcast.paulrbrown.org for configuration and monitoring

## Architecture (Concise)

### Database Design (PostgreSQL via Supabase)
```sql
-- Core Tables
episodes: id, episode_guid, feed_id, title, published_date, duration_seconds, 
          audio_url, transcript_path, scores (JSON), status, failure_count, timestamps

feeds: id, feed_url, title, description, active, 
       consecutive_failures, last_checked, timestamps

digests: id, topic, digest_date, script_path, mp3_path, mp3_title, 
         mp3_summary, episode_ids (JSON), github_url, timestamps
```

**Production Architecture**: PostgreSQL (Supabase) with RLS and professional backups, local OpenAI Whisper with memory-efficient transcription, 6-phase orchestrator with standardized logging, and Next.js Web UI with dynamic RSS API.

**Key Updates** (v1.49-v1.52):
- Dynamic RSS API (no static files) since v1.49
- Memory-efficient transcription with O(1) memory usage (v1.52)
- Database-first architecture (no filesystem fallbacks, v1.52)
- Dedicated retention phase with configurable periods (v1.51)

Key folders: data/ (logs, transcripts - staging only), scripts/ (6 phase scripts), web_ui_hosted/ (Next.js app)

## Web UI (Next.js on Vercel)

Next.js Web UI hosted at podcast.paulrbrown.org provides configuration, monitoring, and operations.

### Capabilities
- **Settings** (Database-backed via `web_settings` table):
  - Content filtering (score_threshold, max_episodes_per_digest)
  - Audio processing (chunk_duration_minutes, transcribe settings)
  - Retention periods (local_mp3_days, github_release_days, logs_days, etc.)
  - Settings are read by the pipeline via `WebConfigManager`
- **Feeds**:
  - List feeds (feed_url, title, active, last_checked, consecutive_failures)
  - Add feed (URL validation, duplicate guard, title autofill via FeedParser)
  - Toggle active; soft delete
  - "Check feed" verifies TLS and audio enclosure reachability (no pipeline run)
  - Latest episode title + published date displayed per RSS feed
- **Topics** (Database-First Architecture):
  - List/edit topics from PostgreSQL `topics` table
  - Edit voice_id, instructions_md (stored in database, no files), description, active
  - All topic configuration in database, no filesystem dependencies (v1.52)
- **Dashboard**:
  - Mirrors key settings from DB
  - Last Run distillation (recent scored episodes with correct feed + qualifying topics; latest digests from DB including episode titles and MP3 durations)
  - Transcribed but not yet digested (accurate feed names; one‑time repair of legacy mis‑associations using transcript headers)
  - Retry failed episodes; Run Publishing / Run Full Pipeline controls
  - Tail endpoint for latest log; we removed separate publishing log creation (noise)

### Notable Architectural Choices (v1.49-v1.52)
- **Dynamic RSS API**: RSS XML generated on-demand from database (no static files, v1.49)
- **Database-First**: All configuration in PostgreSQL, no filesystem fallbacks (v1.52)
- **Memory-Efficient Transcription**: Incremental database writes for O(1) memory usage (v1.52)
- **Immediate MP3 Cleanup**: Local MP3s deleted after GitHub upload (v1.51)
- **6-Phase Pipeline**: Dedicated retention phase for systematic cleanup (v1.51)
- **Row Level Security**: Full RLS enabled on all Supabase tables for security

### Operations
- **Production**: Hosted at https://podcast.paulrbrown.org (Next.js on Vercel)
- **Local Development**: `cd web_ui_hosted && npm run dev` (localhost:3000)
- **UI Tests**: `cd ui-tests && npm install && npx playwright install && npx playwright test`

### Acceptance
- Dashboard reflects latest pipeline status (scored episodes, digests, RSS items, pending/failed episodes)
- Feeds and Topics changes persist and affect the pipeline
- “Check feed” surfaces networking/format issues that would block downloads

## Status & Roadmap

**Current Status**: v1.52 - Production system with 6-phase pipeline, database-first architecture, and dynamic RSS API

**Completed (v1.01-v1.52)**:
- Core 6-phase pipeline (Discovery, Audio, Digest, TTS, Publishing, Retention)
- PostgreSQL database with Row Level Security (RLS)
- Memory-efficient transcription (O(1) memory usage)
- Dynamic RSS API (Next.js route, no static files)
- Database-first architecture (no filesystem fallbacks)
- Next.js Web UI hosted on Vercel
- Automated retention management with configurable periods

**Remaining** (See master-tasklist.md):
- 15 P3 (Low Priority) tasks including:
  - Database connection optimization (connection pooling)
  - Analytics & metrics dashboard
  - Weekly summary digest feature
  - Enhanced monitoring and alerting

1. **Feed Manager** (`feed_manager.py`)
   - Add/remove RSS podcast feeds
   - Parse RSS feeds to discover new episodes
   - Track feed health and failure monitoring

2. **Audio Processor** (`audio_processor.py`)
   - Download podcast audio files from RSS episodes
   - Split audio into 10-minute chunks for processing
   - Manage audio file caching and cleanup

3. **Transcript Generator** (`openai_whisper_transcriber.py`)
   - Transcribe audio chunks using local OpenAI Whisper
   - Memory-efficient mode with incremental database writes (v1.52)
   - O(1) constant memory usage regardless of transcript size
   - Quality validation and error handling

4. **Content Scorer** (integrated in `run_audio.py` since v1.28)
   - Score episodes against all topics using GPT-5-mini
   - Structured JSON output with relevancy scores 0.0-1.0
   - Integrated into Audio phase for efficiency

5. **Script Generator** (`script_generator.py`)
   - Combine high-scoring episodes (≥0.65) per topic
   - Load topic instructions from database `instructions_md` field (v1.52)
   - Database-first architecture (no filesystem fallbacks)
   - Use GPT-5 with 25,000 word limit per script

6. **TTS Generator** (`tts_generator.py`)
   - Convert scripts to MP3 using ElevenLabs API
   - Configurable voice settings per topic
   - Generate titles/summaries using GPT-5-nano

7. **Publisher** (`run_publishing.py`)
   - Upload MP3s to GitHub repository (GitHub Releases)
   - Update database with github_url for dynamic RSS API
   - Delete local MP3s immediately after successful upload

8. **Retention Manager** (`run_retention.py` - v1.51+)
   - Dedicated Phase 6 for all cleanup operations
   - Configurable retention periods via web_settings table
   - Cleanup: GitHub releases, database records, logs, audio cache

9. **Main Orchestrator** (`run_full_pipeline_orchestrator.py`)
   - Coordinate entire 6-phase pipeline
   - Comprehensive logging with phase summaries (v1.52)
   - Support phase-specific execution (e.g., --phase audio)

## Key Features & Requirements

### Content Processing
- **Source**: RSS podcast feeds from PostgreSQL `feeds` table
- **Filtering**: Minimum 3-minute duration, exclude short segments
- **Transcription**: Local OpenAI Whisper with 3-minute audio chunking
- **Memory Efficiency**: Incremental database writes for O(1) memory usage (v1.52)
- **Scoring**: Each episode scored against all topics (0.0-1.0 scale)
- **Threshold**: Only episodes scoring ≥0.65 included in digests
- **Deduplication**: Prevent reprocessing of same episode_guid

### Quality Controls
- **Transcript Validation**: Verify transcript quality and completeness from OpenAI Whisper
- **Failure Handling**: 3-retry limit, mark failed episodes permanently
- **Feed Health**: Flag feeds with 3+ consecutive days of failures
- **Content Limits**: Maximum 25,000 words per script
- **Audio Quality**: Optimize for Bluetooth earbuds (good mobile quality)
- **Chunking Strategy**: Process audio in 3-minute segments for optimal ASR performance
- **Memory Management**: O(1) constant memory usage via incremental database writes (v1.52)

### Automation Features
- **Daily Execution**: Cron job at 6 AM daily
- **Smart Lookback**: Monday 72hrs, other weekdays 24hrs
- **No Content Handling**: Generate "no new episodes today" audio on empty days
- **Manual Override**: Support specific date execution for debugging/catch-up
- **Comprehensive Logging**: File-based logging with minimal console output

### Publishing & Distribution
- **GitHub Integration**: Automated MP3 upload to GitHub Releases with daily tags
- **Dynamic RSS API**: Next.js API route generates RSS 2.0 XML on-demand from database (v1.49)
  - URL: podcast.paulrbrown.org/daily-digest.xml (rewrite to /api/rss/daily-digest)
  - 5-minute edge cache, no static files, database is single source of truth
- **Vercel Hosting**: Next.js app with API routes hosted on Vercel
- **Retention Management**: Dedicated Phase 6 with configurable retention periods (v1.51)
  - Local MP3s: Deleted immediately after GitHub upload
  - GitHub releases: Configurable (default 14 days)
  - Database records: Configurable (default 14 days)
- **Metadata Rich**: Include timestamps, summaries, and topic categorization

## API Integrations

### Audio Processing
- **RSS Feeds**: Standard RSS 2.0 with podcast extensions for episode discovery
- **HTTP Downloads**: Direct audio file downloads from podcast CDNs
- **OpenAI Whisper**: Local cross-platform transcription (no API costs)
- **ffmpeg**: Audio chunking and format conversion

### AI Services
- **OpenAI GPT-5-mini**: Content scoring with Responses API and JSON schema
- **OpenAI GPT-5**: Script generation following topic instructions
- **OpenAI GPT-5-nano**: Title and summary generation

### Audio Services
- **ElevenLabs**: High-quality TTS conversion with voice customization

### Publishing Services
- **GitHub API**: Repository management, file uploads, and release management
- **Vercel**: Next.js app hosting with API routes for dynamic RSS generation

## Configuration Management

### Environment Variables (.env)
```
OPENAI_API_KEY=your-openai-api-key-here
ELEVENLABS_API_KEY=your-elevenlabs-key-here
GITHUB_TOKEN=your-github-token-here
GITHUB_REPOSITORY=your-username/your-repo-name
```

### Configuration (Database-First Architecture, v1.52)
- **PostgreSQL `feeds` table**: RSS podcast feed management
- **PostgreSQL `topics` table**: Topic configuration, voice settings, instructions_md
- **PostgreSQL `web_settings` table**: All system settings including retention periods
- **No filesystem configuration files**: All config in database (digest_instructions/ removed v1.52)

## Success Metrics

### Operational KPIs
- **Uptime**: >99% daily pipeline success rate
- **Processing Speed**: <30 minutes total pipeline execution
- **Content Quality**: Consistent high-quality digest generation
- **Error Recovery**: Graceful handling of API failures and timeouts

### Quality Metrics
- **Transcript Accuracy**: Successful ASR transcription from podcast episodes
- **Scoring Accuracy**: Relevant content properly identified (≥0.65 threshold)
- **Audio Quality**: Clear, professional-sounding TTS output
- **RSS Compliance**: Compatible with all major podcast clients

### User Experience
- **Zero Manual Effort**: Fully automated daily operation
- **Reliable Delivery**: Consistent daily episode availability
- **Topic Relevance**: High-quality, on-topic content curation
- **Easy Management**: Simple RSS feed add/remove process

## Risk Mitigation

### Technical Risks
- **API Dependencies**: Implement retry logic and graceful degradation
- **Rate Limiting**: Respectful API usage with proper delays
- **Storage Constraints**: Automated cleanup and optimization
- **Processing Failures**: Comprehensive error handling and recovery

### Content Risks
- **Quality Control**: AI scoring ensures relevant content inclusion
- **Copyright Compliance**: Transcript-only processing, no audio redistribution
- **Content Availability**: Handle ASR transcription failures gracefully
- **Audio Processing**: Robust handling of various audio formats and quality levels

### Operational Risks
- **Maintenance Burden**: Well-documented, modular architecture
- **Scalability**: SQLite suitable for single-user personal use
- **Backup Strategy**: Git-based configuration and GitHub hosting

## Future Enhancements

### Phase 2 Features (Post-MVP)
- **Music Bed Integration**: Intro/outro music and transitions between topics
- **Advanced Audio Production**: Dynamic audio mixing and production
- **Multi-Voice Support**: Different voices for different content types
- **Enhanced Filtering**: More sophisticated content relevance detection

### Long-term Vision
- **Mobile App**: Dedicated podcast client with advanced features
- **Analytics Dashboard**: Content performance and engagement tracking
- **Social Features**: Sharing key insights and highlights
- **Enterprise Version**: Multi-user support and team features

## Implementation Timeline

**Total Duration**: 16 days across 8 phases
**Testing Strategy**: Comprehensive testing at end of each phase
**Deployment**: Progressive rollout with validation checkpoints

See `completed-phases1-7.md` for completed phases and `tasklist2.md` for the remaining plan (Web UI + automation).

---

**Document Version**: 2.0
**Last Updated**: September 16, 2025
**Status**: Production Operational
