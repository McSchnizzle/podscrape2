# Complete Hosted Migration Plan

## Purpose
Create a single roadmap for finishing the GitHub + Vercel + Supabase migration. This plan stems from the audit findings, `move-online2.md`, `phase5-tasklist.md`, and `gh-publishing-workflow-learnings.md`, and it targets the seven open issues called out on 2025-09-20.

## Current Gaps Snapshot (2025-09-20)
- [x] Hosted Topics & Script Lab now save to Supabase (`topics`, `topic_instruction_versions`); filesystem files kept as legacy read-only.
- [x] Pipeline config reads multi-topic metadata from Supabase; orchestrator logs runs to `pipeline_runs`.
- [x] Episodes API surfaces digest membership via `digest_episode_links` so UI can show feed/digest attribution.
- [x] `validated-full-pipeline.yml` receives `PIPELINE_RUN_ID` and orchestrator updates Supabase for live monitoring.
- [x] Hosted dashboard/activity components consume Supabase + GitHub data; workflow labels align with “Run Validated Pipeline”.
- [x] Publishing & Maintenance pages reimplemented in Next.js using Supabase data and GitHub dispatch APIs.
- [x] README/PRD/Operations updated for hosted-first workflow and Supabase migration steps.
- [ ] Automated caching strategy and Playwright smoke suite still pending.

## Supabase Schema Additions & Changes
1. `topics`
   - Columns: `id SERIAL PK`, `slug TEXT UNIQUE`, `name TEXT`, `description TEXT`, `voice_id TEXT`, `voice_settings JSONB`, `instructions_md TEXT`, `is_active BOOLEAN`, `sort_order INT`, `created_at TIMESTAMPTZ`, `updated_at TIMESTAMPTZ`, `last_generated_at TIMESTAMPTZ`.
   - Purpose: Single source of truth for topic metadata, voice configuration, and current instructions.
2. `topic_instruction_versions`
   - Columns: `id SERIAL PK`, `topic_id INT FK`, `version INT`, `instructions_md TEXT`, `change_note TEXT`, `created_at TIMESTAMPTZ`, `created_by TEXT`.
   - Purpose: Optional history + rollback for Script Lab edits; REST API can cap history if storage is a concern.
3. `web_settings`
   - Validate actual schema in Supabase; if missing, create via migration with columns (`id`, `category`, `setting_key`, `setting_value`, `value_type`, `description`, timestamps) to match `WebConfigManager`.
   - Add composite unique constraint `(category, setting_key)` enforced at DB level.
4. `digest_episode_links`
   - Columns: `id SERIAL PK`, `digest_id INT FK`, `episode_id INT FK`, `topic TEXT`, `score NUMERIC`, `position INT`, `created_at TIMESTAMPTZ`.
   - Replaces JSON `episode_ids` for many-to-many mapping, enabling joins for Episodes & Publishing views.
5. `pipeline_runs`
   - Columns: `id UUID PK`, `workflow_run_id BIGINT`, `workflow_name TEXT`, `trigger TEXT`, `status TEXT`, `conclusion TEXT`, `started_at TIMESTAMPTZ`, `finished_at TIMESTAMPTZ`, `phase JSONB`, `notes TEXT`.
   - Enables dashboard to stream supabase-backed status + cross-link to GitHub logs.
6. Optional supporting views
   - `active_topics_view` (filters `is_active = true`, sorted by order)
   - `topic_digest_summary_view` (last generated + published information per topic).

## Migration Workflow
1. Alembic migrations
   - Generate migration for each new table + constraints.
   - Use Alembic operations so migrations run locally and in CI.
2. Data backfill script (`scripts/migrate_topics_to_supabase.py`)
   - Loads `config/topics.json` and `digest_instructions/*.md` → inserts into `topics` + `topic_instruction_versions`.
   - Maps instruction file to slug via sanitized name.
   - Seeds `voice_settings` from `topics.json.settings.default_voice_settings`.
3. JSON cleanup
   - Once data is in Supabase, mark `config/topics.json` + `digest_instructions/` as legacy/read-only.
   - Update ConfigManager to fall back to Supabase first, optionally “hydrate” the JSON for local dev-only scenarios.
4. `digest_episode_links`
   - Backfill existing digests by exploding JSON `episode_ids` and matching on `episodes.id`.
   - Update ingestion pipeline to populate this table going forward.
5. `pipeline_runs`
   - Create bootstrap script to ingest the last N GitHub workflow runs via API, seeding history for the dashboard.

## Config & Pipeline Refactor Plan
1. Replace `ConfigManager` with repository pattern
   - Create `TopicRepository` (SQLAlchemy) sourcing from Supabase tables.
   - WebConfig remains as the typed settings layer, but `ConfigManager` should only act as a compatibility shim.
