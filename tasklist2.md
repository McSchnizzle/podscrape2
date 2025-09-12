# RSS Podcast Transcript Digest System — Remaining Work (Phases A–F)

Project focus: Complete automation (Phase 8), add a local Web UI for settings and operations, and harden publishing and ops. This supersedes open items from completed-phases1-7.md.

## Phase A: Web UI Core (Config Backbone)
- Scaffold Flask app (`web_ui/`) with TailwindCSS + Alpine.js
- Add `web_settings` table and `WebConfigManager` with type validation (string/int/float/bool/json)
- Migrate key settings into web settings (score_threshold, max_episodes_per_digest, chunk_duration_minutes)
- Inject `WebConfigManager` into:
  - `ConfigManager.get_score_threshold`
  - `ParakeetTranscriber` (chunk_duration_minutes)
  - `ScriptGenerator` (max_episodes, limits)

Deliverables:
- `web_ui/app.py`, `routes/`, `templates/`, `models/settings.py`
- Migration script to seed settings from JSON config

## Phase B: Feed & Topic Management
- Feeds UI: list/add/remove/activate/deactivate feeds (DB-backed)
- Topics UI: list/edit topics and voice settings (validates instruction files exist)
- Persist changes to DB/JSON as appropriate and reflect in pipeline

Deliverables:
- `routes/feeds.py`, `routes/topics.py`, `templates/feeds.html`, `templates/topics.html`
- Validation: file existence, voice ID sanity checks

## Phase C: Pipeline Controls & Monitoring
- Dashboard: recent episodes, digests, status (counts, last run time)
- Controls: run pipeline (manual), retry failed episodes, view/download latest logs
- Health: show env/key status, ffmpeg availability, disk usage

Deliverables:
- `routes/dashboard.py`, `routes/system.py`
- Log streaming endpoint for latest logfile

## Phase D: Publishing & Retention (UI + Backing)
- Publishing UI: list digests with MP3 paths, publish/unpublish to GitHub
- Asset status: mark and upload missing assets to existing releases (uses current GitHubPublisher improvements)
- Retention: configure retention days; dry-run previews; run cleanup

Deliverables:
- `routes/publishing.py`, `templates/publishing.html`
- Wire to `GitHubPublisher`, `RetentionManager`

## Phase E: Automation & Orchestration (Phase 8)
- Orchestrator: Monday 72hr vs weekday 24hr lookback
- Manual trigger support for specific dates (catch-up)
- Weekly summaries (Fridays) aggregating digested transcripts by topic
- Cron/scheduler integration (APScheduler)
- Error handling, retry strategies, and status surfacing in UI

Deliverables:
- `orchestrator.py` or augment `run_full_pipeline.py` with date-window logic
- Weekly summary generator (topic-based aggregation)

## Phase F: Ops Hardening & Docs
- GitHub auth: prefer GH CLI if available; fallback to token (document clearly)
- End-to-end tests for automation & publishing
- Documentation refresh: install, run, UI guide, ops playbook

Open Items migrated from completed-phases1-7.md
- Phase 7 (Publishing):
  - Resolve GitHub API permission variance: add GH CLI-first publish path (done partially via tooling), document fallback with PAT
- Phase 8 (Automation):
  - Build orchestrator (lookback logic)
  - Weekly summaries
  - Cron/CI scheduling and docs
  - Full end-to-end automation test

