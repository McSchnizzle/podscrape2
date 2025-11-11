# RSS Podcast Digest System

Production-ready automated system that generates daily, topic-based podcast digests from RSS feeds. Features a comprehensive orchestrator, PostgreSQL database, OpenAI Whisper transcription, and Next.js Web UI for management.

**Current Version**: v1.84 (November 2025)
**Live RSS Feed**: https://podcast.paulrbrown.org/daily-digest.xml (Dynamic API)

## 🎯 Overview

This production system automatically:
- Discovers new episodes from RSS podcast feeds
- Downloads and transcribes audio using local OpenAI Whisper
- Scores content against multiple topics using GPT-4o-mini
- Generates topic-based digest scripts using GPT-4o (dialogue or narrative mode)
- Converts scripts to MP3 audio using ElevenLabs TTS (single-voice or multi-voice dialogue)
- Publishes via GitHub Releases and RSS feed at podcast.paulrbrown.org

## 🏗️ Architecture

**6-Phase Pipeline** (v1.51+):
```
1. Discovery → 2. Audio (Download/Transcribe/Score) → 3. Digest (Script Gen) →
4. TTS → 5. Publishing (GitHub + DB) → 6. Retention (Cleanup)
```

**Data Flow**:
```
RSS Feeds → Episode Discovery → Audio Download/Chunking → OpenAI Whisper (Memory-Efficient) →
AI Scoring → Script Generation (Database-First) → TTS → GitHub Releases → Dynamic RSS API → Retention Cleanup
```

### Core Components
- **Database**: PostgreSQL (Supabase) with SQLAlchemy models, RLS security, and automatic connection pooling
- **Orchestrator**: Production-ready 6-phase pipeline with comprehensive logging and error handling
- **Transcription**: Local OpenAI Whisper with memory-efficient incremental database writes (v1.52)
- **AI Processing**: GPT-4o-mini scoring and GPT-4o script generation (database-first architecture)
- **Audio/TTS**: ElevenLabs with per-topic voice configuration
  - **Dialogue Mode**: Multi-voice conversations with Text-to-Dialogue API (v3) and intelligent chunking
  - **Narrative Mode**: Single-voice TTS with text normalization and optimization
- **Publishing**: GitHub Releases (MP3 assets) + Dynamic RSS API (v1.49)
- **Retention**: Automated cleanup phase with configurable retention periods (v1.51)
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
├── scripts/                # Production phase scripts (6-phase architecture)
│   ├── run_discovery.py   # Phase 1: RSS feed discovery
│   ├── run_audio.py       # Phase 2: Download + transcribe + score
│   ├── run_digest.py      # Phase 3: Script generation
│   ├── run_tts.py         # Phase 4: Audio generation
│   ├── run_publishing.py  # Phase 5: GitHub uploads + database updates
│   └── run_retention.py   # Phase 6: Cleanup old files and records
├── data/
│   ├── database/          # Legacy SQLite files (PostgreSQL primary since v1.28)
│   ├── transcripts/       # Raw transcript files from OpenAI Whisper
│   ├── scripts/           # Temporary digest scripts (deleted after DB upload)
│   ├── completed-tts/     # Staging area for MP3s (deleted after GitHub upload)
│   └── logs/              # Execution logs (automatic retention management)
├── config/
│   └── (legacy files - all config now in PostgreSQL database)
├── tests/                # Phase-specific test suites
├── docs/
│   └── archive/          # Historical documentation
├── run_full_pipeline_orchestrator.py  # Production orchestrator
├── run_full_pipeline.py               # Legacy single-phase runner
└── run_publishing_pipeline.py         # Publishing-only pipeline
```

## 🚀 Quick Start

### Prerequisites
- Python 3.13+
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

# Individual phase execution (6-phase architecture)
python3 scripts/run_discovery.py   # Phase 1: Discover new episodes
python3 scripts/run_audio.py       # Phase 2: Download, transcribe, and score
python3 scripts/run_digest.py      # Phase 3: Generate scripts
python3 scripts/run_tts.py         # Phase 4: Create audio
python3 scripts/run_publishing.py  # Phase 5: Publish to GitHub + update DB
python3 scripts/run_retention.py   # Phase 6: Cleanup old files/records
```

