# Move Online - Phase 2 (Remaining Tasks)

**Pending work to complete the move to online infrastructure**

> **2025-09-20 Update:** See `docs/complete-hosted-migration-plan.md` for the detailed Supabase-first roadmap covering topics/settings migration, pipeline refactors, and hosted UI parity. Items below will be reconciled against that plan as work proceeds on `feature/complete-hosted-migration`.

## Phase 1a — Database Migration ✅ COMPLETED

- [x] **Utility Script Updates**: Update remaining scripts to use new repository pattern
  - [x] `rescore_episodes.py`: Uses new SQLAlchemy repository pattern via `get_episode_repo()`
  - [x] `reset_latest_episode.py`: Uses new SQLAlchemy repository pattern via `get_episode_repo()`
  - [x] All utility scripts converted to SQLAlchemy repository pattern
- [x] **Testing**: Unit/integration tests pass against Postgres via test fixtures in `conftest.py`

## Phase 2 — Storage and Artifact Strategy ⚠️ PENDING CI/CD

- [ ] **Pipeline Artifacts**: Pipeline logs and generated content uploaded as GitHub Actions Artifacts
  - **Status**: No GitHub Actions workflow files found (`.github/workflows/` directory does not exist)
  - **Dependency**: Requires Phase 4 CI/CD implementation first

## Phase 3 — CLI Enhancements ✅ PARTIALLY COMPLETED

- [ ] **Testing**: Add `pytest` integration tests for each phase using fixtures (no GPT/TTS calls)
  - **Status**: Pytest framework established with comprehensive fixtures in `conftest.py`
  - **Phase Tests**: Basic phase test files exist but marked as legacy/skipped
  - **Missing**: Integration tests specifically for current `scripts/run_*.py` phase scripts
- [x] **Web UI Integration**: Web UI integration refactoring to use phase scripts
  - **Status**: ✅ Web UI properly integrates with orchestrator architecture
  - **Full Pipeline**: Uses `run_full_pipeline_orchestrator.py` which calls all phase scripts including publishing
  - **Publishing Only**: Provides separate publishing-only option via `scripts/run_publishing.py` for maintenance/repair scenarios
  - **Architecture**: Orchestrator includes publishing as final phase (line 322), Web UI offers both full pipeline and standalone publishing

## Phase 3.5 — AI Token Configuration Management ✅ COMPLETED

**REALITY CHECK**: Comprehensive AI token configuration already fully implemented in Web UI:

- ✅ **Scoring Configuration**:
  - Content scoring model selection, max output/input tokens, batch processing limits
- ✅ **Digest Generation Configuration**:
  - Model selection, max output/input tokens for script generation
- ✅ **Metadata Generation Configuration**:
  - Model selection, max title/summary/description tokens, input token limits
- ✅ **TTS Configuration**:
  - ElevenLabs model selection, max character limits per generation
- ✅ **STT Configuration**:
  - Whisper model selection, max file size limits
- ✅ **Pipeline Processing Configuration**:
  - Max episodes per run, score thresholds, processing limits

**Implementation Status**:
- ✅ **Web UI Settings Page**: Complete AI configuration section with model selection and token controls
- ✅ **Database Integration**: All settings persist via `web_settings` table and WebConfig system
- ✅ **Service Integration**: All AI services read token limits from WebConfig with validation
- ✅ **Intelligent Validation**: Auto-adjustment against model capabilities with tooltips
- ✅ **Token Usage Logging**: All OpenAI API calls now log actual token consumption
- ✅ **Pipeline Limits**: Discovery, scoring, digest, TTS phases respect configurable limits

**Additional Enhancement Completed**:
- ✅ **Token Usage Monitoring**: Added detailed token logging to all OpenAI API calls for cost tracking

## Phase 4 — CI/CD ✅ COMPLETED

- ✅ **Full Pipeline Operational**: Complete orchestrated workflow via `.github/workflows/phase-tts.yml`
  - ✅ All phases: Discovery → Audio → Scoring → Digest → TTS → Publishing
  - ✅ **Scheduled Execution**: Daily at 5:00 AM UTC via cron
  - ✅ **Manual Dispatch**: Available with configurable inputs (limit, days_back, dry_run)
  - ✅ **Environment Variable Fix**: Resolved `GH_REPOSITORY` → `GITHUB_REPOSITORY` workflow error
  - ✅ **Database Repair**: Auto-detection and repair of UNPUBLISHED digests with existing GitHub releases
