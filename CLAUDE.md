# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## High-Level Architecture

This is an automated RSS podcast digest system that follows this flow:
```
RSS Feeds → Episode Discovery → Audio Download/Chunking → Transcription (OpenAI Whisper) →
AI Scoring (GPT) → Script Generation → TTS Audio → Publishing (GitHub + Dynamic RSS API) → Retention
```

**Current Version**: v1.84 (November 2025)
**Pipeline Architecture**: 6 phases (Discovery, Audio, Digest, TTS, Publishing, Retention)

### Core Data Flow
- **RSS Feeds**: Monitored for new episodes via `src/podcast/feed_parser.py`
- **Audio Processing**: Downloads, chunks (3-min), transcribes with OpenAI Whisper (cross-platform)
- **Content Scoring**: Uses GPT-4o-mini to score transcripts against configured topics (threshold: 0.65)
- **Script Generation**: Creates topic-based digest scripts using GPT-4o and database-stored topic instructions (database-first architecture)
  - **Dialogue Mode**: SPEAKER_1/SPEAKER_2 format with audio tags (15-20k chars)
  - **Narrative Mode**: Single-voice TTS-optimized prose (10-15k chars)
- **Audio Generation**: Converts scripts to MP3 using ElevenLabs TTS
  - **Dialogue Mode**: Text-to-Dialogue API (v3) with intelligent chunking (~3k chars per chunk)
  - **Narrative Mode**: Standard Text-to-Speech API with single voice
- **Publishing**: Uploads to GitHub Releases, updates database for dynamic RSS API (no static files since v1.49)
- **Retention**: Automatic cleanup of old MP3s, GitHub releases, logs, and database records based on configured retention periods

### Database Architecture (PostgreSQL via Supabase)
- **episodes**: Core episode data, transcripts, AI scores, processing status
- **feeds**: RSS feed URLs, titles, health status, last checked timestamps
- **digests**: Generated scripts, MP3 metadata, publishing status
- **web_settings**: UI configuration (score thresholds, audio processing settings)

The system uses PostgreSQL (Supabase) with SQLAlchemy models in `src/database/sqlalchemy_models.py`. Legacy SQLite support available in `src/database/models.py`.

## Development Commands

### **CRITICAL: Version Management on Every Commit**
**IMPORTANT**: Before making any commit, you MUST update the version number in `web_ui_hosted/app/version.ts`:

```typescript
export const VERSION = "0.78"; // Increment by 0.01 from previous version
```

**Current version tracking**:
- Check current version: `web_ui_hosted/app/version.ts`
- Version guide: `VERSION_GUIDE.md`
- Every commit increments by 0.01 (e.g., 0.77 → 0.78 → 0.79)
- Include version in commit message: `feat: add feature (v0.78)`

### Environment Setup
```bash
# Use python3 explicitly (required on macOS)
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt

# Required external tools
brew install ffmpeg  # Audio processing
brew install gh && gh auth login  # GitHub publishing
```

### Core Pipeline Commands
```bash
# Full pipeline orchestrator: RSS → Audio → Transcript → Score → Script → MP3 → Publish
python3 run_full_pipeline_orchestrator.py

# Legacy single-phase: RSS → Audio → Transcript → Score → Script → MP3 → Publish
python3 run_full_pipeline.py

# Publishing only: MP3s → GitHub → RSS → Vercel
python3 run_publishing_pipeline.py

# Stop after specific phase for debugging
python3 run_full_pipeline_orchestrator.py --phase audio  # discovery, audio, digest, tts, publishing, retention

# Individual phase scripts (production-ready)
python3 scripts/run_discovery.py    # RSS feed discovery
python3 scripts/run_audio.py        # Download + transcribe + score (integrated since v1.28)
python3 scripts/run_digest.py       # Script generation
python3 scripts/run_tts.py          # Audio generation
python3 scripts/run_publishing.py   # GitHub release uploads + database updates
python3 scripts/run_retention.py    # Cleanup old files and database records
```

### Web UI (Next.js)
```bash
# Start Next.js web interface (default: localhost:3000)
cd web_ui_hosted && npm run dev

# UI tests (requires UI running)
cd ui-tests && npm install && npx playwright install && npx playwright test
```

### Testing Commands
```bash
# Phase-specific testing (real RSS feeds, no mocking)
python3 test_phase2_simple.py  # RSS feed parsing
python3 test_phase3.py         # Audio transcription
python3 test_phase4.py         # Content scoring
python3 test_phase5.py         # Script generation
python3 test_phase6_integration.py  # TTS audio generation

# Integration tests
python3 test_full_pipeline_integration.py
python3 test_database_integration.py

# Utility testing
python3 test_voice_configuration.py
python3 test_metadata_generation.py
```

