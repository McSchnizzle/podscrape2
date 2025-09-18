# Phase 4 Task List — Incremental CI/CD Rollout

Goal: bring the orchestrated pipeline online in GitHub Actions one phase at a time. Each subphase stands up a minimal workflow, exercises the phase in isolation, wires it to the temporary Web UI control panel, and only then moves on. The dashboard stays untouched until all phases are battle-tested.

## Prerequisites
- Pip requirements and Alembic migrations verified in CI cache (`python -m pip install -r requirements.txt`, `python -m alembic upgrade head`).
- Web UI temp page scaffold (`web_ui/templates/ci_controls.html`, controller route, shared layout partials) ready to host buttons and status stream.
- GitHub fine-grained PAT with `workflow` scope available for Web UI dispatch calls.

## Phase 4.0 — CI/CD Bootstrap
Purpose: hydrate GitHub with required secrets, confirm permissions, and validate that the Actions runner can reach our core services before enabling pipeline phases.

1. **Secret Inventory & Creation**
   - Document required secrets in `OPERATIONS.md`: `DATABASE_URL`, `SUPABASE_*`, `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`, `GH_TOKEN`/`GITHUB_TOKEN`, `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`, `WEBUI_DISPATCH_PAT` (fine-grained with `workflow` scope).
   - Create or update repository/environment secrets in GitHub and note owners responsible for refreshing them.
   - For local verification, add `scripts/doctor.py` section covering GitHub Actions-specific variables.
   - ✅ Completed 2025-09-17: documented in `OPERATIONS.md` (Secret Inventory) and surfaced via `scripts/doctor.py` CI checks.

2. **Bootstrap Workflow**
   - Add `.github/workflows/ci-bootstrap.yml` with manual dispatch only.
   - Steps: checkout, setup Python, install `requests`/`psycopg`, run a Python script that
     - verifies `DATABASE_URL` connectivity (`SELECT 1`),
     - hits `https://api.openai.com/v1/models` with `OPENAI_API_KEY`,
     - performs a lightweight ElevenLabs auth check (e.g., list voices with `dry_run` flag),
     - calls `gh api` or GitHub REST `GET /repos/{repo}` using PAT to ensure workflow-scope token works.
   - Upload a small JSON report artifact summarizing the connectivity test results.
   - ✅ Completed 2025-09-17: `.github/workflows/ci-bootstrap.yml` committed; artifact `ci-bootstrap-report.json` published (run `17810460258`).

3. **Review & Sign-off**
   - Run workflow via `workflow_dispatch`; confirm logs mask secrets and all checks succeed.
   - If any check fails, update secrets or adjust network allow-list before proceeding to Subphase 4.1.
   - Record run link and resolution notes in `Phase4 rollout log` (new section in `OPERATIONS.md`).
   - ✅ Completed 2025-09-17: validation run recorded in `OPERATIONS.md` Phase 4 rollout log with artifact download instructions.


## Subphase 4.1 — Discovery Workflow
1. **GitHub Actions**
   - Create `.github/workflows/phase-discovery.yml` with steps: checkout, setup Python, install requirements, run `python scripts/run_discovery.py --limit 2 --verbose --dry-run`.
   - Add aggressive caching (`actions/cache`) for `~/.cache/pip`, `.venv`, and feed data fixtures to keep reruns fast.
   - Upload log artifact (`discovery.log`) and JSON output for inspection.
 - Gate on pull requests + manual dispatch; allow concurrency cancel.
  - ✅ Completed 2025‑09‑17: workflow `phase-discovery.yml` run ID `17810944886` (dry-run limit=1, days_back=3).
2. **Testing**
   - Add pytest marker (e.g., `tests/test_phase_scripts.py::TestPhaseScripts::test_discovery_script_help`) to CI so dry-run executes quickly.
   - Ensure log parsing works locally via `python scripts/run_discovery.py --limit 1 --dry-run`.
3. **Web UI**
   - Add temporary “CI Controls” page replicating live status layout.
   - Include “Run Discovery Workflow” button that triggers `phase-discovery.yml` via GitHub REST dispatch; stream results in the page.
   - Confirm button works end-to-end on staging GitHub repo before promoting.

## Subphase 4.2 — Audio Workflow
1. **GitHub Actions**
   - `.github/workflows/phase-audio.yml`: reuse discovery artifact or sample payload; run `python scripts/run_audio.py --limit 1 --dry-run` (no Whisper heavy lifting yet).
   - Cache Whisper models, ffmpeg build downloads, and pip wheels between runs.
   - Cache Whisper model if needed; upload audio/transcript artifacts.
   - ✅ Completed 2025‑09‑17: workflow `phase-audio.yml` run ID `17811446743` (dry-run limit=1, days_back=3).
2. **Testing**
   - Expand pytest to cover audio runner entrypoint stub (mock network / ffmpeg availability check).
   - Manual dry-run on GitHub-hosted runner to verify ffmpeg install instructions.
3. **Web UI**
   - Add “Run Audio Workflow” button + status card on CI Controls page.
   - Display artifact download link once run completes.

## Subphase 4.3 — Scoring Workflow
1. **GitHub Actions**
   - `.github/workflows/phase-scoring.yml`: run `python scripts/run_scoring.py --limit 2 --dry-run`, mock GPT calls with existing fixtures to avoid live tokens.
   - Cache pip deps plus prompt fixture archives for deterministic run times.
   - Persist scoring output JSON + structured logs.
   - ✅ Completed 2025‑09‑17: workflow `phase-scoring.yml` run ID `17811674774` (dry-run limit=1, days_back=3).
