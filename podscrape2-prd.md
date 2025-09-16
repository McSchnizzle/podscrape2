# RSS Podcast Transcript Digest — Product Brief

**Production Status**: Fully operational automated daily digest system with PostgreSQL database, OpenAI Whisper transcription, and comprehensive orchestrator.

An automated daily digest system that ingests podcast episodes from RSS feeds, transcribes audio using local OpenAI Whisper, scores content for topic relevancy, generates topic scripts, produces MP3s, and publishes a canonical RSS feed.

Canonical RSS: https://podcast.paulrbrown.org/daily-digest.xml

## What It Does
- **Discovery**: Find new episodes from configured RSS feeds with health monitoring
- **Processing**: Download and chunk audio; transcribe with local OpenAI Whisper (cross-platform)
- **Intelligence**: Score against topics using GPT-5-mini; generate digest scripts with GPT-5
- **Production**: Create MP3s with ElevenLabs TTS using topic-specific voices
- **Publishing**: Deploy via GitHub Releases (MP3s) and Vercel (RSS feed)
- **Management**: Optional Web UI for configuration and monitoring

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

**Production Architecture**: PostgreSQL (Supabase) with professional backups, local OpenAI Whisper transcription, comprehensive orchestrator with standardized logging and retention management.

Key folders: data/ (logs, transcripts, scripts, completed-tts), scripts/ (phase scripts), public/ (daily-digest.xml)

## Web UI (Phases A–C)

An optional local Web UI (Flask on 127.0.0.1:5001) provides configuration and operations while keeping the CLI pipelines unchanged when the UI is not running.

### Capabilities
- **Settings** (DB‑backed via `web_settings` + `WebConfigManager`):
  - content_filtering.score_threshold
  - content_filtering.max_episodes_per_digest
  - audio_processing.chunk_duration_minutes
  - audio_processing.transcribe_all_chunks / max_chunks_per_episode
  - Settings are read by the pipeline (scorer, script generator, transcriber/audio)
- **Feeds**:
  - List feeds (feed_url, title, active, last_checked, consecutive_failures)
  - Add feed (URL validation, duplicate guard, title autofill via FeedParser)
  - Toggle active; soft delete
  - “Check feed” verifies TLS and audio enclosure reachability (no pipeline run)
  - Latest episode title + published date displayed per RSS feed
- **Topics**:
  - List/edit topics from `config/topics.json`
  - Edit voice_id, instruction_file (upload/validate under `digest_instructions/`), description, active
  - Persist via `ConfigManager.save_topics()`; ContentScorer uses `ConfigManager` with `WebConfigManager` override
- **Dashboard**:
  - Mirrors key settings from DB
  - Last Run distillation (recent scored episodes with correct feed + qualifying topics; latest digests from DB including episode titles and MP3 durations)
  - Transcribed but not yet digested (accurate feed names; one‑time repair of legacy mis‑associations using transcript headers)
  - Retry failed episodes; Run Publishing / Run Full Pipeline controls
  - Tail endpoint for latest log; we removed separate publishing log creation (noise)

### Notable Choices
- The UI does not trigger GPT/TTS except for manual “Run Full Pipeline”.
- All settings live in SQLite (web_settings); `ConfigManager` reads `score_threshold` from WebConfig when present.
- ContentScorer now loads topics and threshold via `ConfigManager` (with WebConfig override) to align with the Web UI.
- Episodes used in digests are marked `digested` after daily digests complete to prevent reuse. A one‑time repair aligns legacy entries.

### Operations
- Start UI: `bash scripts/run_web_ui.sh` (PORT override supported)
- UI tests: `cd ui-tests && npm install && npx playwright install && npx playwright test`

### Acceptance
- Dashboard reflects latest pipeline status (scored episodes, digests, RSS items, pending/failed episodes)
- Feeds and Topics changes persist and affect the pipeline
- “Check feed” surfaces networking/format issues that would block downloads

## Status & Next

Status: Core pipeline, publishing, and Web UI complete through Phase C.

Next:
- Phase D: Publishing UI (publish/unpublish, asset status), retention controls
- Phase E: Orchestration (lookback logic, manual dates, weekly summaries, scheduling)
- Phase F: Ops/docs (end‑to‑end tests, concise docs)

1. **Feed Manager** (`feed_manager.py`)
   - Add/remove RSS podcast feeds
   - Parse RSS feeds to discover new episodes
   - Track feed health and failure monitoring

