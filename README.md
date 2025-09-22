# RSS Podcast Digest System

Production-ready automated system that generates daily, topic-based podcast digests from RSS feeds. Features a comprehensive orchestrator, PostgreSQL database, OpenAI Whisper transcription, and optional Web UI for management.

**Live RSS Feed**: https://podcast.paulrbrown.org/daily-digest.xml

## 🎯 Overview

This production system automatically:
- Discovers new episodes from RSS podcast feeds
- Downloads and transcribes audio using local OpenAI Whisper
- Scores content against multiple topics using GPT-5-mini
- Generates topic-based digest scripts using GPT-5
- Converts scripts to MP3 audio using ElevenLabs TTS
- Publishes via GitHub Releases and RSS feed at podcast.paulrbrown.org

## 🏗️ Architecture

```
RSS Feeds → Episode Discovery → Audio Download/Chunking → OpenAI Whisper Transcription → AI Scoring → Script Generation → TTS → GitHub/RSS Publishing
```

### Core Components
- **Database**: PostgreSQL (Supabase) with SQLAlchemy models and automatic connection pooling
- **Orchestrator**: Production-ready pipeline with comprehensive logging and error handling
- **Transcription**: Local OpenAI Whisper (cross-platform, no API costs)
- **AI Processing**: GPT-5-mini scoring and GPT-5 script generation
- **Audio/TTS**: ElevenLabs with per-topic voice configuration
- **Publishing**: GitHub Releases (MP3 assets) + Vercel (RSS feed)
- **Web UI**: Next.js app hosted at podcast.paulrbrown.org for management and monitoring

## 📁 Project Structure

```
podscrape2/
├── src/                    # Source code
│   ├── database/          # Database models and migrations
│   ├── podcast/           # RSS feeds, episodes, audio
│   ├── transcripts/       # Transcript processing
│   ├── scoring/           # AI-powered content scoring
│   ├── generation/        # Script generation
│   ├── audio/             # TTS and audio processing
│   └── publishing/        # GitHub and RSS publishing
├── web_ui_hosted/         # Next.js Web UI (hosted on Vercel)
├── ui-tests/              # Playwright end-to-end tests for the Web UI
├── scripts/                # Production phase scripts
│   ├── run_discovery.py   # RSS feed discovery
│   ├── run_audio.py       # Download + transcribe
│   ├── run_scoring.py     # AI content scoring
│   ├── run_digest.py      # Script generation
│   ├── run_tts.py         # Audio generation
│   └── run_publishing.py  # GitHub + RSS + Vercel
├── data/
│   ├── database/          # Legacy SQLite files
│   ├── transcripts/       # Raw transcript files
│   ├── scripts/           # Generated digest scripts
│   ├── completed-tts/     # Generated MP3 files
│   └── logs/              # Execution logs
├── config/
│   ├── channels.json      # YouTube channel configuration
│   └── topics.json        # Topic and voice settings
├── digest_instructions/   # Topic-specific generation instructions
├── music_cache/          # Audio assets for music beds
├── tests/                # Phase-specific test suites
├── docs/
│   ├── podscrape2-prd.md # Product Requirements Document
│   └── completed-phases1-7.md  # Completed work log (Phases 1–7)
│   └── tasklist2.md      # Remaining work (Web UI + Automation)
├── run_full_pipeline_orchestrator.py  # Production orchestrator
├── run_full_pipeline.py               # Legacy single-phase runner
└── run_publishing_pipeline.py         # Publishing-only pipeline
```

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- RSS podcast feeds to monitor
- API keys: OpenAI, ElevenLabs, GitHub
- PostgreSQL database (Supabase recommended)
- ffmpeg for audio processing

### Installation

1. **Clone Repository**
   ```bash
   git clone https://github.com/McSchnizzle/podscrape2.git
   cd podscrape2
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

4. **Setup Database**
   ```bash
   # For PostgreSQL (production)
   python3 -m alembic upgrade head

   # For SQLite (legacy/local testing)
   python3 src/database/init_db.py
   ```

5. **Add RSS Feeds**
   ```bash
   # Via Web UI (recommended)
   # Navigate to https://podcast.paulrbrown.org/feeds
   # Or run locally: cd web_ui_hosted && npm run dev

   # Or via database directly
   # Add feeds to PostgreSQL feeds table
   ```

6. **Run Test Pipeline**
   ```bash
   # Production orchestrator (recommended)
   python3 run_full_pipeline_orchestrator.py --phase discovery

   # Full production run
   timeout 15m python3 run_full_pipeline_orchestrator.py
   ```

### Configuration

#### API Keys (.env)
```bash
OPENAI_API_KEY=your-openai-api-key-here          # GPT-5 models
ELEVENLABS_API_KEY=your-elevenlabs-key-here      # TTS generation
GITHUB_TOKEN=your-github-token-here              # Repository access
GITHUB_REPOSITORY=your-username/your-repo-name
DATABASE_URL=postgresql://user:pass@host:5432/db # PostgreSQL (Supabase)
WHISPER_MODEL=base                               # OpenAI Whisper model size
```

#### Feed Management
```bash
# Use Web UI for feed management (recommended)
# Visit https://podcast.paulrbrown.org/feeds
# Or run locally: cd web_ui_hosted && npm run dev

