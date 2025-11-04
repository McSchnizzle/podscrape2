# GitHub Actions Workflow Failure Analysis

**Date:** November 4, 2025
**Issue:** Validated Full Pipeline workflow failing for last 4 days
**Last Successful Code Change:** October 22, 2025 (commit f58b64c)

## Investigation Summary

### Timeline
- **Oct 13**: Added `min_episodes_per_digest` feature (commit 234fab2)
- **Oct 22**: Fixed digest logic bug (commit f58b64c) - **LAST CODE CHANGE**
- **~Oct 31**: Workflows started failing (estimated, based on "4 days ago")
- **Nov 4**: Investigation initiated

### Key Finding
**No code changes occurred between Oct 22 and Nov 4**, meaning the failures are **environmental** rather than code-related.

## Potential Root Causes

### 1. Expired or Invalid Secrets (MOST LIKELY)
The workflow depends on several GitHub secrets that may have expired:

#### Required Secrets (`.github/workflows/validated-full-pipeline.yml`)
- `DATABASE_URL` - PostgreSQL/Supabase connection string
- `OPENAI_API_KEY` - For content scoring and script generation
- `ELEVENLABS_API_KEY` - For TTS audio generation
- `GH_TOKEN` - GitHub personal access token for release publishing
- `GITHUB_REPOSITORY` - Target repository (format: `owner/repo`)

#### Symptom Indicators by Secret
| Secret | Failure Phase | Error Pattern |
|--------|---------------|---------------|
| `DATABASE_URL` | Discovery (Phase 1) | Connection errors, RLS policy errors |
| `OPENAI_API_KEY` | Audio (Phase 2) or Digest (Phase 3) | 401 Unauthorized, API errors |
| `ELEVENLABS_API_KEY` | TTS (Phase 4) | 401 Unauthorized, quota errors |
| `GH_TOKEN` | Publishing (Phase 5) | 403 Forbidden, push failures |

### 2. Database Schema Migration Issues
The codebase uses Alembic migrations with Row Level Security (RLS). If migrations haven't been applied:

```bash
# Check migration status
python3 -m alembic current

# Apply pending migrations
python3 -m alembic upgrade head
```

**RLS-Specific Issue**: All tables have RLS enabled. The connection MUST use:
- Service role credentials (`postgres` user)
- `SUPABASE_SERVICE_ROLE` key for admin operations
- Standard `anon` or `authenticated` roles will fail with permission errors

### 3. API Rate Limits or Billing Issues
- **OpenAI**: Daily/monthly token limits exceeded
- **ElevenLabs**: Character quota exhausted
- **GitHub**: API rate limit (5000 requests/hour for authenticated users)

### 4. Recent Digest Logic Changes
Although fixed on Oct 22, the changes to digest generation logic could interact with existing data:

**What Changed:**
- Episodes are now ALWAYS included if >= 1 qualifying episode exists
- `min_episodes_per_digest` setting effectively unused after fix
- Episodes properly marked as `digested` to prevent re-processing

**Potential Issue:**
If old episodes were stuck in `scored` status, they might all get processed at once, causing:
- API rate limit hits (too many episodes to process)
- Token quota exhaustion (large batch of scripts/TTS)
- Database connection pool exhaustion

## Diagnostic Steps

### Step 1: Run Environment Doctor
```bash
python3 scripts/doctor.py
```

This will check:
- ✅ All required environment variables present
- ✅ Database connectivity
- ✅ API key validity
- ✅ External tool availability (ffmpeg, gh CLI)
- ✅ Python dependencies

### Step 2: Check GitHub Secrets
Go to repository settings → Secrets and variables → Actions:

```bash
# Or use GitHub API
gh api repos/OWNER/REPO/actions/secrets
```

Verify all secrets are:
- Present (not deleted)
- Not expired (especially personal access tokens)
- Have correct scopes/permissions

### Step 3: Check Database Migration Status
```bash
# Set DATABASE_URL first
export DATABASE_URL="your_supabase_connection_string"

# Check current migration
python3 -m alembic current

# Expected output: b2eebe8a3dcc (head)
# If not at head, run:
python3 -m alembic upgrade head
```

### Step 4: Verify Database RLS Configuration
```bash
# Connect to database
psql $DATABASE_URL

# Check RLS status on critical tables
SELECT schemaname, tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN ('episodes', 'digests', 'feeds', 'web_settings', 'topics');

# All should show rowsecurity = true
```

### Step 5: Check for Stuck Episodes
```python
# Run this to check for accumulated episodes
python3 << 'PY'
from src.database.models import get_episode_repo
repo = get_episode_repo()

# Count episodes by status
from collections import Counter
episodes = repo.get_all()
statuses = Counter(ep.status for ep in episodes)
print("Episode status counts:")
for status, count in statuses.items():
    print(f"  {status}: {count}")

# Check scored episodes waiting for digest
scored = repo.get_episodes_by_status('scored')
print(f"\nScored episodes waiting for digest: {len(scored)}")
if len(scored) > 50:
    print("⚠️  WARNING: Large backlog of scored episodes may cause API rate limiting")
PY
```

### Step 6: Test Individual Phases
Run each phase independently to isolate the failure:

```bash
# Phase 1: Discovery
python3 scripts/run_discovery.py --verbose

# Phase 2: Audio Processing
python3 scripts/run_audio.py --verbose

# Phase 3: Digest Generation
python3 scripts/run_digest.py --verbose

# Phase 4: TTS Generation
python3 scripts/run_tts.py --verbose

# Phase 5: Publishing
python3 scripts/run_publishing.py --verbose

# Phase 6: Retention
python3 scripts/run_retention.py --verbose
```

