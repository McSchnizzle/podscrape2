# Repository Guidelines

## Project Structure & Module Organization
- `src/` — application code (database, podcast pipeline, publishing, config, utils)
- `scripts/` — production phase scripts (`run_discovery.py`, `run_audio.py`, etc.) and utilities
- `web_ui/` — optional Flask Web UI (port 5001) with templates
- `ui-tests/` — Playwright UI tests and config
- `data/` — logs, audio artifacts, legacy SQLite database
- **Top-level runners**:
  - `run_full_pipeline_orchestrator.py` (production orchestrator)
  - `run_full_pipeline.py` (legacy single-phase)
  - `run_publishing_pipeline.py` (publishing only)
  - Individual phase scripts in `scripts/` directory

## Build, Test, and Development Commands
- Create venv and install deps:
  ```bash
  python3 -m venv .venv && source .venv/bin/activate
  python3 -m pip install -r requirements.txt
  ```
- Run publishing (uses existing MP3s, no GPT/TTS):
  ```bash
  timeout 12m python3 run_publishing_pipeline.py -v
  ```
- Run full pipeline (production orchestrator):
  ```bash
  timeout 15m python3 run_full_pipeline_orchestrator.py
  ```
- Run individual phases:
  ```bash
  python3 scripts/run_discovery.py --verbose
  python3 scripts/run_audio.py --limit 3
  python3 scripts/run_scoring.py
  python3 scripts/run_digest.py
  python3 scripts/run_tts.py
  python3 scripts/run_publishing.py
  ```
- Start Web UI (optional):
  ```bash
  bash scripts/run_web_ui.sh  # PORT=5002 to override
  ```
- Playwright UI tests (with UI running):
  ```bash
  cd ui-tests && npm install && npx playwright install && npx playwright test
  ```

## Pre-commit Testing Discipline
- Always run the Web UI and the Playwright UI tests locally before committing/pushing changes that touch `web_ui/`, templates, or publishing logic.
  - Start the server: `bash scripts/run_web_ui.sh`
  - Run tests: `cd ui-tests && npm install && npx playwright install && npx playwright test`
- Ensure these flows render without errors:
  - Dashboard + Live Status streaming
  - Feeds and Topics CRUD
  - Publishing page lists digests and shows actions
  - Settings saves, including Retention values

## Coding Style & Naming Conventions
- Python: Black formatting, Flake8 lint, MyPy typing. Use 4-space indent, snake_case for modules/functions, PascalCase for classes.
- Files/paths: descriptive snake/kebab case (e.g., `generate_local_rss.py`, `web_ui/templates/settings.html`).

## Testing Guidelines
- Python tests via `pytest` (unit/integration). Name files `test_*.py`.
- UI tests via Playwright in `ui-tests/` under `tests/*.spec.ts`.
- Prefer tests that avoid GPT/TTS costs (use existing MP3s and DB fixtures).

## Commit & Pull Request Guidelines
- Commits: imperative mood, concise summary; include “what/why” (e.g., “Fix: upload missing assets to existing release”).
- PRs: clear description, rationale, logs/screenshots for UI/ops, and validation steps (commands + expected output).

## Security & Configuration Tips
- **Environment Variables**: `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`, `GITHUB_TOKEN`, `GITHUB_REPOSITORY`, `DATABASE_URL` (PostgreSQL/Supabase)
- **Canonical RSS**: `public/daily-digest.xml` (deployed on Vercel)
- **Database**: PostgreSQL via Supabase (production), SQLite (legacy). Use `python3 -m alembic upgrade head` for PostgreSQL migrations
- **Transcription**: Local OpenAI Whisper (no API costs) with `WHISPER_MODEL` environment variable
