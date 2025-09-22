# Operations Runbook

## Secret Inventory (Phase 4.0 – CI/CD Bootstrap)
The following GitHub repository secrets are required for the CI bootstrap and subsequent Phase 4 workflows:

- `DATABASE_URL`
- `SUPABASE_URL`
- `SUPABASE_PASSWORD` (or direct `SUPABASE_DB_URL`)
- `OPENAI_API_KEY`
- `ELEVENLABS_API_KEY`
- `GH_TOKEN` (fine-grained PAT with `workflow` scope)
- `GITHUB_REPOSITORY` (owner/repo string for GitHub API convenience)
- `VERCEL_TOKEN`
- `VERCEL_ORG_ID`
- `VERCEL_PROJECT_ID`
- `WEBUI_DISPATCH_PAT`

Keep these secrets updated whenever credentials rotate. Validate the full set with the `CI Bootstrap` workflow after any change.
Run `python scripts/doctor.py` locally and confirm the CI/CD secrets block passes before dispatching workflows.

## Supabase Schema Migration & Backfill (Hosted UI)
- Ensure Supabase credentials (`DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE` if used) are present in your shell or `.env` before running migrations.
- Apply the latest Alembic migrations:
  ```bash
  python3 -m alembic upgrade head
  ```
- Backfill topics and instructions from the legacy JSON/markdown files:
  ```bash
  python3 scripts/migrate_topics_to_supabase.py --dry-run   # preview changes
  python3 scripts/migrate_topics_to_supabase.py             # perform import
  ```
- After the import succeeds, treat `config/topics.json` and `digest_instructions/*.md` as read-only. Updates should flow through the hosted Topics or Script Lab pages backed by Supabase.
- Verify the import by visiting the hosted Topics page or querying:
  ```bash
  psql "$DATABASE_URL" -c 'select name, slug, last_generated_at from topics order by sort_order;'
  ```

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

### 2025-09-18 — Subphase 4.4 Digest Dry Run Revalidation
- Workflow: `Phase Digest` (`.github/workflows/phase-digest.yml`)
- Run ID: `17841228652` (`gh run view 17841228652`)
- Status: ✅ Success (dry run; validates scoring dry-run fallback)
- Summary:
  - Scoring step accepts discovery/audio payload without DB rows when `--dry-run` is set.
  - Artifacts confirm both episodes processed with `status='dry_run'` and no failures.
- Artifact download: `gh run download 17841228652 -n digest-phase -D ./tmp/digest-phase-latest`
- Notes: Keeps digest workflow green after logic change; next subphase is TTS.

### 2025-09-18 — Subphase 4.5 TTS Dry Run
- Workflow: `Phase TTS` (`.github/workflows/phase-tts.yml`)
- Run ID: `17842116998` (`gh run view 17842116998`)
- Status: ✅ Success (dry run via mocked ElevenLabs path)
- Summary:
  - Reuses discovery→digest dry runs, then executes `run_tts.py --dry-run` to validate CLI path.
  - Artifacts: `tts-phase` bundle with TTS logs and `tts-output.json` (no digests processed).
- Artifact download: `gh run download 17842116998 -n tts-phase -D ./tmp/tts-phase`
- Notes: Next step is wiring CI Controls button and optional mock output preview.

### 2025-09-18 — Subphase 4.6 Publishing Dry Run
- Workflow: `Phase Publishing` (`.github/workflows/phase-publishing.yml`)
- Run ID: `17843283291` (`gh run view 17843283291`)
- Status: ✅ Success (dry run using `DRY_RUN` env toggle)
- Summary:
  - Chains discovery→audio→scoring→digest→tts dry runs before invoking publishing.
  - Publishing logs confirm GitHub/Vercel operations short-circuit under dry run while reporting planned actions.
- Artifact download: `gh run download 17843283291 -n publishing-phase -D ./tmp/publishing-phase`
- Notes: Web UI control hook-up remains; DRY_RUN env now governs all phase scripts.

### 2025-09-19 — Phase Architecture Reorganization
- **Issue Identified**: TTS phase was hardcoded to `DRY_RUN: "true"`, preventing actual MP3 file creation
- **Root Cause Analysis**: Files were being created locally but lost when GitHub Actions workflow environments ended
- **Architectural Decision**: Move MP3 upload responsibility from Publishing to TTS phase for better separation
- **Implementation Changes**:
  - Fixed TTS workflow to use `${{ inputs.dry_run }}` instead of hardcoded "true"
  - Added GitHub publisher integration to TTS phase for immediate MP3 upload after creation
  - Modified Publishing phase to focus on RSS generation and Vercel deployment via git commits
  - Updated database persistence to store GitHub Release URLs after upload
- **Benefits**: Eliminates file transfer between workflows, improves error recovery, enables parallel TTS execution
- **Deployment Strategy**: Publishing now commits RSS to main branch, triggering automatic Vercel deployment