- ✅ **Web UI Integration**: Complete CI controls in main dashboard
  - ✅ "Run Full Pipeline" button triggers orchestrated workflow
  - ✅ Live status streaming with phase indicators and real-time logs
  - ✅ System health monitoring and artifact management
- ✅ **Token Usage Monitoring**: All OpenAI API calls log detailed usage information
- ✅ **Publishing Architecture**: TTS uploads MP3s → Publishing generates RSS → Vercel auto-deploys
- ✅ **Error Recovery**: Graceful handling of workflow failures with database consistency
- ✅ **GitHub Secrets**: All required secrets configured and validated via bootstrap workflow

**Acceptance Criteria Status**:
- ✅ **Manual Dispatch**: Works via Web UI and GitHub Actions interface
- ✅ **Scheduled Execution**: Daily runs producing RSS and artifacts automatically
- ✅ **Monitoring**: Live logs, system health, downloadable artifacts available
- ✅ **RSS Generation**: Automatic RSS updates with 32 episodes published successfully

## Phase 5 — Web UI Hosting + DNS ✅ SUBSTANTIALLY COMPLETE

- ✅ **Next.js/Vercel Deployment**: Complete hosted admin UI at `podcast.paulrbrown.org`
  - ✅ Next.js 14 + TypeScript + TailwindCSS app deployed to Vercel
  - ✅ Supabase connectivity via DatabaseClient with pooled connections
  - ✅ **Complete CRUD interfaces**: 6/8 pages implemented (Dashboard, Feeds, Topics, Script Lab, Episodes, Settings)
  - ✅ Real-time status monitoring and health checks
  - ✅ Professional card-based UI with proper loading states and error handling
- ✅ **RSS Feed Hosting**: Canonical RSS now served from Vercel
  - ✅ Publishing pipeline writes to `web_ui_hosted/public/daily-digest.xml`
  - ✅ Vercel auto-deploys RSS updates from GitHub pushes
  - ✅ All recent MP3s properly served with correct metadata
- ✅ **GitHub Workflow Dispatch Integration**: Complete UI buttons to trigger pipeline runs
  - ✅ Real GitHub Actions API integration with workflow triggers
  - ✅ Live status monitoring with auto-refresh and manual refresh button
  - ✅ Working "Run Full Pipeline" and "Publishing Only" buttons
  - ✅ Real-time workflow activity display with status icons
  - ✅ Enhanced logs page with cache-busting and real-time job progress
  - ✅ Database integration for episode counts and processing stats
- ✅ **Settings Management**: Complete settings functionality with manual save UX
  - ✅ **Fixed settings saving**: Manual save/reset buttons with proper database persistence
  - ✅ **Enhanced UX**: Replaced aggressive auto-save with user-controlled save operations
  - ✅ AI Content Scoring: model selection, token limits, batch processing controls
  - ✅ AI Digest Generation: model, output/input tokens, transcript buffer settings
  - ✅ AI Metadata Generation: model, title/summary/description token limits
  - ✅ AI TTS Generation: ElevenLabs model selection, character limits
  - ✅ AI STT Transcription: Whisper model selection, file size limits
  - ✅ Transcript Processing: max length, chunk overlap configuration
- ✅ **Complete Page Implementation**:
  - ✅ **Topics page**: Full topic management with Supabase-backed voice and instruction editing
  - ✅ **Script Lab page**: Digest generation testing with Supabase instructions and preview
  - ✅ **Episodes page**: Complete episode browsing, filtering, and digest inclusion badges
  - ✅ **Feeds page**: Enhanced with latest episode data and comprehensive feed management
  - ✅ **Publishing page**: GitHub releases and RSS publishing management dashboard
  - ✅ **Maintenance page**: System maintenance tools with pipeline runs and GitHub activity
  - ✅ **Enhanced navigation**: All pages properly linked in responsive navigation

