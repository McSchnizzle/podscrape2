# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## High-Level Architecture

This is an automated RSS podcast digest system that follows this flow:
```
RSS Feeds → Episode Discovery → Audio Download/Chunking → Transcription (Parakeet MLX) →
AI Scoring (GPT) → Script Generation → TTS Audio → Publishing (GitHub + Vercel RSS)
```

### Core Data Flow
- **RSS Feeds**: Monitored for new episodes via `src/podcast/feed_parser.py`
- **Audio Processing**: Downloads, chunks (3-min), transcribes with Parakeet MLX on Apple Silicon
- **Content Scoring**: Uses GPT-5-mini to score transcripts against configured topics (threshold: 0.65)
- **Script Generation**: Creates topic-based digest scripts using GPT-5 and topic instruction files
- **Audio Generation**: Converts scripts to MP3 using ElevenLabs TTS with topic-specific voices
- **Publishing**: Uploads to GitHub Releases, generates RSS feed, deploys to Vercel

### Database Architecture (SQLite → Postgres Migration Ready)
- **episodes**: Core episode data, transcripts, AI scores, processing status
- **feeds**: RSS feed URLs, titles, health status, last checked timestamps
- **digests**: Generated scripts, MP3 metadata, publishing status
- **web_settings**: UI configuration (score thresholds, audio processing settings)

The system supports both SQLite (current) and Postgres via SQLAlchemy models in `src/database/sqlalchemy_models.py`.

## Development Commands

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
# Full pipeline: RSS → Audio → Transcript → Score → Script → MP3 → Publish
python3 run_full_pipeline.py

# Publishing only: MP3s → GitHub → RSS → Vercel
python3 run_publishing_pipeline.py

# With custom logging
python3 run_full_pipeline.py --log pipeline_$(date +%Y%m%d_%H%M%S).log

# Stop after specific phase for debugging
python3 run_full_pipeline.py --phase audio  # discovery, audio, scoring, digest, tts
```

### Web UI (Optional)
```bash
# Start local web interface on 127.0.0.1:5001 (or custom PORT)
bash scripts/run_web_ui.sh
PORT=5002 bash scripts/run_web_ui.sh  # Custom port

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
# Initialize database
python3 src/database/init_db.py

# Manual episode scoring
python3 rescore_episodes.py

# Reset latest episode status for testing
python3 reset_latest_episode.py

# Transcribe specific episode
python3 transcribe_episode.py <episode_guid>
```

## Critical Development Guidelines

### Python Environment
**ALWAYS use `python3` command, never `python`** - this is critical for macOS compatibility.

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

### Configuration Management
- **Topics**: Managed in `config/topics.json` with voice mappings and instruction files
- **Topic Instructions**: Stored in `digest_instructions/` directory as markdown files
- **Web Settings**: Database-backed via `web_settings` table and `WebConfigManager`
- **Environment**: API keys in `.env` file (OpenAI, ElevenLabs, GitHub tokens)

### Audio Processing Architecture
- **Chunking**: Audio split into 3-minute chunks for optimal ASR performance
- **Transcription**: Parakeet MLX (Apple Silicon optimized) or fallback CPU processing
- **TTS**: ElevenLabs with topic-specific voice IDs and settings
- **Cleanup**: Automatic cleanup of intermediate audio files after processing

## Key File Structure Understanding

### Source Code Organization (`src/`)
```
config/          # Configuration management (topics, web settings, environment)
database/        # SQLite models + SQLAlchemy migration-ready models
podcast/         # RSS parsing, audio processing, Parakeet transcription
scoring/         # GPT-based content scoring against topics
generation/      # Script generation using topic instructions + GPT
audio/           # TTS generation, metadata, audio management
publishing/      # GitHub uploads, RSS generation, Vercel deployment
```

### Data Architecture (`data/`)
```
database/        # SQLite files (main: digest.db)
transcripts/     # Raw transcript files from Parakeet MLX
scripts/         # Generated digest scripts (markdown format)
completed-tts/   # Final MP3 files organized by date
logs/           # Pipeline execution logs
rss/            # Generated RSS feed (daily-digest.xml)
```

### Web UI (`web_ui/`)
Flask application providing local configuration interface:
- Settings management (score thresholds, audio processing options)
- Feed management (add/edit RSS feeds, health checking)
- Topic configuration (voice IDs, instruction files)
- Dashboard (recent episodes, system status, pipeline controls)

### Publishing Architecture
- **GitHub Releases**: Daily tags (`daily-YYYY-MM-DD`) with MP3 assets
- **RSS Generation**: Standards-compliant podcast RSS with proper metadata
- **Vercel Deployment**: Automatic deployment to `podcast.paulrbrown.org/daily-digest.xml`
- **Retention**: Automatic cleanup of old files (7-14 day retention)

## Integration Points

### Database Migration Strategy
The system is architected for migration from SQLite to Postgres (Supabase):
- Current: SQLite with custom models in `src/database/models.py`
- Future: SQLAlchemy models in `src/database/sqlalchemy_models.py`
- Migration script: `src/database/migrate_phase7.py`

### API Dependencies
- **OpenAI**: GPT-5-mini for scoring, GPT-5 for script generation
- **ElevenLabs**: TTS audio generation with voice cloning
- **GitHub**: Release management and asset hosting
- **Vercel**: RSS feed hosting and CDN

### External Tool Dependencies
- **ffmpeg**: Required for audio chunking and format conversion
- **gh CLI**: GitHub authentication and operations
- **parakeet-mlx**: Apple Silicon optimized transcription (optional but recommended)

## Development Workflow

When implementing features:
1. **Follow the phase structure**: The system was built in phases 1-7, each with specific test files
2. **Test with real data**: Use the established RSS feeds, not mock data
3. **Respect the data flow**: RSS → Audio → Transcript → Score → Script → TTS → Publish
4. **Database-first**: Update models and migrations before changing logic
5. **Error handling**: The system handles network failures, API limits, and partial processing gracefully
6. **Logging**: Comprehensive logging is critical - logs go to `data/logs/` and console

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

### Configuration Changes
- **Topics**: Edit `config/topics.json` directly or via Web UI
- **Instruction Files**: Add/edit markdown files in `digest_instructions/`
- **Settings**: Use Web UI or direct database manipulation of `web_settings` table
- **Feeds**: Add via Web UI or database insertion into `feeds` table