#### Topic Management (Database-First Architecture)
- **All topic configuration lives in PostgreSQL `topics` table** (v1.52)
- Topic instructions stored as `instructions_md` field in database (no filesystem files)
- Voice settings, descriptions, and active status all in database
- **Management Options**:
  - Web UI Topics page: https://podcast.paulrbrown.org/topics (recommended)
  - Direct PostgreSQL table manipulation via Supabase SQL editor
  - No JSON files or markdown files in filesystem (digest_instructions/ removed v1.52)

### 🎙️ Multi-Voice Dialogue Mode (v1.79+)

The system supports two script generation modes per topic:

**Dialogue Mode** - Multi-voice conversational digests:
- **Format**: SPEAKER_1/SPEAKER_2 conversation with audio tags
- **Length**: 15,000-20,000 characters
- **Audio Tags**: ElevenLabs tags like `[excited]`, `[thoughtful]`, `[serious]`, `[laughs]`
- **TTS**: Text-to-Dialogue API (v3) with intelligent chunking (~3k chars per chunk)
- **Use Case**: Topics that benefit from conversational exploration (e.g., Community Organizing)

**Narrative Mode** - Single-voice optimized digests:
- **Format**: Standard narrative prose with TTS optimization
- **Length**: 10,000-15,000 characters
- **Optimization**: Text normalization (numbers spelled out, abbreviations expanded)
- **TTS**: Standard Text-to-Speech API with single voice
- **Use Case**: Topics that benefit from authoritative narration (e.g., AI & Technology)

**Configuration** (via Web UI):
1. Visit Topics page: https://podcast.paulrbrown.org/topics
2. Select script mode: "dialogue" or "narrative"
3. For dialogue mode:
   - Choose Voice 1 (e.g., "Young Jamal - energetic, passionate")
   - Choose Voice 2 (e.g., "Dakota H - thoughtful, analytical")
   - Select GPT model: gpt-4o or gpt-4o-mini
4. Edit topic instructions to guide conversation style
5. Use Script Lab preview to test with real episodes

**Example Dialogue Script**:
```
SPEAKER_1: [excited] Hey everyone, welcome back! Today we're diving into some incredible stories from the world of community organizing.

SPEAKER_2: [thoughtful] That's right. We've been following some amazing movements, and the energy behind these grassroots efforts is absolutely inspiring.
```

**Example Narrative Script**:
```
Welcome to today's digest on artificial intelligence and technology. We're exploring groundbreaking developments in AI safety, machine learning, and the future of autonomous systems...
```

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

- **Settings**: Database-backed controls for:
  - Content filtering (score_threshold, max_episodes_per_digest)
  - Audio processing (chunk_duration_minutes, transcribe settings)
  - Retention periods (local_mp3_days, github_release_days, logs_days, etc.)
- **Feeds**:
  - List/group active RSS feeds, latest episode + published date
  - Add feeds (URL validation, duplicate guard, title autofill), toggle active, soft delete
  - "Check feed" verifies TLS and audio enclosure reachability (no pipeline run)
- **Topics**:
  - Configure script mode: dialogue (multi-voice) or narrative (single-voice)
  - Select Voice 1 and Voice 2 (for dialogue mode) from ElevenLabs voice library
  - Choose dialogue model: GPT-4o or GPT-4o-mini
  - Edit instructions_md (database-stored, no files), description, active status
  - Script Lab preview: Generate and preview scripts with real episode data
  - All topic configuration stored in PostgreSQL, no filesystem dependencies
- **Dashboard**:
  - Key settings display; Recent RSS episodes with phase summaries
  - Last Run summary (scored episodes, created digests, MP3 durations)
  - Transcribed but not yet digested episodes; retry failed episodes
  - Run Publishing / Run Full Pipeline / per-phase execution buttons
  - Live Status: auto-starts log streaming with real-time phase badges
  - System Health: ffmpeg, gh CLI + auth, OpenAI Whisper, API keys, database connectivity

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

### Daily Pipeline (6-Phase Architecture)
1. **Discovery**: Find new episodes from RSS podcast feeds, update database
2. **Audio**: Download audio, chunk into 3-min segments, transcribe with OpenAI Whisper (memory-efficient), score with GPT-5-mini
3. **Digest**: Generate topic-based digest scripts using GPT-5 and database-stored instructions
4. **TTS**: Convert scripts to MP3 using ElevenLabs with topic-specific voices
5. **Publishing**: Upload MP3s to GitHub Releases, update database with github_url for dynamic RSS API
6. **Retention**: Cleanup old MP3s, GitHub releases, logs, and database records per configured retention periods

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

