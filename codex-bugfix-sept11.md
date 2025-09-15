Codex Bugfix Summary — Sept 11

Scope: Align codebase with RSS-first architecture, improve robustness, and smooth over legacy YouTube test hooks. Includes six fixes (3 high-priority, 3 lower-priority).

High-Priority Fixes
- Align DB init with RSS schema
  - File: `src/database/init_db.py`
  - Changes: Removed channel repo usage; now validates `feeds`, `episodes`, `digests`, `system_metadata`. Switched to `get_feed_repo` and `get_podcast_episode_repo`. Logs updated to report active feeds.

- Unify episode access on RSS repos and provide scored-episodes query
  - Files: `src/podcast/rss_models.py`, `src/generation/script_generator.py`
  - Changes: Added `get_scored_episodes_for_topic(...)` to `PodcastEpisodeRepository` (SQLite JSON extract). Switched `ScriptGenerator` to use `get_podcast_episode_repo` and standardized OpenAI client import.

- Harden RSS date parsing (no private APIs)
  - File: `src/podcast/feed_parser.py`
  - Changes: Replaced `feedparser._parse_date` fallback with `email.utils.parsedate_to_datetime`, normalizing to UTC. Avoids reliance on private feedparser internals.

Lower-Priority Fixes
- OpenAI client usage consistency in generation
  - File: `src/generation/script_generator.py`
  - Changes: Use `from openai import OpenAI`; keep Responses API with `client.responses.create` for GPT-5.

- Add YouTube resolver shims for legacy tests/callers
  - File: `src/youtube/channel_resolver.py`
  - Changes: Added module-level helpers `resolve_channel(...)` and `validate_channel_id(...)` that proxy to `ChannelResolver`. This keeps YouTube-related tests/imports working without re-enabling YouTube pipeline.

- Make config path resolution robust to CWD
  - File: `src/config/config_manager.py`
  - Changes: Default `config_dir` now resolves relative to project root (`.../config`) instead of CWD to prevent misloads.

Notes
- No behavioral changes to publishing, scoring logic, or audio beyond repository selection and robustness improvements.
- README did not require changes because `src/database/init_db.py` now aligns with the RSS schema and runs successfully.

Files Changed
- M `src/database/init_db.py`
- M `src/podcast/rss_models.py`
- M `src/generation/script_generator.py`
- M `src/podcast/feed_parser.py`
- M `src/youtube/channel_resolver.py`
- M `src/config/config_manager.py`

Validation
- DB init now checks/uses feeds/episodes/digests and repo creation works.
- Episode selection for script gen pulls from RSS repo via JSON score filtering.
- RSS parsing handles varied date formats without private APIs.
- Legacy YouTube test imports succeed via shims.

---

Follow‑up Updates (later Sep 11)

Standardize canonical RSS to daily-digest.xml
- vercel.json: switched headers to `/daily-digest.xml` and added a permanent redirect from `/daily-digest2.xml` to `/daily-digest.xml`.
- src/publishing/vercel_deployer.py: writes `public/daily-digest.xml`, updates links/validation to canonical URL.
- run_publishing_pipeline.py and run_full_pipeline.py: write RSS to `public/daily-digest.xml` after generation so Vercel auto-serves the latest.
- README.md, podscrape2-prd.md, public/index.html: updated references to canonical feed.

Deduplicate MP3 path resolution and fix publishing misses
- src/audio/audio_manager.py: added `resolve_existing_mp3_path(...)` utility.
- run_full_pipeline.py and run_publishing_pipeline.py: use the shared resolver and persist normalized absolute `mp3_path` to DB.
- src/publishing/github_publisher.py: when a daily release already exists, upload any missing MP3 assets and refresh release data to prevent 404s.

Eliminate divergence and harden hand‑offs
- run_full_pipeline.py: Phase 7 now hands off to `PublishingPipelineRunner` (with fallback) to keep one publishing path.
- Added `RetentionManager.cleanup_all(...)` alias to match orchestration calls.