### Database Commands
```bash
# Initialize database (SQLite legacy) or run Alembic migrations (PostgreSQL)
python3 src/database/init_db.py
python3 -m alembic upgrade head  # For PostgreSQL/Supabase

# Manual episode scoring
python3 rescore_episodes.py

# Reset latest episode status for testing
python3 reset_latest_episode.py

# Transcribe specific episode
python3 transcribe_episode.py <episode_guid>

# Row Level Security (RLS) Management
python3 -m alembic upgrade head  # Apply all RLS migrations
python3 -m alembic current       # Check current migration status

# RLS Troubleshooting - if database access fails
# 1. Verify service role credentials in environment
# 2. Check that DATABASE_URL uses service role (postgres user)
# 3. Confirm SUPABASE_SERVICE_ROLE is set for web UI
# 4. All operations should use service role which bypasses RLS
```

## Critical Development Guidelines

### Environment Configuration - FAIL FAST PRINCIPLE
**CRITICAL**: Environment configuration issues must FAIL IMMEDIATELY and LOUDLY. No fallbacks, no silent failures.

**Core Principle**: If any required environment variable is missing or misconfigured, the system must:
1. Stop immediately with a clear error message
2. Exit with a non-zero status code
3. Show RED status in the Web UI system health
4. Never attempt to run with incomplete configuration

**Required Environment Variables**:
- `OPENAI_API_KEY` - OpenAI API access for scoring and script generation
- `ELEVENLABS_API_KEY` - ElevenLabs TTS audio generation
- `GITHUB_TOKEN` - GitHub repository access for publishing
- `GITHUB_REPOSITORY` - Target repository (format: owner/repo)
- `DATABASE_URL` or Supabase configuration - Database connectivity

**Implementation**:
- Use `scripts/doctor.py` to validate all required dependencies
- Web UI system health section shows immediate RED for missing config
- All scripts check environment at startup before proceeding
- No masking or workarounds - configuration problems must be fixed

### Python Environment
**Requires Python 3.13+**. Always use `python3` command, never `python` - this is critical for macOS compatibility.

### macOS Command Compatibility
**Use `gtimeout` instead of `timeout`** for command timeouts on macOS. For Claude Code Bash tool, use the `timeout` parameter instead.

### Real Data Testing Philosophy
**NEVER use mock data or fake RSS feeds**. Always test with real RSS feeds:
- The Bridge with Peter Mansbridge: https://feeds.simplecast.com/imTmqqal
- Anchor feed: https://anchor.fm/s/e8e55a68/podcast/rss
- The Great Simplification: https://thegreatsimplification.libsyn.com/rss
- Movement Memos: https://feeds.megaphone.fm/movementmemos
- Kultural: https://feed.podbean.com/kultural/feed.xml

Real data reveals actual RSS behavior, network issues, and audio CDN problems that mocks hide.

### Configuration Management (Database-First Architecture)
- **Topics**: Stored in PostgreSQL `topics` table with voice mappings and instructions_md (no filesystem fallbacks since v1.52)
- **Topic Instructions**: Stored as `instructions_md` field in database `topics` table (digest_instructions/ directory deleted in v1.52)
- **Web Settings**: Database-backed via `web_settings` table and `WebConfigManager`
- **Environment**: API keys in `.env` file (OpenAI, ElevenLabs, GitHub tokens)
- **Feeds**: Stored in PostgreSQL `feeds` table (no JSON files)

### Audio Processing Architecture
- **Chunking**: Audio split into 3-minute chunks for optimal ASR performance
- **Transcription**: OpenAI Whisper (local, cross-platform) with configurable model size
- **Memory Efficiency**: Incremental database writes per chunk for O(1) constant memory usage (v1.52)
- **TTS**: ElevenLabs with topic-specific voice IDs and settings (single-voice or multi-voice dialogue)
- **Cleanup**: Automatic cleanup of intermediate audio files after processing

### Multi-Voice Dialogue Mode (v1.79+)
The system supports two script generation modes per topic:

**Dialogue Mode** (for conversational digests):
- **Format**: SPEAKER_1/SPEAKER_2 conversation format with audio tags
- **Length**: 15,000-20,000 characters
- **Audio Tags**: Supports ElevenLabs audio tags like [excited], [thoughtful], [serious], [laughs], etc.
- **TTS API**: ElevenLabs Text-to-Dialogue API (v3) with intelligent chunking
- **Chunking**: Automatically splits scripts into ~3k character chunks at speaker boundaries
- **Voice Config**: Requires `voice_1_id` and `voice_2_id` in database (configured via Web UI)