# Or check feeds programmatically
python3 scripts/run_discovery.py --dry-run --verbose

# Individual phase execution
python3 scripts/run_discovery.py   # Discover new episodes
python3 scripts/run_audio.py       # Download and transcribe
python3 scripts/run_scoring.py     # Score content
python3 scripts/run_digest.py      # Generate scripts
python3 scripts/run_tts.py         # Create audio
python3 scripts/run_publishing.py  # Publish to GitHub/RSS
```

#### Topic Management (Supabase)
- Topics, instructions, and voice settings now live in the Supabase `topics` table.
- To migrate legacy JSON/topic files:
  ```bash
  python3 scripts/migrate_topics_to_supabase.py --dry-run   # preview
  python3 scripts/migrate_topics_to_supabase.py             # import into Supabase
  ```
- Edit topics from the hosted Web UI (Topics page) or locally via Supabase SQL/editor.

## 🔄 Daily Operation

### Automated Execution
```bash
# Add to crontab for daily 6 AM execution
0 6 * * * cd /path/to/podscrape2 && timeout 15m python3 run_full_pipeline_orchestrator.py
```

### Manual Execution
```bash
# Full production pipeline
python3 run_full_pipeline_orchestrator.py

# Stop after specific phase
python3 run_full_pipeline_orchestrator.py --phase audio

# Publishing only (uses existing MP3s)
python3 run_publishing_pipeline.py

# Individual phase with options
python3 scripts/run_audio.py --limit 3 --verbose
python3 scripts/run_scoring.py --dry-run
```

### Monitoring
```bash
# View recent logs
tail -f data/logs/digest_$(date +%Y%m%d).log

# Check channel health
python src/channels/manage.py health

# Database status
python src/database/status.py
```

## 🖥️ Web UI (Hosted)

The Next.js Web UI is hosted at https://podcast.paulrbrown.org and provides:

- **Settings**: DB‑backed controls for:
  - content_filtering.score_threshold
  - content_filtering.max_episodes_per_digest
  - audio_processing.chunk_duration_minutes
  - audio_processing.transcribe_all_chunks / max_chunks_per_episode
- **Feeds**:
  - List/group (RSS vs YouTube), latest episode + published date (RSS)
  - Add (URL validation, duplicate guard, title autofill), toggle active, soft delete
  - “Check feed” verifies TLS and audio enclosure reachability (no pipeline run)
- **Topics**:
  - Edit voice_id, instruction_file (upload/validate under `digest_instructions/`), description, active
- **Dashboard**:
  - Key settings; 6 most recent RSS items
  - Last Run summary (recent scored episodes with correct feed + qualifying topics; created digests and MP3 durations)
  - Transcribed but not yet digested (accurate); retry failed episodes
  - Run Publishing / Run Full Pipeline / per‑phase buttons
  - Live Status: auto‑starts log streaming with phase badges
  - System Health: ffmpeg, gh CLI + auth, parakeet‑mlx, API keys

Run the UI locally:
```bash
cd web_ui_hosted && npm run dev    # Usually starts on localhost:3000
```

Web UI tests (with UI running):
```bash
cd ui-tests && npm install && npx playwright install && npx playwright test
```

## 🧪 Testing

Each development phase includes comprehensive testing:

```bash
# Run phase-specific tests
python tests/test_phase1.py  # Database and configuration
python tests/test_phase2.py  # Channel management
python tests/test_phase3.py  # Transcript processing
# ... etc

# Run integration tests
python tests/test_integration.py

