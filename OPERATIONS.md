# Operations Runbook

## Secret Inventory (Phase 4.0 – CI/CD Bootstrap)
The following GitHub repository secrets are required for the CI bootstrap and subsequent Phase 4 workflows:

- `DATABASE_URL`
- `SUPABASE_URL`
- `SUPABASE_PASSWORD` (or direct `SUPABASE_DB_URL`)
- `OPENAI_API_KEY`
- `ELEVENLABS_API_KEY`
- `GH_TOKEN` (fine-grained PAT with `workflow` scope)
- `GH_REPOSITORY` (owner/repo string for GitHub API convenience)
- `VERCEL_TOKEN`
- `VERCEL_ORG_ID`
- `VERCEL_PROJECT_ID`
- `WEBUI_DISPATCH_PAT`

Keep these secrets updated whenever credentials rotate. Validate the full set with the `CI Bootstrap` workflow after any change.

## Phase 4 Rollout Log

### 2025-09-17 — CI Bootstrap Validation
- Workflow: `CI Bootstrap` (`.github/workflows/ci-bootstrap.yml`)
- Run ID: `17810460258` (`gh run view 17810460258`)
- Status: ✅ Success
- Summary:
  - Database: `SELECT 1` succeeded against `DATABASE_URL`.
  - OpenAI: `Fetched 86 models` from `https://api.openai.com/v1/models`.
  - ElevenLabs: `Retrieved 10` models from `https://api.elevenlabs.io/v1/models`.
  - GitHub: Repository access verified via `GH_TOKEN`.
- Artifact: `ci-bootstrap-report/ci-bootstrap-report.json` (download with `gh run download 17810460258 -n ci-bootstrap-report`).
- Notes: Workflow now caches pip wheels in later phases; rerun after any credential updates.

### 2025-09-17 — Subphase 4.1 Discovery Dry Run
- Workflow: `Phase Discovery` (`.github/workflows/phase-discovery.yml`)
- Run ID: `17810944886` (`gh run view 17810944886`)
- Status: ✅ Success (limit=1, days_back=3, dry run)
- Summary:
  - Discovery scanned 29 feeds, skipped historical items, and produced a dry-run JSON output at `artifacts/discovery-output.json`.
  - Pip/virtualenv caches populated (`pip-Linux-3.11-…`, `venv-Linux-3.11-…`) to accelerate future runs.
  - Logs archived in the `discovery-phase` artifact along with summary JSON.
- Artifact download: `gh run download 17810944886 -n discovery-phase -D ./tmp/discovery-phase`
- Notes: First run incurred full dependency installation (~4m28s). Subsequent runs should re-use caches.

Add new entries below as additional Phase 4 subphases go live.