2. **Testing**
   - Ensure `tests/test_phase_scripts.py` covers scoring script import/help; add fixture verifying dry-run path.
   - Validate environment guard prevents accidental live token use on CI.
3. **Web UI**
   - CI Controls button for scoring; update page to show last run duration, topic counts from artifact.

## Subphase 4.4 — Digest Workflow
1. **GitHub Actions**
   - `.github/workflows/phase-digest.yml`: run `python scripts/run_digest.py --limit 1 --dry-run`, ensure dependencies on scoring outputs satisfied (use seeded DB fixture or artifact from prior run).
   - Reuse cached pip deps and share digest template cache (Markdown/JSON) between runs.
   - Upload generated script markdown.
   - ✅ Completed 2025‑09‑17: workflow `phase-digest.yml` run ID `17812724198` (dry-run limit=1, days_back=3).
   - ✅ Re-validated 2025‑09‑18: workflow `phase-digest.yml` run ID `17841228652` (dry-run limit=auto; confirms scoring fallback fix).
2. **Testing**
   - Extend pytest fixtures to verify digest generation dry-run path using local sample transcripts.
   - Confirm Alembic migrations run before pipeline step to keep schema aligned.
3. **Web UI**
   - Button + status panel for digest, showing produced script metadata (word count, topics).

## Subphase 4.5 — TTS Workflow
1. **GitHub Actions**
   - `.github/workflows/phase-tts.yml`: run `python scripts/run_tts.py --limit 1 --dry-run` with ElevenLabs disabled (mock) to avoid spending credits; perimeter check for required key.
   - Cache ElevenLabs voice metadata and pip deps; reuse synthesized placeholder assets.
   - Upload synthesized audio placeholder or JSON summary.
   - ✅ Completed 2025-09-18: workflow `phase-tts.yml` run ID `17842116998` (dry-run; seeds discovery→digest before TTS).
2. **Testing**
   - Add unit test to confirm dry-run returns structured response without calling ElevenLabs (`tests/test_phase_scripts.py`).
   - Validate pipeline respects WebConfig TTS settings on CI.
   - ✅ `tests/test_phase_scripts.py::test_tts_script_dry_run_empty_payload` exercises CLI dry-run path with empty payload.
3. **Web UI**
   - Button triggers TTS workflow; card displays audio metadata or dry-run notice.

## Subphase 4.6 — Publishing Workflow
1. **GitHub Actions**
   - `.github/workflows/phase-publishing.yml`: run `python scripts/run_publishing.py --verbose` with `DRY_RUN` env guard; mock GitHub release calls via fine-grained PAT and skip destructive steps.
   - Cache pip deps and GitHub release metadata (e.g., `~/.cache/gh`) to avoid redundant API calls.
   - Ensure retention manager cleanup tasks run safely (skip destructive actions in dry-run).
   - ✅ Completed 2025-09-18: workflow `phase-publishing.yml` run ID `17843283291` (dry-run end-to-end).
2. **Testing**
   - ✅ `tests/test_phase_scripts.py::test_publishing_runner_dry_run` ensures the runner exits successfully in dry-run mode with mocked repositories.
   - Manual verification that GitHub API fallback for CLI-less environments succeeds.
3. **Web UI**
   - Button for publishing workflow; show outcome summary (release/tag names, RSS file path, deployment status).

## Subphase 4.7 — Orchestrated Full Run
1. **GitHub Actions**
   - Compose final `.github/workflows/full-pipeline.yml` pulling together validated steps; ensure concurrency, retention, artifact uploads for logs, transcripts, RSS, and optional `pg_dump`.
   - Carry over caches from subphase workflows (pip, Whisper models, digest templates, gh metadata) so scheduled runs stay within time limits.
   - Schedule cron + manual dispatch; gate on previous phase success.
2. **Testing**
   - Smoke test on staging branch; confirm orchestrator exit codes bubble up.
   - Expand pytest to include orchestrator CLI help smoke test in CI job.
3. **Web UI**
   - Promote CI Controls components into Live Status page (or merge once stable).
   - Add summary of last full run, artifact links, and manual dispatch confirmation modal.

## Temporary CI Controls Page Requirements
- Route: `/ci-controls` (authenticated via existing mechanism).
- Template extends dashboard layout but clearly marked “Experimental”.
- Components:
  - Status cards for each workflow (icon, last run timestamp, outcome, link to GitHub run).
  - Buttons calling GitHub `workflow_dispatch` endpoint via server-side helper (use PAT, fail fast on non-200).
  - Streaming area (reuse live status SSE) to show logs or queue info.
- Logging: dedicated logger (`web_ui.ci_controls`) with minimal noise.

## Exit Criteria per Subphase
- Workflow succeeds on branch PR trigger and manual dispatch.
- Web UI button launches workflow, returns success/failure message, and surfaces run results.
- Dry-run outputs stored as artifacts, reviewed for correctness.
- Rollback plan documented (disable workflow file, remove button) before proceeding.

## Final Deliverables
- All phase-specific workflow files committed with documentation headers.
- Web UI CI Controls page merged but hidden behind feature flag until full pipeline ready.
- Ops notes added to `OPERATIONS.md` describing manual dispatch, log retrieval, and incident response.
- Phase 4 review checklist completed and archived in repo docs.