2. Pipeline phases fetch topics from DB
   - `ContentScorer`, `ScriptGenerator`, `VoiceManager` to consume `TopicRepository.get_active_topics()` and `TopicRepository.get_instructions(topic_id)`.
   - Remove direct file reads; keep optional file fallback under `tests/fixtures` to avoid regressions.
3. Multi-topic scoring + digest
   - Ensure scoring result persists per-topic scores (already stored in `episodes.scores` JSONB).
   - `ScriptGenerator.create_daily_digests` loops through active topics from DB; persist digest metadata + `digest_episode_links`.
4. Phase run metadata
   - Update each phase script to register progress in `pipeline_runs` (create new row at orchestrator start, update per phase). Use `ORCHESTRATED_EXECUTION` to gate.
5. Workflow tweaks (`validated-full-pipeline.yml`)
   - Inject `PIPELINE_RUN_ID` env so every phase shares the same row.
   - Persist discovery/audio/scoring outputs via DB instead of JSON piping; or continue piping but also write summary rows into DB to support restarts.
6. GitHub permissions & secrets
   - Re-confirm PAT scopes (contents:write, actions:read). Document env updates (GH_TOKEN vs PAT) per `gh-publishing-workflow-learnings.md`.
7. TTS sparing
   - Add dry-run flag through pipeline to skip TTS + publishing (default off in production). Validation tasks should exercise up to digest stage.

## Hosted UI Integration Blueprint
1. API layer rewrite
   - `/api/topics` → CRUD via Supabase (`topics`, `topic_instruction_versions`); return full metadata for UI.
   - `/api/script-lab` → load/save instructions from Supabase, commit new version row, update `topics.instructions_md` + `voice_id`.
   - `/api/episodes` → query `episodes` join `feeds` + `digest_episode_links` + `digests` for accurate feed/digest info.
2. Dashboard & Logs
   - `/api/pipeline/status` should join `pipeline_runs` + live GitHub API (fallback). Map by workflow ID + job name (“Run Validated Pipeline”).
   - Implement `/api/logs/stream` to stream combined GitHub job logs (via Actions API) or DB stored events.
3. Feature parity pages
   - **Publishing**: surface GitHub releases, Supabase digests (`published_at`), queue manual publish job.
   - **Maintenance**: port Flask utilities (reset episodes, retention cleanup, log viewer). Use Supabase functions or serverless actions instead of local shell commands.
4. UX updates
   - Show topic activity (last generated, last published) using `topics.last_generated_at` + `digests` aggregates.
   - Update Episodes table columns to include feed title, digest badges, and per-topic score chips fetched from Supabase.

## Testing & Validation Strategy
- Unit/integration: extend pytest suites with Supabase test containers or mocks for `TopicRepository` and `pipeline_runs` interactions.
- CLI smoke scripts: add `scripts/test_scoring_without_tts.py` to validate multi-topic path without hitting ElevenLabs.
- Playwright: expand UI tests for Topics CRUD, Script Lab edits (assert DB updates), Episodes digest badges, Dashboard status.
- Workflow rehearsal: run `publishing-only.yml` in dry-run mode to validate pipeline run tracking without TTS.

## Performance & Caching
- Introduce a caching layer for hosted routes (Next.js `revalidateTag`/`revalidatePath`, edge caching, or Supabase row-level caching) once the APIs are fully Supabase-backed.
- Identify high-traffic views (Dashboard, Episodes, Topics) and budget TTLs to balance freshness with perceived latency.
- Ensure cache invalidation hooks tie into pipeline run updates (e.g., invalidate topic/digest pages when `pipeline_runs` changes phase, refresh episodes when digest links update).
- Document caching strategy in `OPERATIONS.md` and validate via Lighthouse/Browser dev tools.

## Documentation Updates
- Update `README.md` with hosted-first workflow, Supabase schema tables, and “legacy local UI” status.
- Update `podscrape2-prd.md` to reference hosted admin flow, Supabase configuration, and GitHub Actions triggers.
- Annotate `move-online2.md` and `phase5-tasklist.md` with links to this plan and the new milestones.
- Document rollout steps + migration scripts in `OPERATIONS.md` once implemented.

## Execution Milestones
1. **Schema & Data Migration** (Topics, instruction versions, digest links, pipeline runs).
2. **Config/Pipeline Refactor** (TopicRepository, multi-topic support, pipeline_runs logging).
3. **Hosted API/UI Update** (Topics, Script Lab, Episodes, Dashboard, Publishing, Maintenance).
4. **Workflow & Monitoring Enhancements** (validated workflow updates, live logs, Supabase status persistence).
5. **Docs & Runbook Refresh** (README, PRD, operations guides).

Each milestone should land as atomic PRs off `feature/complete-hosted-migration`, with Supabase migrations + scripts included and CI focused on pre-TTS phases.
