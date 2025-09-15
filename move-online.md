# Move Online Plan

A practical, multi‑phase plan to move this project off local-only and onto the web. It focuses on:
- Hosting the Web UI at `podcast.paulrbrown.org`.
- Running the daily pipeline on infra other than your laptop.
- Keeping dev/prod parity with easy single‑phase testing.
- Clear data layout for DB, audio, RSS, and logs.
- Migrating STT from Parakeet to OpenAI Whisper (or better) cleanly.

This plan is designed to be executed in a feature branch and merged incrementally.

## Decision (per constraints)

- Use Supabase Postgres as the primary database shared by CI and the Vercel UI.
- Run the daily pipeline on GitHub Actions; connect to Supabase via `DATABASE_URL`.
- Host RSS and the admin/status UI on Vercel at `podcast.paulrbrown.org`.
- Keep pipeline logs as GitHub Actions Artifacts with 7‑day retention.
- Publish MP3s as GitHub Releases assets (public URLs) and also upload a zipped audio bundle to Artifacts for 7‑day backup.


## High‑Level Architecture Options

- Option A — GitHub Actions + Supabase + Vercel (selected)
  - Daily pipeline runs as a scheduled GitHub Action and uses Supabase Postgres for state.
  - Web UI runs on Vercel and reads/writes to Supabase using pooled connections.
  - Static RSS (`public/daily-digest.xml`) is deployed on Vercel; RSS enclosures link to GitHub Releases asset URLs.

- Option B — Single Host (Render/Fly/VM) with cron
  - Not selected due to “GitHub or Vercel only” constraint.

- Option C — Vercel‑only with Cron invoking serverless functions
  - Not recommended for this workload: long‑running audio/LLM tasks, local files, and DB writes do not fit serverless time and storage limits well.

Decision needed: Pick Option A or B. This plan optimizes for Option A, with notes for B.


## Guiding Principles
- Single source of truth for storage layout via `DATA_ROOT` and environment.
- Pipelines are modular, idempotent, and runnable by phase without full runs.
- All generated outputs have explicit retention and are discoverable in logs.
- CI is cost‑aware: default to “publishing only” in PRs; full runs only on schedule.


## Phase 0 — Branch, Secrets, and Prep

- [ ] Create feature branch `feature/move-online` for all changes.
- [ ] Add `.env.sample` with documented variables:
  - `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`, `GITHUB_TOKEN`, `GITHUB_REPOSITORY`, `DATA_ROOT`, `WEBUI_SECRET`, `LOG_LEVEL`, `DATABASE_URL` (Supabase Postgres), optional `SUPABASE_POOL_URL` for serverless pooling.
- [ ] Audit paths and I/O:
  - Replace any hardcoded absolute paths with `DATA_ROOT` + subpaths.
  - Canonical structure (local and remote must match):
    - `data/database/digest.db`
    - `data/audio/` (MP3s)
    - `data/logs/` (pipeline + web logs)
    - `public/` (RSS, static)
- [ ] Add `scripts/doctor.py` (or similar) to validate data layout and permissions.
- [ ] Add `scripts/bootstrap_local.sh` to pull the latest DB/audio/log artifacts from CI to a dev machine.

Acceptance criteria
- `DATABASE_URL` wired; local and CI can connect to Supabase.
- `scripts/doctor.py` passes locally and in CI (checks DB connectivity and data paths).


## Phase 1a — Database Migration to Supabase Postgres

- [ ] Add SQLAlchemy + Alembic to project (models and migrations).
- [ ] Translate existing `schema.sql` to SQLAlchemy models with Postgres types:
  - Use JSONB for `scores` and `episode_ids`.
  - Add indexes: `episodes(episode_guid)`, `episodes(status, published_date)`, `digests(digest_date, topic)`.
- [ ] Create Alembic initial migration to create tables in Supabase.
- [ ] One-time data migration `scripts/migrate_sqlite_to_pg.py`:
  - Reads from local SQLite (`data/database/digest.db`) and bulk-inserts into Postgres.
  - Normalizes datetimes to UTC; casts JSON fields; preserves IDs where practical.