# Run performance tests
python tests/test_performance.py
```

## 📊 Content Flow

### Daily Pipeline
1. **Discovery**: Find new episodes from RSS podcast feeds
2. **Filtering**: Exclude episodes <3 minutes, download audio
3. **Transcription**: Process audio chunks with local OpenAI Whisper
4. **Scoring**: Score each episode against all topics (GPT-5-mini)
5. **Selection**: Include episodes scoring ≥0.65 for each topic
6. **Generation**: Create topic-based digest scripts (GPT-5)
7. **Audio**: Convert scripts to MP3 (ElevenLabs TTS)
8. **Publishing**: Upload to GitHub Releases and update RSS feed

### Content Scoring
- Each episode scored against all topics (0.0-1.0 scale)
- Threshold: ≥0.65 for inclusion in topic digest
- High-scoring episodes can appear in multiple topic digests
- Empty topics generate "no new episodes today" audio

### Quality Controls
- Minimum 3-minute video duration
- 3-retry limit for transcript failures
- Channel health monitoring (flag after 3 consecutive failure days)
- 25,000 word limit per script
- Audio quality optimized for mobile/Bluetooth playback

## 📱 RSS Feed

**Feed URL**: https://podcast.paulrbrown.org/daily-digest.xml (canonical)

Note: As of Sep 2025, the project standardized on `daily-digest.xml` (retiring `daily-digest2.xml`). A redirect from `/daily-digest2.xml` to `/daily-digest.xml` is configured in `vercel.json` for backward compatibility.

### Features
- RSS 2.0 with podcast extensions
- Daily episodes organized by topic
- Rich metadata; compatible with major podcast clients
- 14‑day retention management

### Episode Naming
- **MP3**: `{topic}_{YYYYMMDD}_{HHMMSS}.mp3`
- **Title**: "{Topic} Daily Digest - {Month DD, YYYY}"
- **No Content**: "No New Episodes Today - {Month DD, YYYY}"

## 🔧 Maintenance

### File Retention (WebConfig Driven)
- **Local MP3s**: 7 days automatic cleanup via orchestrator
- **GitHub Releases**: 14 days automatic cleanup
- **Database**: PostgreSQL with Supabase professional backups
- **Logs**: 3 days automatic cleanup with WebConfig override
- **Scripts/Transcripts**: 14 days automatic cleanup

### Health Monitoring
- Channel failure tracking
- API rate limit monitoring
- Database performance metrics
- Audio generation success rates

### Troubleshooting
```bash
# Check system status
python src/utils/health_check.py

# Repair database
python src/database/repair.py

# Retry failed episodes
python src/utils/retry_failed.py

# Clear cache
python src/utils/clear_cache.py
```

## 🛠️ Development

### Phase-Based Development
See `completed-phases1-7.md` for completed phases and `tasklist2.md` for remaining work and Web UI plan.

**Current Status**: Phase 0 - Project Setup  
**Next Phase**: Phase 1 - Foundation & Data Layer

### Contributing
1. Follow phase-based development approach
2. Run phase tests before proceeding  
3. Update `tasklist2.md` with progress
4. Maintain comprehensive test coverage

### Code Style
- Black formatting with Flake8 linting
- Type hints required for all functions
- Comprehensive error handling with retry logic
- Standardized logging via PipelineLogger
- SQLAlchemy models with Alembic migrations

## 📚 Documentation

- **[Product Requirements](docs/podscrape2-prd.md)**: Complete project specification
- **[Completed Phases](completed-phases1-7.md)**: Work completed to date
- **[Remaining Work](tasklist2.md)**: Web UI + automation plan
- **[Topic Instructions](digest_instructions/)**: AI generation guidelines
- **[API Integration Guide](docs/gpt5-implementation-learnings.md)**: GPT-5 implementation details

## 🚨 Important Notes

### Rate Limits & Politeness
- YouTube API: Respectful request spacing
- OpenAI API: Built-in rate limiting
- ElevenLabs: Voice generation quotas
- GitHub API: Release management limits

### Privacy & Compliance
- Transcript-only processing (no audio redistribution)
- Local database storage for privacy
- Fair use compliance for content curation
- No PII storage or processing

### Future Enhancements
- Music bed integration with existing assets
- Advanced audio production features  
- Multi-voice support for different content types
- Enhanced content filtering and relevance detection

---

## 📞 Support

For questions or issues:
1. Check existing logs in `data/logs/`
2. Run health check: `python src/utils/health_check.py`
3. Review phase testing in `completed-phases1-7.md` and remaining items in `tasklist2.md`
4. Check API key configuration in `.env`

**Project Status**: 🔄 Active Development  
**Current Phase**: Phase 0 - Project Setup  
**Target Completion**: September 24, 2025