### 2025-09-19 — TTS Workflow Publishing Fix
- **Issue**: Environment variable error `GH_REPOSITORY: unbound variable` causing git push failures
- **Root Cause**: Workflow used `${{ secrets.GH_REPOSITORY }}` instead of `${{ secrets.GITHUB_REPOSITORY }}`
- **Fix Applied**: Updated `.github/workflows/phase-tts.yml` lines 39 and 196
- **Database Repair Logic**: Enhanced publishing pipeline to detect and repair UNPUBLISHED digests with existing GitHub releases
- **Validation**: RSS feed increased from 31 to 32 episodes, including recovered September 20th digest
- **Result**: Workflow now successfully publishes MP3s and updates RSS feed without manual intervention

## Phase 4 Completion Status

### ✅ Completed Subphases
- 4.0: CI/CD Bootstrap
- 4.1: Discovery Workflow
- 4.2: Audio Workflow
- 4.3: Scoring Workflow
- 4.4: Digest Workflow
- 4.5: TTS Workflow (with publishing integration)
- 4.6: Publishing Workflow (RSS generation focus)

### ❌ Remaining Tasks
- 4.7: Orchestrated Full Run (`.github/workflows/full-pipeline.yml`)
- Web UI CI Controls page (`/ci-controls` route)
- End-to-end validation of complete pipeline

## Common Issues & Troubleshooting

### TTS Workflow Failures
- **Symptom**: Git push fails with "unbound variable"
- **Cause**: Environment variable name mismatch
- **Fix**: Verify `GITHUB_REPOSITORY` secret exists (not `GH_REPOSITORY`)

### Missing Episodes in RSS Feed
- **Symptom**: GitHub releases exist but episodes missing from RSS
- **Cause**: Database not updated after release creation
- **Fix**: Run publishing pipeline - it auto-repairs UNPUBLISHED → PUBLISHED status

### Workflow Dispatch Not Working
- **Symptom**: Manual workflow triggers fail
- **Cause**: Missing `WEBUI_DISPATCH_PAT` with workflow scope
- **Fix**: Generate fine-grained PAT with `actions:write` permission

## Quick Commands

### View Recent Workflow Runs
```bash
gh run list --limit 10
gh run view <RUN_ID>
gh run download <RUN_ID> -n <ARTIFACT_NAME>
```

### Test Publishing Pipeline Locally
```bash
python3 scripts/run_publishing.py --verbose --days-back 7
```

### Check RSS Feed Status
```bash
curl -s https://podcast.paulrbrown.org/daily-digest.xml | grep -c "<item>"
```

### Validate GitHub Releases
```bash
gh release list --limit 5
gh release view daily-YYYY-MM-DD
```


### 2025-09-22 — Episode Status Workflow Improvement
- **Goal**: Eliminate 'discovered' status orphan episodes and improve episode processing workflow
- **Changes Implemented**:
  - **Discovery Script**: Removed fallback defaults - pipeline now fails fast if required database settings unavailable
  - **Web UI**: Changed "Reset to Discovered" to "Reset to Pending" with 'pending' status instead of 'discovered'
  - **Status Migration**: Migrated 10 existing episodes from 'discovered' to 'pending' status with cleared transcript/score data
  - **TypeScript Interface**: Updated Episode status type to use 'pending' instead of 'discovered'
- **Benefits**:
  - Episodes reset via Web UI now automatically enter processing queue on next discovery run
  - When discovery finds fewer new episodes than `max_episodes_per_run`, backlog episodes fill remaining slots
  - Eliminated orphan episodes stuck in unprocessed 'discovered' status
  - FAIL FAST compliance prevents silent pipeline failures from missing database configuration
- **Validation**: 10 episodes successfully migrated and ready for processing in next pipeline run

### 2025-09-19 — Phase 4 Workflow Consolidation & Completion
- **Status**: ✅ **PHASE 4 COMPLETE** - Full pipeline operational
- **Primary Workflow**: `Phase TTS` (`.github/workflows/phase-tts.yml`) - **ORCHESTRATED FULL PIPELINE**
- **Execution**: Daily scheduled execution at 5:00 AM UTC + manual dispatch
- **Architecture**: Single comprehensive workflow: Discovery → Audio → Scoring → Digest → TTS → Publishing
- **Workflow Cleanup**: Removed redundant individual phase workflows:
  - ❌ `phase-discovery.yml` (removed - use phase-tts.yml with parameters)
  - ❌ `phase-audio.yml` (removed - use phase-tts.yml with parameters)
  - ❌ `phase-scoring.yml` (removed - use phase-tts.yml with parameters)
  - ❌ `phase-digest.yml` (removed - use phase-tts.yml with parameters)
  - ❌ `phase-publishing.yml` (removed - use phase-tts.yml with parameters)
- **Control**: Use command-line parameters for phase-specific execution:
  - `--limit N`: Limit number of episodes processed
  - `--days-back N`: Discovery lookback window
  - `--dry-run true/false`: Enable dry-run mode
- **Recent Success**: Run ID `17873538510` - Complete end-to-end pipeline execution

### Active Workflows Post-Consolidation
- ✅ **phase-tts.yml**: Primary orchestrated pipeline (scheduled + manual dispatch)
- ✅ **ci-bootstrap.yml**: Environment validation and secret verification
- ✅ **publishing-only.yml**: Standalone publishing for maintenance scenarios
- ✅ **tts-simulator*.yml**: Development testing workflows