The phase that fails will reveal the root cause.

## Proposed Solutions

### Solution 1: Refresh Expired Secrets (Most Common)
1. **Database URL**:
   ```bash
   # Get new connection string from Supabase dashboard
   # Settings → Database → Connection string
   # Use "Direct connection" with service role credentials
   ```

2. **GitHub Token**:
   ```bash
   # Create new personal access token
   # GitHub → Settings → Developer settings → Personal access tokens
   # Required scopes: repo, workflow, write:packages
   gh auth login  # or update GH_TOKEN secret
   ```

3. **API Keys**:
   - OpenAI: Check billing and generate new key if needed
   - ElevenLabs: Check quota and regenerate key if needed

4. **Update GitHub Secrets**:
   ```bash
   # Via GitHub UI: Settings → Secrets → Actions
   # Or via gh CLI:
   gh secret set DATABASE_URL < database_url.txt
   gh secret set OPENAI_API_KEY < openai_key.txt
   gh secret set ELEVENLABS_API_KEY < elevenlabs_key.txt
   gh secret set GH_TOKEN < github_token.txt
   ```

### Solution 2: Apply Pending Database Migrations
```bash
# Ensure DATABASE_URL is set
export DATABASE_URL="postgresql://postgres:[password]@[host]:5432/postgres"

# Run migrations
python3 -m alembic upgrade head

# Verify RLS policies are enabled
python3 scripts/enable_rls.py
```

### Solution 3: Clear Episode Backlog (If Applicable)
If there's a large backlog of scored episodes causing rate limits:

```bash
# Option A: Increase max_episodes_per_digest to batch process
# Via Web UI: Settings → Content Filtering → Max Episodes per Digest = 10

# Option B: Manually mark old episodes as digested
python3 << 'PY'
from src.database.models import get_episode_repo
from datetime import datetime, timedelta
repo = get_episode_repo()

# Mark scored episodes older than 7 days as digested (to skip them)
cutoff = datetime.now() - timedelta(days=7)
old_scored = [ep for ep in repo.get_episodes_by_status('scored')
              if ep.published_date < cutoff]
print(f"Marking {len(old_scored)} old episodes as digested to clear backlog")
repo.mark_episodes_as_digested([ep.episode_guid for ep in old_scored])
PY
```

### Solution 4: Add Workflow Retry Logic
Update `.github/workflows/validated-full-pipeline.yml` to add automatic retries:

```yaml
# Add to each phase that might fail
- name: Phase 2 - Audio Processing
  uses: nick-fields/retry@v2
  with:
    timeout_minutes: 30
    max_attempts: 3
    retry_wait_seconds: 60
    command: |
      source "${VENV_PATH}/bin/activate"
      python scripts/run_audio.py --verbose --output artifacts/audio-output.json
```

## Verification Steps

After applying fixes:

1. **Trigger Manual Workflow Run**:
   ```bash
   # Via GitHub UI: Actions → Validated Full Pipeline → Run workflow
   # Or via gh CLI:
   gh workflow run validated-full-pipeline.yml
   ```

2. **Monitor Workflow Execution**:
   ```bash
   gh run watch  # Real-time logs
   gh run list --workflow=validated-full-pipeline.yml --limit 5
   ```

3. **Check Phase Outputs**:
   - Discovery: New episodes found and stored
   - Audio: Transcripts generated and stored in database
   - Digest: Scripts created in database
   - TTS: MP3 files generated in `data/completed-tts/`
   - Publishing: GitHub releases created, database updated
   - Retention: Old files cleaned up

4. **Verify RSS Feed**:
   ```bash
   curl -s https://podcast.paulrbrown.org/daily-digest.xml | head -20
   # Should show recent episodes with valid MP3 URLs
   ```

## Prevention Measures

### 1. Add Secret Expiration Monitoring
Create a workflow to check secret validity:

```yaml
# .github/workflows/secret-health-check.yml
name: Secret Health Check
on:
  schedule:
    - cron: '0 8 * * *'  # Daily at 8am

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: python3 scripts/doctor.py
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          ELEVENLABS_API_KEY: ${{ secrets.ELEVENLABS_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GH_TOKEN }}
```

### 2. Add Workflow Notifications
Configure GitHub to send notifications on workflow failures:
- Repository Settings → Notifications
- Enable email/Slack notifications for failed workflows

### 3. Add Better Error Logging
The workflow already uses `--verbose` flags, but consider:
- Uploading full logs as artifacts on failure
- Adding phase-specific health checks before proceeding

## Next Steps

1. **Immediate**: Run `python3 scripts/doctor.py` to identify the specific failure
2. **Verify**: Check GitHub Actions logs for the actual error message
3. **Fix**: Apply appropriate solution based on diagnosis
4. **Test**: Run manual workflow to verify fix
5. **Monitor**: Watch next scheduled run (daily at 5:00 AM UTC)

## Getting Workflow Logs

Since `gh` CLI is available in the environment, retrieve actual failure logs:

```bash
# List recent workflow runs
gh run list --workflow=validated-full-pipeline.yml --limit 10

# Get specific run details
gh run view [RUN_ID]

# Download full logs
gh run download [RUN_ID] --dir workflow-logs/
```

---

**Status**: Investigation complete, awaiting diagnostic results to identify specific failure point.