**Current Status**: Phase 5 complete – hosted UI achieves feature parity with Supabase data

Acceptance criteria
- ✅ Vercel UI loads and shows status from Supabase
- ✅ **Settings and Feeds CRUD**: Complete functionality with manual save UX and latest episode data
- ✅ RSS accessible at canonical URL with working enclosure links
- ✅ Workflow dispatch integration from UI working in production
- ✅ **Major feature parity**: 8/8 pages migrated from legacy Flask UI
- ✅ Live GitHub Actions status monitoring with enhanced refresh capabilities
- ✅ Playwright smoke suite validates Dashboard, Topics, Publishing, Maintenance, Script Lab, Navigation on Vercel/production
- ⚠️ Basic authentication protection (deferred to Phase 7 - not critical for current functionality)

## Phase 6 — Local Dev Parity and Testing

- [ ] Playwright UI tests adapted to run in CI against hosted or local server. *(Smokes running manually; next step is CI integration.)*
- [ ] Provide `scripts/run_web_ui.sh` support for prod‑like `.env` and port override.
- [ ] `scripts/bootstrap_local.sh` to set `.env` with `DATABASE_URL`, verify Supabase connectivity, fetch recent logs (Artifacts) and optionally last N MP3s (from Releases) for debugging.
- [ ] Document Makefile targets or `scripts/*` commands for common flows:
  - `make test`, `make lint`, `make ci-local`, `make run-publish`, `make run-full`.

Acceptance criteria
- Dev can run single phases locally in minutes without incurring cloud costs.
- UI tests green locally and in CI.

## Phase 6.5 — Database Retention and Cleanup System ⚠️ IN PROGRESS

**Goal**: Implement automated database cleanup to prevent database bloat and manage episode/digest lifecycle.

### **Implementation Status**:
- ✅ **WebConfig Settings**: Added `episode_retention_days` (default 14) and `digest_retention_days` (default 14) to replace obsolete file-based retention settings
- ✅ **Retention Strategy Research**:
  - Episodes deleted by `updated_at` field (gets updated during processing phases)
  - Digests deleted by `generated_at` field
  - Legacy transcript files cleaned up (now stored in database `transcript_content` column)
- 🔄 **RetentionManager Updates**:
  - ✅ Removed obsolete policies (local MP3s, audio cache/chunks - handled by audio phase)
  - ✅ Updated CleanupStats to track database deletions
  - 🔄 Adding `_cleanup_database_records()` method for episode and digest cleanup
- ⏳ **Discovery Integration**: Move retention cleanup from end-of-pipeline to beginning of discovery phase
- ⏳ **Settings UI Validation**: Auto-adjust retention days if `discovery_lookback_days >= episode_retention_days`

### **Technical Implementation**:
- **Database Cleanup**: Delete episodes where `updated_at < (now - retention_days)` and digests where `generated_at < (now - retention_days)`
- **Pipeline Integration**: Retention runs first in discovery phase so old records don't interfere with processing
- **Validation Logic**: Ensure `discovery_lookback_days < episode_retention_days` with automatic adjustment in UI
- **File Cleanup**: Clean up legacy transcript files while preserving database-stored transcripts

### **Remaining Work**:
- [ ] Complete `_cleanup_database_records()` implementation with database imports and deletion logic
- [ ] Update `_merge_stats()` to handle new episode/digest deletion counts
- [ ] Move retention execution from end-of-pipeline to beginning of discovery phase
- [ ] Add settings UI validation and auto-adjustment logic
- [ ] Test integration with existing retention policies (logs, GitHub releases)

Acceptance criteria
- Database automatically cleans up old episodes and digests based on configurable retention periods
- Discovery lookback period validation prevents rediscovering recently deleted episodes
- Legacy transcript files cleaned up while preserving database-stored content
- Retention cleanup runs efficiently at start of discovery phase

## Phase 6.6 — Analytics & Metrics Dashboard