**Feed URL**: https://podcast.paulrbrown.org/daily-digest.xml (Dynamic API since v1.49)

**Architecture**:
- Next.js API route (`/api/rss/daily-digest`) generates RSS 2.0 XML on-demand from database
- URL rewrite maps `/daily-digest.xml` → `/api/rss/daily-digest` (configured in vercel.json)
- 5-minute edge cache for performance; database is single source of truth
- No static files; RSS reflects database state within 5 minutes of publishing

### Features
- RSS 2.0 with podcast extensions
- Daily episodes organized by topic (AI & Tech, Social Movements, Psychedelics & Consciousness)
- Rich metadata; compatible with major podcast clients (Apple Podcasts, Spotify, etc.)
- Configurable retention management (default: 14 days for episodes/digests)

### Episode Naming
- **MP3**: `{topic}_{YYYYMMDD}_{HHMMSS}.mp3`
- **Title**: "{Topic} Daily Digest - {Month DD, YYYY}"
- **No Content**: "No New Episodes Today - {Month DD, YYYY}"

## 🔧 Maintenance

### Retention Management (Dedicated Phase 6, v1.51+)
- **Local MP3s**: Deleted immediately after successful GitHub upload (no retention period)
- **GitHub Releases**: Configurable retention (default: 14 days) via `github_release_days` setting
- **Database Records**: Configurable retention (default: 14 days) via `episode_retention_days` and `digest_retention_days`
- **Logs**: Configurable retention (default: 3 days) via `logs_days` setting
- **Audio Cache**: Configurable retention (default: 3 days) via `audio_cache_days` setting
- **Database Backups**: Professional daily backups with 7+ day retention via Supabase
- **Configuration**: All retention periods managed in `web_settings` table, editable via Web UI

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

### Development Status
- **Current Version**: v1.52 (October 2025)
- **Architecture**: 6-phase pipeline (Discovery, Audio, Digest, TTS, Publishing, Retention)
- **Database**: PostgreSQL (Supabase) with Row Level Security (RLS) enabled
- **Recent Work**: See `COMPLETED_TASKS_SUMMARY.md` for detailed session history through v1.52
- **Remaining Work**: See `master-tasklist.md` for P3 (Low) tasks (15 remaining)

### Contributing
1. Follow database-first architecture principles (no filesystem fallbacks)
2. Use 6-phase pipeline structure for new features
3. Update `master-tasklist.md` with progress
4. Maintain comprehensive test coverage with real RSS feeds (no mocks)
5. Increment version in `web_ui_hosted/app/version.ts` on every commit

### Code Style
- Black formatting with Flake8 linting
- Type hints required for all functions
- Comprehensive error handling with retry logic
- Standardized logging via PipelineLogger
- SQLAlchemy models with Alembic migrations

## 📚 Documentation

- **[CLAUDE.md](CLAUDE.md)**: Development guidelines for Claude Code integration
- **[Product Requirements](podscrape2-prd.md)**: Complete project specification
- **[Completed Tasks](COMPLETED_TASKS_SUMMARY.md)**: Detailed session history (v1.01-v1.52)
- **[Remaining Work](master-tasklist.md)**: Current task list (15 P3 tasks remaining)
- **[Version Guide](VERSION_GUIDE.md)**: Version tracking and commit guidelines
- **[Archive](docs/archive/)**: Historical documentation and completed phases

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
2. Run environment validation: `python3 scripts/doctor.py`
3. Review completed work in `COMPLETED_TASKS_SUMMARY.md`
4. Review remaining tasks in `master-tasklist.md`
5. Check API key configuration in `.env`
6. View system health via Web UI: https://podcast.paulrbrown.org

**Project Status**: ✅ Production (v1.52)
**Architecture**: 6-Phase Pipeline (Discovery → Audio → Digest → TTS → Publishing → Retention)
**Database**: PostgreSQL (Supabase) with RLS
**RSS Feed**: Dynamic API (https://podcast.paulrbrown.org/daily-digest.xml)