2. **Audio Processor** (`audio_processor.py`)
   - Download podcast audio files from RSS episodes
   - Split audio into 10-minute chunks for processing
   - Manage audio file caching and cleanup

3. **Transcript Generator** (`transcript_generator.py`)
   - Transcribe audio chunks using Nvidia Parakeet ASR
   - Concatenate chunk transcripts into complete episodes
   - Quality validation and error handling

4. **Content Scorer** (`content_scorer.py`)
   - Score episodes against all topics using GPT-5-mini Responses API
   - Structured JSON output with relevancy scores 0.0-1.0
   - Batch processing for efficiency

5. **Script Generator** (`script_generator.py`)
   - Combine high-scoring episodes (≥0.65) per topic
   - Follow topic-specific instructions from digest_instructions/
   - Use GPT-5 with 25,000 word limit per script

6. **TTS Generator** (`tts_generator.py`)
   - Convert scripts to MP3 using ElevenLabs API
   - Configurable voice settings per topic
   - Generate titles/summaries using GPT-5-nano

7. **Publisher** (`publisher.py`)
   - Upload MP3s to GitHub repository
   - Update RSS XML feed for podcast.paulrbrown.org
   - Manage retention: 7 days local, 14 days GitHub

8. **Main Orchestrator** (`daily_digest.py`)
   - Coordinate entire pipeline
   - Handle Monday (72hr) vs weekday (24hr) lookback
   - Support manual trigger with date parameters

## Key Features & Requirements

### Content Processing
- **Source**: RSS podcast feeds specified by user
- **Filtering**: Minimum 3-minute duration, exclude short segments
- **Transcription**: Nvidia Parakeet ASR with 10-minute audio chunking
- **Scoring**: Each episode scored against all topics (0.0-1.0 scale)
- **Threshold**: Only episodes scoring ≥0.65 included in digests
- **Deduplication**: Prevent reprocessing of same episode_guid

### Quality Controls
- **Transcript Validation**: Verify transcript quality and completeness from ASR
- **Failure Handling**: 3-retry limit, mark failed episodes permanently
- **Feed Health**: Flag feeds with 3+ consecutive days of failures
- **Content Limits**: Maximum 25,000 words per script
- **Audio Quality**: Optimize for Bluetooth earbuds (good mobile quality)
- **Chunking Strategy**: Process audio in 10-minute segments for optimal ASR performance

### Automation Features
- **Daily Execution**: Cron job at 6 AM daily
- **Smart Lookback**: Monday 72hrs, other weekdays 24hrs
- **No Content Handling**: Generate "no new episodes today" audio on empty days
- **Manual Override**: Support specific date execution for debugging/catch-up
- **Comprehensive Logging**: File-based logging with minimal console output

### Publishing & Distribution
- **GitHub Integration**: Automated MP3 upload and release management
- **RSS Compliance**: Full RSS 2.0 specification with podcast extensions
 - **Vercel Hosting**: Static RSS XML served at podcast.paulrbrown.org/daily-digest.xml
- **Retention Management**: Automated cleanup after retention periods
- **Metadata Rich**: Include timestamps, summaries, and topic categorization

## API Integrations

### Audio Processing
- **RSS Feeds**: Standard RSS 2.0 with podcast extensions for episode discovery
- **HTTP Downloads**: Direct audio file downloads from podcast CDNs
- **Nvidia Parakeet ASR**: Open-source ASR model via Hugging Face Transformers

### AI Services
- **OpenAI GPT-5-mini**: Content scoring with Responses API and JSON schema
- **OpenAI GPT-5**: Script generation following topic instructions
- **OpenAI GPT-5-nano**: Title and summary generation

### Audio Services
- **ElevenLabs**: High-quality TTS conversion with voice customization

### Publishing Services
- **GitHub API**: Repository management and file uploads
- **Vercel**: Static hosting for RSS feed delivery

## Configuration Management

### Environment Variables (.env)
```
OPENAI_API_KEY=your-openai-api-key-here
ELEVENLABS_API_KEY=your-elevenlabs-key-here
GITHUB_TOKEN=your-github-token-here
GITHUB_REPOSITORY=your-username/your-repo-name
```

### Configuration Files
- **config/feeds.json**: RSS podcast feed management
- **config/topics.json**: Topic configuration with voice settings
- **digest_instructions/*.md**: Topic-specific generation instructions

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