- [ ] **Analytics Page in Web UI**: Create comprehensive analytics dashboard for feed processing pipeline
  - **Feed Performance Metrics**: Episodes processed, success rates, relevance rates by feed
  - **Episode Status Distribution**: Breakdown by status (pending, transcribed, scored, digested, not_relevant, failed)
  - **Topic Coverage Analysis**: Which topics are getting the most qualifying episodes
  - **Processing Pipeline Statistics**: Average processing times, failure rates, bottlenecks
  - **Feed Quality Assessment**: Identify feeds with high 'not_relevant' rates for potential deactivation
  - **Historical Trends**: Charts showing processing volume and quality over time
- [ ] **Relevance Tracking**: Monitor feeds that consistently produce irrelevant content
  - Track percentage of episodes marked as 'not_relevant' by feed
  - Alert when feeds exceed threshold (e.g., >80% not_relevant over 30 days)
  - Provide recommendations for feed deactivation based on performance data

Acceptance criteria
- Analytics dashboard shows real-time feed performance and processing metrics
- Clear visibility into which feeds are producing relevant vs irrelevant content
- Historical trend analysis for feed quality assessment

## Phase 6.6 — Topic-Specific RSS Feeds

- [ ] **Multi-Feed RSS Architecture**: Replace single `daily-digest.xml` with topic-specific feeds
  - **Individual Topic Feeds**: Generate separate RSS feeds for each topic (e.g., `tech-digest.xml`, `organizing-digest.xml`)
  - **Feed Discovery**: Create master index page listing all available topic feeds
  - **RSS Metadata**: Ensure each topic feed has proper podcast metadata (title, description, artwork)
  - **URL Structure**: Organize feeds at `/feeds/{topic-slug}.xml` for clean URLs
  - **Backward Compatibility**: Consider maintaining legacy `daily-digest.xml` as aggregate feed or redirect
- [ ] **Publishing Pipeline Updates**: Modify publishing logic to generate multiple RSS files
  - Update RSS generation to create per-topic files instead of single aggregate
  - Ensure proper enclosure URLs pointing to topic-specific MP3s
  - Update Vercel deployment to serve multiple feed files
  - Test RSS feeds in podcast clients for proper topic separation

Acceptance criteria
- Each topic has its own dedicated RSS feed with appropriate metadata
- Podcast clients can subscribe to individual topics separately
- RSS feeds validate against podcast standards and work in major podcast apps

## Phase 7 — Rollout and Hardening

- [ ] Staging dry‑runs: schedule job against non‑prod storage (or with `--dry-run`).
- [ ] Backups and retention checked; restore drills for DB and audio.
- [ ] Observability: basic metrics (run duration, items processed), error reporting (Sentry optional).
- [ ] Runbook: failure modes, re‑runs, manual publish steps, data repair scripts.

Acceptance criteria
- First week of scheduled runs complete with no manual intervention.

## Deliverables Checklist

- [ ] `.env.sample` and secrets documented.
- [ ] Storage sync scripts and retention policies.
- [ ] Modular pipeline CLI and flags.
- [ ] CI (`ci.yml`) for PRs and schedule (`publish.yml`) for daily runs.
- [ ] Web UI deployed and DNS configured to `podcast.paulrbrown.org` (or split with `admin.`).
- [ ] STT provider abstraction and OpenAI Whisper implementation.
- [ ] Docs: this plan, OPERATIONS.md (runbook), and quickstart for local dev.

## Notes and Tradeoffs

- Vercel Cron is great for "poke a webhook" jobs, not long audio/LLM work. Use GitHub Actions or a long‑lived host for the heavy lifting.
- GitHub Releases as audio storage works surprisingly well for small/medium catalogs but gets clunky at scale. S3/Backblaze is a smoother long‑term path.
- Supabase provides a shared Postgres DB for CI and UI, avoiding artifact shuttling and simplifying CRUD. Alembic migrations and connection pooling become part of ops.
- Do not commit MP3s into the repo; use GitHub Releases for public audio URLs without extra infra.

## Open Questions

- Confirm: Use GitHub Releases for public MP3 URLs and also upload a 7‑day audio bundle as an Artifact backup.
- Provide Supabase connection details: `DATABASE_URL` for CI/Vercel and `SUPABASE_POOL_URL` if available; confirm RLS policy approach (on/off for server-side use).
- For STT, is the priority speed, cost ceiling, or accuracy parity with current Parakeet output?
