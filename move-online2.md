# Move Online - Phase 2 (Remaining Tasks)

**Pending work to complete the move to online infrastructure**

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

## Phase 3.5 — AI Token Configuration Management **[🆕 NEW REQUIREMENT]**

**Add comprehensive AI token limit controls to Web UI for all AI interactions:**

- [ ] **Scoring Configuration**:
  - `ai_scoring.max_tokens_per_request` (current: ~1000 tokens for GPT-5-mini scoring)
  - `ai_scoring.max_episodes_per_batch` (batch processing limits)
- [ ] **Digest Generation Configuration**:
  - `digest_generation.max_output_tokens` (current: ~25,000 word limit per script)
  - `digest_generation.max_input_tokens` (episode transcript limits)
- [ ] **TTS Phase Configuration**:
  - `tts_generation.max_title_tokens` (episode title generation via GPT-5-nano)
  - `tts_generation.max_summary_tokens` (episode summary generation)
- [ ] **Metadata Generation Configuration**:
  - `metadata.max_description_tokens` (RSS episode descriptions)
  - `metadata.max_topic_analysis_tokens` (topic relevance analysis)

**Implementation Tasks**:
- [ ] Audit all AI API calls across the codebase to identify max_tokens parameters
- [ ] Add `ai_configuration` section to `web_settings` database table
- [ ] Create Web UI settings page for AI token configuration
- [ ] Update all AI service classes to read token limits from WebConfig
- [ ] Add validation and reasonable defaults for all token settings
- [ ] Document token usage implications (cost, quality, performance trade-offs)

**Acceptance Criteria**:
- All AI interactions have configurable token limits via Web UI
- Settings persist in database and affect pipeline execution
- Clear documentation of token usage implications
- Validation prevents unreasonably high/low token limits

## Phase 4 — CI/CD **[✅ READY - Phase 2.5 STT Migration Complete]**

- [ ] `ci.yml` (PRs):
  - Lint (Black/Flake8), type check (MyPy), unit/integration tests.
  - Optionally run Playwright UI tests against the Flask server with seeded DB.
- [ ] `publish.yml` (schedule):
  - Trigger daily on cron (UTC); concurrency: cancel in‑progress on new schedule.
  - Steps: checkout; setup Python; set `DATABASE_URL` secret; run Alembic migrations; run `run_full_pipeline.py --log ...` or staged commands; upload logs and `pg_dump` as Artifacts with `retention-days: 7`; commit/push `public/` changes; create/update a daily GitHub Release with MP3 assets; delete Releases older than 7 days; post job summary with links to Release assets and RSS.
- [ ] Configure Secrets in GitHub: `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`, `GH_TOKEN` (fine‑grained), any storage keys.
- [ ] Add failure notifications (GitHub notifications, optional Slack/Email).

Acceptance criteria
- Manual "Dispatch" works; scheduled run produces RSS and artifacts.
- Logs and DB available as downloadable artifacts; RSS diff is in commit/PR.

## Phase 5 — Web UI Hosting + DNS

- [ ] Deploy the admin/status UI to Vercel:
  - Connect directly to Supabase for CRUD (Feeds, Topics, Episode status, Retention settings) via pooled connections.
  - Continue to use GitHub Workflow Dispatch for heavy actions (e.g., re-run pipeline) to keep serverless fast.
  - Apply minimal auth: password via `WEBUI_SECRET` or GitHub OAuth; consider RLS policies for write endpoints.
- [ ] DNS: point `podcast.paulrbrown.org` to Vercel; serve `public/daily-digest.xml` and the UI under the same domain.

Acceptance criteria
- Vercel UI loads, shows status from Postgres, allows CRUD where appropriate, and can dispatch runs. RSS accessible at canonical URL; enclosure links work in podcast clients.

## Phase 6 — Local Dev Parity and Testing

- [ ] Playwright UI tests adapted to run in CI against hosted or local server.
- [ ] Provide `scripts/run_web_ui.sh` support for prod‑like `.env` and port override.
- [ ] `scripts/bootstrap_local.sh` to set `.env` with `DATABASE_URL`, verify Supabase connectivity, fetch recent logs (Artifacts) and optionally last N MP3s (from Releases) for debugging.
- [ ] Document Makefile targets or `scripts/*` commands for common flows:
  - `make test`, `make lint`, `make ci-local`, `make run-publish`, `make run-full`.

Acceptance criteria
- Dev can run single phases locally in minutes without incurring cloud costs.
- UI tests green locally and in CI.

## Phase 6.5 — Analytics & Metrics Dashboard

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