- [ ] Refactor `src/database/models.py` into a provider with SQLAlchemy sessions and repositories that target Postgres SQLAlchemy models.
  - Replace SQLite-specific SQL (e.g., `json_extract`, `date('now', ...)`) with SQLAlchemy expressions for Postgres (`scores->>topic`, `now() - interval`).
  - Keep a lightweight SQLite fallback only for offline dev if `DATABASE_URL` is absent.

Acceptance criteria
- Postgres schema created via Alembic; data migrated from a representative SQLite snapshot.
- Unit/integration tests pass against Postgres.
- Pipeline read/writes succeed in CI with Supabase.

## Phase 1 — Modularize Pipeline for Single‑Phase Runs

- [ ] Introduce a simple pipeline CLI with subcommands (wrappers OK):
  - `ingest` (fetch sources), `transcribe`, `summarize`, `tts`, `publish`.
  - Keep top‑level `run_full_pipeline.py` for convenience; route into subcommands.
- [ ] Add flags: `--dry-run`, `--limit N`, `--from-step`, `--to-step`.
- [ ] Ensure idempotency: skip already‑processed items by checking DB/status.
- [ ] Standardize logging to `data/logs/pipeline_YYYYMMDD_HHMMSS.log`.
- [ ] Add `pytest` integration tests for each phase using fixtures (no GPT/TTS calls).
- [ ] Make `run_publishing_pipeline.py` strictly publishing from existing MP3s.

Acceptance criteria
- Each phase can run independently without requiring others.
- Publishing pipeline produces the canonical RSS from existing artifacts.


## Phase 2 — Storage and Artifact Strategy

Selected approach (DB in Supabase; RSS public; audio in Releases).

- DB: Supabase Postgres is the source of truth; upload a daily `pg_dump` as an Artifact with `retention-days: 7` for backup.
- Logs: Upload pipeline logs as Artifacts with `retention-days: 7`.
- Audio: Publish MP3s as GitHub Releases assets; also upload a zipped audio bundle as an Artifact backup; keep only the last 7 daily Releases.
- RSS: Commit changes in `public/` back to repo (bot commit) and deploy on Vercel.

Tasks
- [ ] Add `scripts/publish_release_assets.py` for MP3 uploads with `Content-Type: audio/mpeg` and retention cleanup (delete Releases older than 7 days).
- [ ] Add `scripts/db_backup.py` to run `pg_dump` (schema+data) and upload as Artifact.

Acceptance criteria
- Public MP3 links via Releases work; daily DB backup artifacts exist for the last 7 days.


## Phase 3 — CI/CD

- [ ] `ci.yml` (PRs):
  - Lint (Black/Flake8), type check (MyPy), unit/integration tests.
  - Optionally run Playwright UI tests against the Flask server with seeded DB.
- [ ] `publish.yml` (schedule):
  - Trigger daily on cron (UTC); concurrency: cancel in‑progress on new schedule.
  - Steps: checkout; setup Python; set `DATABASE_URL` secret; run Alembic migrations; run `run_full_pipeline.py --log ...` or staged commands; upload logs and `pg_dump` as Artifacts with `retention-days: 7`; commit/push `public/` changes; create/update a daily GitHub Release with MP3 assets; delete Releases older than 7 days; post job summary with links to Release assets and RSS.
- [ ] Configure Secrets in GitHub: `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`, `GH_TOKEN` (fine‑grained), any storage keys.
- [ ] Add failure notifications (GitHub notifications, optional Slack/Email).

Acceptance criteria
- Manual “Dispatch” works; scheduled run produces RSS and artifacts.
- Logs and DB available as downloadable artifacts; RSS diff is in commit/PR.


## Phase 4 — Web UI Hosting + DNS

- [ ] Deploy the admin/status UI to Vercel:
  - Connect directly to Supabase for CRUD (Feeds, Topics, Episode status, Retention settings) via pooled connections.
  - Continue to use GitHub Workflow Dispatch for heavy actions (e.g., re-run pipeline) to keep serverless fast.
  - Apply minimal auth: password via `WEBUI_SECRET` or GitHub OAuth; consider RLS policies for write endpoints.