**Narrative Mode** (for single-voice digests):
- **Format**: Standard narrative prose with TTS optimization
- **Length**: 10,000-15,000 characters
- **TTS Optimization**: Text normalization (numbers spelled out, abbreviations expanded)
- **TTS API**: ElevenLabs standard Text-to-Speech API
- **Voice Config**: Uses primary `voice_1_id` only

**Configuration** (via Web UI Topics page):
```typescript
// Database fields in topics table
script_mode: 'dialogue' | 'narrative'  // Script generation mode
voice_1_id: string                      // ElevenLabs voice ID for Voice 1 / narrator
voice_2_id: string | null               // ElevenLabs voice ID for Voice 2 (dialogue only)
dialogue_model: string                  // GPT model: 'gpt-4o' or 'gpt-4o-mini'
instructions_md: string                 // Topic-specific generation instructions
```

**Dialogue Script Example**:
```
SPEAKER_1: [excited] Hey everyone, welcome back! Today we're diving into some incredible stories from the world of community organizing.

SPEAKER_2: [thoughtful] That's right. We've been following some amazing movements, and the energy behind these grassroots efforts is absolutely inspiring.

SPEAKER_1: [serious] Let's start with the transit justice campaign in Los Angeles...
```

**Narrative Script Example**:
```
Welcome to today's digest on artificial intelligence and technology. We're exploring groundbreaking developments in AI safety, machine learning, and the future of autonomous systems.

Recent research from Stanford reveals fascinating insights into large language model capabilities. Scientists have discovered that these models can exhibit emergent properties...
```

**Audio Tags Reference**:
Supported ElevenLabs audio tags for dialogue mode:
- Emotion: `[excited]`, `[thoughtful]`, `[serious]`, `[concerned]`, `[hopeful]`
- Action: `[laughs]`, `[sighs]`, `[chuckles]`
- Pacing: `[pause]`, `[quickly]`, `[slowly]`

**Implementation Files**:
- Script generation: `src/generation/script_generator.py`
- Audio generation: `src/audio/audio_generator.py`
- Dialogue chunking: `src/audio/dialogue_chunker.py`
- Web UI configuration: `web_ui_hosted/app/topics/page.tsx`
- Script preview: `web_ui_hosted/app/api/script-lab/preview/route.ts`

## Key File Structure Understanding

### Source Code Organization (`src/`)
```
config/          # Configuration management (web settings, environment)
database/        # SQLAlchemy models for PostgreSQL + legacy SQLite support
podcast/         # RSS parsing, audio processing, OpenAI Whisper transcription
generation/      # Script generation using database-stored instructions + GPT
audio/           # TTS generation, metadata, audio management
publishing/      # GitHub uploads, database updates for dynamic RSS API
utils/           # Shared utilities, logging, error handling
```

### Data Architecture (`data/`)
```
database/        # Legacy SQLite files (digest.db) - PostgreSQL primary since v1.28
transcripts/     # Raw transcript files from OpenAI Whisper
scripts/         # Temporary digest scripts (deleted after database upload since v1.51)
completed-tts/   # Staging area for MP3 files (deleted after GitHub upload since v1.51)
logs/           # Pipeline execution logs (automatic retention management)
```

**Note**: RSS feed is now dynamically generated via API route (no static files since v1.49)

### Web UI (`web_ui_hosted/`)
Next.js application providing hosted configuration interface at podcast.paulrbrown.org:
- Settings management (score thresholds, audio processing options, retention periods)
- Feed management (add/edit RSS feeds, health checking, active/inactive toggles)
- Topic configuration (voice IDs, instructions_md editing via database)
- Dashboard (recent episodes, system status, pipeline controls, phase summaries)

### Publishing Architecture
- **GitHub Releases**: Daily tags (`daily-YYYY-MM-DD`) with MP3 assets uploaded and stored
- **Dynamic RSS API**: Next.js API route generates RSS 2.0 XML from database on-demand (v1.49)
  - URL: `podcast.paulrbrown.org/daily-digest.xml` → `/api/rss/daily-digest`
  - 5-minute edge cache, no static files, database is single source of truth
- **Vercel Hosting**: Automatic deployment of Next.js app with API routes
- **Retention Phase**: Dedicated cleanup phase (v1.51) with configurable periods:
  - Local MP3s: Deleted immediately after GitHub upload
  - GitHub releases: 14 days (configurable)
  - Database records: 14 days (configurable)
  - Logs: 3 days (configurable)

## Integration Points

### Database Architecture
The system uses PostgreSQL (Supabase) for production:
- **Production**: PostgreSQL with SQLAlchemy models in `src/database/sqlalchemy_models.py`
- **Legacy**: SQLite support maintained in `src/database/models.py`
- **Migration**: Completed migration to Supabase with automatic connection pooling
- **Backup**: Professional daily backups with 7+ day retention via Supabase
- **Security**: Full Row Level Security (RLS) enabled on ALL tables following Supabase best practices

