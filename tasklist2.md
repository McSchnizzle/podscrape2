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

Status: Completed
- Implemented Flask UI skeleton with Tailwind/Alpine.
- DB‑backed WebConfig with typed settings (thresholds, chunking, caps).
- Settings wired into pipeline components (ConfigManager, transcriber, generator).

## Phase B: Feed & Topic Management
- Feeds UI: list/add/remove/activate/deactivate feeds (DB-backed)
- Topics UI: list/edit topics and voice settings (validates instruction files exist)
- Persist changes to DB/JSON as appropriate and reflect in pipeline

Deliverables:
- `routes/feeds.py`, `routes/topics.py`, `templates/feeds.html`, `templates/topics.html`
- Validation: file existence, voice ID sanity checks

Status: Completed
- Feeds UI: list, add (URL validation + duplicate guard + title autofill), activate/deactivate, soft delete, and “Check” (TLS + enclosure reachability). Grouped RSS vs YouTube; latest episode/date per RSS feed.
- Topics UI: edit voice_id, instruction_file (upload/validate), description, active. Persist via `ConfigManager.save_topics()`.
- Config: added `get_all_topics()` + `save_topics()`; Topics load/save robust to CWD.

## Phase C1: Pipeline Controls & Monitoring
- Dashboard: recent episodes, digests, status (counts, last run time)
- Controls: run pipeline (manual), retry failed episodes, view/download latest logs
- Health: show env/key status, ffmpeg availability, disk usage

Deliverables:
- `routes/dashboard.py`, `routes/system.py`
- Log streaming endpoint for latest logfile

Status: Completed
- Dashboard controls to run publishing/full pipeline; retry failed episodes.
- Latest log tail endpoint; removed creation of separate publishing log files.
- Feed/episode association fixes: correct `feed_id` on insert; one‑time repair based on transcript headers.
 - Live Status: Server‑Sent Events (SSE) log streaming with phase badges (Discovery → Publishing) and auto‑start when launching runs.
 - System Health panel: checks ffmpeg, gh CLI + auth, parakeet‑mlx availability, and presence of required API keys/tokens.

## Phase C2: Dashboard Enhancements (Observability)
- Show key settings on dashboard (not just in Settings):
  - content_filtering.score_threshold, content_filtering.max_episodes_per_digest
  - audio_processing.chunk_duration_minutes, audio_processing.transcribe_all_chunks, audio_processing.max_chunks_per_episode
- Last run summary:
  - Last pipeline run timestamp, duration, exit status
  - Counters for last run window: episodes discovered, transcribed, scored, digested
  - Link to last log file and to publishing log when applicable
- RSS currently published:
  - Parse `public/daily-digest.xml` and list N most recent items (title, date, duration, mp3 link)
  - Surface when canonical RSS missing or unreadable
- Transcribed but not yet digested:
  - DB query for episodes with status 'transcribed' (or scored) not marked 'digested'
  - Show feed title, episode title, published date, and quick link to view details
- UI polish:
  - Add pagination or "show more" for long lists; default N = 5–10 per section
  - Consistent empty-state banners and quick links to actions (e.g., run pipeline)

Deliverables:
- Extend `/` route and `dashboard.html` to render sections above
- Utility to read last pipeline log metadata (mtime, size, tail of errors)
- Helper to parse RSS safely with error banners
- Tests: lightweight Playwright smoke for presence of each section when data exists

Status: Completed
- Settings mirrored on dashboard; RSS items (6) from `public/daily-digest.xml`.
- Last Run distilled from DB (recent scored episodes with correct feed + qualifying topics) and latest digests (topics, episode titles, MP3 durations). Fallback away from brittle log parsing.
- “Transcribed not yet digested” section lists accurate feed names; repairs legacy mis‑associations.
- Episodes used in digests are marked 'digested' post‑publish to prevent reuse.
- Playwright coverage: dashboard sections + feed‑name variety check; feeds/topics flows.
 - Added “Max episodes per run” (pipeline) setting; runner uses it for discovery.
 - Immediate archive of digested transcripts: after digest creation, mark episodes 'digested' and move transcripts to `digested/` folder; DB path updated. One‑click maintenance: “Archive Digested Transcripts”.

## Phase D: Publishing & Retention (UI + Backing)
- Publishing UI: list digests with MP3 paths, publish/unpublish to GitHub
- Asset status: mark and upload missing assets to existing releases (uses current GitHubPublisher improvements)
- Retention: configure retention days; dry-run previews; run cleanup

Deliverables:
- `routes/publishing.py`, `templates/publishing.html`
- Wire to `GitHubPublisher`, `RetentionManager`

Status: In Progress
- Completed
  - Publishing runner: "ensure assets" for daily releases (upload missing assets), with REST→GH CLI fallback and post‑upload asset listing.
  - Full pipeline: final verification logs GitHub release assets for today's tag.
  - Web UI Maintenance: "Repair Publishing (Ensure Assets)" button with streaming logs (auto opens in Live Status).
  - Removed separate publishing log files; publishing logs to console/Live Status.
- Remaining
  - /publishing UI page
    - List digests (date, topic) with MP3 metadata (filename, size, duration) and links (local path, GitHub release asset).
    - Asset status column (Present/Missing), "Re‑upload missing" action per‑row and bulk.
    - Publish/Unpublish toggles (Unpublish: remove asset from release and clear DB URL; Publish: attach asset and set URL).
    - Date filter and pagination; link to RSS entry if present.
  - Retention controls UI
    - Configure keep days per asset class (logs, scripts, local MP3s, old releases – if scoped) and save in settings.
    - Dry‑run preview (counts + bytes to delete) and run cleanup; stream results to Live Status.
  - Tests
    - Playwright coverage for listing, status badges, publish/unpublish flows, and retention dry‑run confirmation.
  - Optional (nice‑to‑have)
    - Per‑phase timings surfaced in Last Run.
    - One‑line publishing status on dashboard.

## Phase E: Automation & Orchestration (Phase 8)
- Orchestrator: Monday 72hr vs weekday 24hr lookback
- Manual trigger support for specific dates (catch-up)
- Weekly summaries (Fridays) aggregating digested transcripts by topic
- Cron/scheduler integration (APScheduler)
- Error handling, retry strategies, and status surfacing in UI
- Reduce log volume: decrease full pipeline log output by ~50% while retaining critical milestones and errors

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
## Phase B2: Topics Editor Enhancements (Future)
- Bulk add/remove topics and reordering via drag-and-drop.
- Inline validation for voice IDs and instruction file existence with per-row status.
- Preview instruction files with markdown rendering and quick open in editor.
- Duplicate-name detection and friendly rename flow.
- Import/export topics JSON from the UI with schema validation.
