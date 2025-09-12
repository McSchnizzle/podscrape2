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

Net effect
- Canonical feed served at `/daily-digest.xml` with redirect in place.
- Publishing pipeline uploads missing assets to existing releases (fixes podcast client download failures).
- Reduced duplication (shared MP3 resolver, publishing hand‑off), improved reliability.
