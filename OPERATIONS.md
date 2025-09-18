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
Run `python scripts/doctor.py` locally and confirm the CI/CD secrets block passes before dispatching workflows.

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

### 2025-09-17 — Subphase 4.2 Audio Dry Run
- Workflow: `Phase Audio` (`.github/workflows/phase-audio.yml`)
- Run ID: `17811446743` (`gh run view 17811446743`)
- Status: ✅ Success (limit=1, days_back=3, dry run with discovery seed)
- Summary:
  - Discovery seeding produced `discovery-output.json` with a single pending episode.
  - Audio phase executed in dry-run mode (no downloads/transcription) and reported the episode in `audio-output.json`.
  - Pip, virtualenv, and Whisper caches reused from previous run; ffmpeg installed via apt each execution.
  - Artifact `audio-phase` contains discovery JSON, audio JSON, and logs (`audio_20250917_214614.log`).
- Artifact download: `gh run download 17811446743 -n audio-phase -D ./tmp/audio-phase`
- Notes: Whisper cache path currently empty on runners; warning during cache save is expected until models are downloaded in a non–dry-run future phase.

### 2025-09-17 — Subphase 4.3 Scoring Dry Run
- Workflow: `Phase Scoring` (`.github/workflows/phase-scoring.yml`)
- Run ID: `17811674774` (`gh run view 17811674774`)
- Status: ✅ Success (limit=1, days_back=3, dry run end-to-end)
- Summary:
  - Discovery and audio dry-run steps executed inline so scoring has seeded data.
  - Scoring dry-run reported one episode with empty `scores` map (expected because GPT call is skipped).
  - Artifacts: `scoring-phase` zip containing discovery/audio/scoring JSON outputs and logs (`scoring_*.log`, `audio_*.log`, `discovery_*.log`).
  - Pip/venv caches hit; Whisper cache still empty (warning noted).
- Artifact download: `gh run download 17811674774 -n scoring-phase -D ./tmp/scoring-phase`
- Notes: Future real runs must ensure transcripts exist before removing dry-run guard.

### 2025-09-17 — Subphase 4.4 Digest Dry Run
- Workflow: `Phase Digest` (`.github/workflows/phase-digest.yml`)
- Run ID: `17812724198` (`gh run view 17812724198`)
- Status: ✅ Success (limit=1, days_back=3, dry run across discovery/audio/scoring/digest)
- Summary:
  - Replayed discovery → audio → scoring dry-run steps before invoking digest to ensure DB state consistent.
  - Digest dry-run reports zero generated digests (expected) and confirms the pipeline wiring.
  - Artifact `digest-phase` contains discovery/audio/scoring outputs, digest output (dry-run message), and combined logs.
  - Caches reused from prior runs; Whisper cache still empty (warning remains expected).
- Artifact download: `gh run download 17812724198 -n digest-phase -D ./tmp/digest-phase`
- Notes: When enabling real digest generation, remove dry-run flag and ensure transcripts/scoring data exist for the target date.