#### Row Level Security (RLS) Implementation
**CRITICAL**: All tables in the public schema have RLS enabled per Supabase security requirements.

**RLS Status (ALL ENABLED)**:
- ✅ `episodes` - RLS enabled with service_role + authenticated policies
- ✅ `feeds` - RLS enabled with service_role + authenticated policies
- ✅ `digests` - RLS enabled with service_role + authenticated policies
- ✅ `web_settings` - RLS enabled with service_role + authenticated policies
- ✅ `topics` - RLS enabled with service_role + authenticated policies
- ✅ `topic_instruction_versions` - RLS enabled with service_role + authenticated policies
- ✅ `digest_episode_links` - RLS enabled with service_role + authenticated policies
- ✅ `pipeline_runs` - RLS enabled with service_role + authenticated policies
- ✅ `alembic_version` - RLS enabled with service_role policy only

**RLS Policies**:
- **service_role_policy**: Full CRUD access for backend operations and migrations
- **authenticated_read_policy**: Read-only access for web UI (where applicable)

**Database Connection Requirements**:
- **Python Backend**: Uses `postgres` user (service role) via `DATABASE_URL`/`SUPABASE_PASSWORD`
- **Next.js Web UI**: Uses `SUPABASE_SERVICE_ROLE` key for admin operations
- **Alembic Migrations**: Uses service role credentials, bypasses RLS automatically

**Adding New Tables**: Always include RLS enablement in migration files:
```sql
-- In your Alembic migration upgrade() function:
op.execute("ALTER TABLE your_new_table ENABLE ROW LEVEL SECURITY;")
op.execute('''
    CREATE POLICY "service_role_policy" ON your_new_table
    FOR ALL TO service_role
    USING (true) WITH CHECK (true);
''')
op.execute('''
    CREATE POLICY "authenticated_read_policy" ON your_new_table
    FOR SELECT TO authenticated
    USING (true);
''')
```

### API Dependencies
- **OpenAI**: GPT-5-mini for scoring, GPT-5 for script generation
- **ElevenLabs**: TTS audio generation with voice cloning
- **GitHub**: Release management and asset hosting
- **Vercel**: RSS feed hosting and CDN

### External Tool Dependencies
- **ffmpeg**: Required for audio chunking and format conversion
- **gh CLI**: GitHub authentication and operations
- **OpenAI Whisper**: Cross-platform local transcription (no API costs)

## Development Workflow

When implementing features:
1. **Use the orchestrator**: Primary pipeline is `run_full_pipeline_orchestrator.py` with comprehensive logging and error handling
2. **Phase-based development**: Independent phase scripts in `scripts/` directory for modular execution
3. **Test with real data**: Use the established RSS feeds, not mock data
4. **Respect the data flow**: RSS → Audio → Transcript → Score → Script → TTS → Publish
5. **Database-first**: SQLAlchemy models with migrations for PostgreSQL (Supabase)
6. **Error handling**: The system handles network failures, API limits, and partial processing gracefully
7. **Logging**: Standardized logging via `PipelineLogger` with automatic cleanup and retention management

## Common Maintenance Tasks

### Episode Processing Issues
```bash
# Check episode status in database
python3 -c "from src.database.models import *; repo = get_episode_repo(); episodes = repo.get_recent_episodes(5); [print(f'{e.title}: {e.status}') for e in episodes]"

# Rescore existing episodes with new topics/thresholds
python3 rescore_episodes.py

# Retry failed episodes
python3 -c "from src.database.models import *; repo = get_episode_repo(); failed = repo.get_failed_episodes(); print(f'Failed: {len(failed)}')"
```

### Publishing Issues
```bash
# Retry publishing for recent digests
python3 run_publishing_pipeline.py --days-back 7

# Check GitHub releases
gh release list --repo $GITHUB_REPOSITORY

# Validate RSS feed
curl -s https://podcast.paulrbrown.org/daily-digest.xml | head -20
```

### Configuration Changes (Database-First Architecture)
- **Topics**: Edit via Web UI Topics page or direct PostgreSQL `topics` table manipulation
- **Topic Instructions**: Edit `instructions_md` field in `topics` table (no filesystem files since v1.52)
- **Settings**: Use Web UI Settings page or direct database manipulation of `web_settings` table
- **Feeds**: Add via Web UI Feeds page or database insertion into `feeds` table
- **Retention Periods**: Configure via Web UI or `web_settings` table (local_mp3_days, github_release_days, etc.)