Fixes for regressions and quick QA checks
- Fixed indentation error in `run_full_pipeline.py` under `if vercel_deployed`.
- Added quick local validation steps (used during this patch cycle):
  - Python syntax check: `py_compile` on modified Python files (passed).
  - Live RSS checks: `curl` 200 for `/daily-digest.xml` and validator returned True.
  - Enclosure URLs: verified GitHub assets return 302 to CDN (no 404s).

New docs and task management
- Added `tasklist2.md` (Phases A–F) for Web UI + automation work.
- Renamed `tasklist.md` → `completed-phases1-7.md`; updated README and PRD references.

Contact metadata correction
- Updated contact email used in generated RSS metadata from `paul@paulrbrown.org` to `brownpr0@gmail.com` across code and public feed.

Net effect
- Canonical feed served at `/daily-digest.xml` with redirect in place.
- Publishing pipeline uploads missing assets to existing releases (fixes podcast client download failures).
- Reduced duplication (shared MP3 resolver, publishing hand‑off), improved reliability.

---

Session Addendum (Web UI + Tests + Ops), Sept 11–12

Optional Web UI (Phase A)
- Added DB‑backed settings manager and UI:
  - Files: `src/config/web_config.py`, `web_ui/app.py`, `web_ui/templates/{base,dashboard,settings}.html`.
  - Settings (persisted in `web_settings`):
    - `content_filtering.score_threshold` (float)
    - `content_filtering.max_episodes_per_digest` (int)
    - `audio_processing.chunk_duration_minutes` (int)
  - ConfigManager optionally reads score threshold from WebConfig.
  - ScriptGenerator caps topic episodes using `max_episodes_per_digest`.
  - New launcher: `scripts/run_web_ui.sh` (creates venv, installs deps, kills existing port, starts on 127.0.0.1:5001; supports `PORT=5002`).

Playwright UI tests (optional)
- Added a minimal Playwright test harness to validate the UI:
  - Files: `ui-tests/package.json`, `ui-tests/playwright.config.ts`, `ui-tests/tests/web-ui.spec.ts`.
  - Test: opens `/` and `/settings`, updates values, verifies success banner and dashboard reflection.

Operational fixes & quality of life
- Requirements cleanup: removed `sqlite3` (stdlib) from `requirements.txt`; added `Flask` for Web UI.
- Web UI startup improvements:
  - `web_ui/app.py` prints explicit instructions if Flask is missing.
  - `scripts/run_web_ui.sh` now kills existing process on the port before starting.
  - `web_ui/app.py` accepts `--port`.
- Publishing hardening:
  - GH CLI fallback refined (auth detection, correct JSON fields) for 401/no token cases.
  - REST remains preferred when `GITHUB_TOKEN` is available.
- Contact metadata: changed RSS email to `brownpr0@gmail.com` across pipeline and public feed.

Verification performed
- Web UI endpoints validated via Flask test client and Playwright (1 test passed).
- Publishing cycle re‑run with a 12‑minute timeout using existing MP3s only:
  - RSS generated, public feed updated and deployed to Vercel.
  - Live canonical feed shows 6 items.

How to run (post‑context reset)
- Environment
  - Python 3.9+; create venv: `python3 -m venv .venv && source .venv/bin/activate`.
  - Install: `python3 -m pip install -r requirements.txt`.
  - Env vars: set `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`, `GITHUB_TOKEN` (or authenticate GH CLI), `GITHUB_REPOSITORY`.
- Database
  - Already initialized under `data/database/digest.db`.
  - Only run `python src/database/init_db.py` if starting from scratch or to reset (`--reset`).
- Web UI (optional)
  - `bash scripts/run_web_ui.sh` (or `PORT=5002 bash scripts/run_web_ui.sh`).
  - Visit `http://127.0.0.1:5001` and edit settings.
- Playwright tests (optional)
  - In one terminal, run the Web UI.
  - In `ui-tests/`: `npm install && npx playwright install && npx playwright test`.
- Publishing (no GPT/TTS costs)
  - `timeout 12m python3 run_publishing_pipeline.py -v` (uses existing MP3 files).
  - Verify: `https://podcast.paulrbrown.org/daily-digest.xml` is HTTP 200 and shows latest items.

Notes on `/init`
- No special `/init` is required for the app; the DB is auto‑initialized if missing.
- Run `src/database/init_db.py` only when you need to create/reset the database schema.