- [ ] DNS: point `podcast.paulrbrown.org` to Vercel; serve `public/daily-digest.xml` and the UI under the same domain.

Acceptance criteria
- Vercel UI loads, shows status from Postgres, allows CRUD where appropriate, and can dispatch runs. RSS accessible at canonical URL; enclosure links work in podcast clients.


## Phase 5 — STT Migration (Parakeet → OpenAI)

- [ ] Introduce STT provider abstraction (`src/pipeline/stt/providers.py`).
- [ ] Implement `openai_whisper` provider with retries and cost caps.
  - Prefer `gpt-4o-mini-transcribe` (fast/cost‑effective) or `whisper-1` if still available in your account/region.
- [ ] Keep Parakeet provider for fallback; make provider selectable via env `STT_PROVIDER=parakeet|openai`.
- [ ] Add photonegative tests (skip external calls) and golden tests using cached transcripts.
- [ ] CLI tool: `scripts/transcribe_one.py <audiofile>` for quick/manual validation.

Acceptance criteria
- Either provider can be toggled by config with identical downstream outputs (schema stable).
- Integration test validates that OpenAI provider meets accuracy/runtime expectations on sample clips.


## Phase 6 — Local Dev Parity and Testing

- [ ] Playwright UI tests adapted to run in CI against hosted or local server.
- [ ] Provide `scripts/run_web_ui.sh` support for prod‑like `.env` and port override.
- [ ] `scripts/bootstrap_local.sh` to set `.env` with `DATABASE_URL`, verify Supabase connectivity, fetch recent logs (Artifacts) and optionally last N MP3s (from Releases) for debugging.
- [ ] Document Makefile targets or `scripts/*` commands for common flows:
  - `make test`, `make lint`, `make ci-local`, `make run-publish`, `make run-full`.

Acceptance criteria
- Dev can run single phases locally in minutes without incurring cloud costs.
- UI tests green locally and in CI.


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


## Concrete Next Steps (Week 1)

1) Decide architecture: Option A (CI + hosted UI) vs B (single host + cron).
2) Create `feature/move-online` branch and add `.env.sample` + `DATA_ROOT` plumbing.
3) Add `scripts/doctor.py` and wire `data/` layout enforcement.
4) Extract pipeline phases into subcommands; keep existing runners intact.
5) Draft CI workflows (lint/tests only) to validate structure before enabling schedule.


## Notes and Tradeoffs

- Vercel Cron is great for “poke a webhook” jobs, not long audio/LLM work. Use GitHub Actions or a long‑lived host for the heavy lifting.
- GitHub Releases as audio storage works surprisingly well for small/medium catalogs but gets clunky at scale. S3/Backblaze is a smoother long‑term path.
- Supabase provides a shared Postgres DB for CI and UI, avoiding artifact shuttling and simplifying CRUD. Alembic migrations and connection pooling become part of ops.
- Do not commit MP3s into the repo; use GitHub Releases for public audio URLs without extra infra.


## Open Questions for You

- Confirm: Use GitHub Releases for public MP3 URLs and also upload a 7‑day audio bundle as an Artifact backup.
- Provide Supabase connection details: `DATABASE_URL` for CI/Vercel and `SUPABASE_POOL_URL` if available; confirm RLS policy approach (on/off for server-side use).
- For STT, is the priority speed, cost ceiling, or accuracy parity with current Parakeet output?


---

Appendix — Example CI Shapes (sketch)

- `.github/workflows/ci.yml` (PR)
  - steps: checkout → setup-python → pip install → black/flake8/mypy → pytest → start web UI → Playwright tests.

- `.github/workflows/publish.yml` (schedule)
  - on: schedule: `0 13 * * *` UTC (adjust as desired)
  - steps: checkout → setup-python → export `DATABASE_URL` secret → run Alembic migrations → run full pipeline with `--log` → upload logs and daily `pg_dump` artifact (retention 7 days) → commit `public/` → create/update daily GitHub Release with MP3 assets (set audio/mpeg) → delete Releases older than 7 days → post run summary with links.
