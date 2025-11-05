# Episode Reset Guide

**Purpose:** Reset episodes from 'digested' back to 'scored' status after workflow failures.

## When to Use This

Use this script when:
- Workflows failed during the publishing phase
- Episodes were marked as 'digested' but never published to GitHub releases
- You need to re-run the digest/TTS/publishing phases on existing episodes

## Quick Start

### Option 1: Dry Run (Recommended First)

See what would be reset without making changes:

```bash
python3 scripts/reset_episodes_to_scored.py --since 2025-10-31 --dry-run
```

Expected output:
```
============================================================
Episode Status Reset Tool
============================================================

🔍 Connecting to database...
   Cutoff date: 2025-10-31 00:00:00
   Mode: DRY RUN

📊 Found 15 episodes marked as 'digested' since 2025-10-31 00:00:00

📋 Episodes to reset (showing up to 20):
   ID 123: Episode Title Here... [max score: 0.85]
      Updated: 2025-11-01 05:23:45
   ...

🔍 DRY RUN: Would reset 15 episodes from 'digested' to 'scored'
   Run without --dry-run to perform the update

============================================================
✅ Dry run complete: 15 episodes would be reset
============================================================
```

### Option 2: Perform the Reset

Once you've verified the dry run looks correct:

```bash
python3 scripts/reset_episodes_to_scored.py --since 2025-10-31
```

Expected output:
```
============================================================
Episode Status Reset Tool
============================================================

🔍 Connecting to database...
   Cutoff date: 2025-10-31 00:00:00
   Mode: LIVE UPDATE

📊 Found 15 episodes marked as 'digested' since 2025-10-31 00:00:00

📋 Episodes to reset (showing up to 20):
   ID 123: Episode Title Here... [max score: 0.85]
      Updated: 2025-11-01 05:23:45
   ...

🔄 Resetting 15 episodes from 'digested' to 'scored'...
✅ Successfully reset 15 episodes to 'scored' status
✅ Verification: No 'digested' episodes remain since 2025-10-31 00:00:00

📊 Current episode status distribution:
   scored: 45
   digested: 120
   transcribed: 8
   pending: 2

============================================================
✅ Reset complete: 15 episodes updated to 'scored' status
   These episodes will be picked up in the next workflow run
============================================================
```

## Usage Examples

### Reset episodes from October 31 onwards
```bash
python3 scripts/reset_episodes_to_scored.py --since 2025-10-31
```

### Reset episodes from November 1 onwards
```bash
python3 scripts/reset_episodes_to_scored.py --since 2025-11-01
```

### Reset only yesterday's episodes
```bash
python3 scripts/reset_episodes_to_scored.py --since 2025-11-03
```

### Dry run to preview changes
```bash
python3 scripts/reset_episodes_to_scored.py --since 2025-10-31 --dry-run
```

## Requirements

### Environment Variables

The script requires `DATABASE_URL` to be set:

```bash
export DATABASE_URL="postgresql://postgres:[password]@[host]:5432/postgres"
```

Or add it to your `.env` file:
```bash
# .env
DATABASE_URL=postgresql://postgres:[password]@[host]:5432/postgres
```

Then load it:
```bash
source .env  # or use dotenv
python3 scripts/reset_episodes_to_scored.py --since 2025-10-31
```

### Python Dependencies

```bash
pip install 'psycopg[binary]'
```

## What Happens After Reset

1. **Episodes Status:** Changed from `digested` → `scored`
2. **Next Workflow Run:** These episodes will be:
   - Picked up by digest phase (Phase 3)
   - Included in new digest scripts
   - Converted to TTS audio (Phase 4)
   - Published to GitHub releases (Phase 5)

## Episode Status Flow

Normal flow:
```
pending → processing → transcribed → scored → digested → published
```

After reset:
```
digested → scored → (workflow picks up) → digested → published
```

## Verification Steps

### 1. Check database directly

```bash
psql $DATABASE_URL -c "
SELECT status, COUNT(*)
FROM episodes
GROUP BY status
ORDER BY count DESC;
"
```

### 2. Check episodes that were reset

```bash
psql $DATABASE_URL -c "
SELECT id, title, status, updated_at
FROM episodes
WHERE status = 'scored'
AND updated_at >= '2025-10-31'::timestamp
ORDER BY updated_at DESC
LIMIT 10;
"
```

### 3. Run digest phase to confirm pickup

```bash
python3 scripts/run_digest.py --verbose --dry-run
```

Should show:
```
Found X qualifying undigested episodes for [topic]
```

## Troubleshooting

### Error: "DATABASE_URL environment variable not set"

**Solution:** Export the DATABASE_URL:
```bash
export DATABASE_URL="your_connection_string"
# or
source .env  # if you have a .env file
```

### Error: "No module named 'psycopg'"

**Solution:** Install psycopg:
```bash
pip install 'psycopg[binary]'
```

### Error: "Temporary failure in name resolution"

**Solution:** Check network connectivity to database:
```bash
ping aws-1-us-west-1.pooler.supabase.com
# or
curl https://aws-1-us-west-1.pooler.supabase.com
```

If ping fails, check firewall/VPN settings.

### Found 0 episodes to reset

**Possible reasons:**
1. No episodes were marked as digested since the cutoff date
2. Episodes were digested before the cutoff date (use earlier --since date)
3. Episodes already reset previously

**Check with SQL:**
```bash
psql $DATABASE_URL -c "
SELECT status, COUNT(*), MIN(updated_at), MAX(updated_at)
FROM episodes
GROUP BY status;
"
```

## Safety Features

1. **Dry Run Mode:** Always preview changes before applying
2. **Date Filtering:** Only affects episodes updated after specified date
3. **Transaction Safety:** Database changes are committed in a single transaction
4. **Verification:** Script verifies the update after completion
5. **Detailed Logging:** Shows exactly which episodes are affected

## Integration with Workflow

After resetting episodes:

### Manual Workflow Trigger
```bash
# Go to GitHub Actions UI
# Select "Validated Full Pipeline"
# Click "Run workflow"
```

### Or use workflow dispatch (if you have gh CLI)
```bash
gh workflow run validated-full-pipeline.yml
```

### Or schedule will pick it up
The daily workflow runs at 5:00 AM UTC automatically.

## Related Files

- **Script:** `scripts/reset_episodes_to_scored.py`
- **Digest Phase:** `scripts/run_digest.py`
- **Full Pipeline:** `run_full_pipeline_orchestrator.py`
- **Workflow:** `.github/workflows/validated-full-pipeline.yml`

## Best Practices

1. **Always dry run first** to verify changes
2. **Use specific dates** rather than resetting everything
3. **Check episode count** before and after reset
4. **Verify workflow picks them up** with a test run
5. **Document why you reset** in your notes/changelog

---

**Created:** November 4, 2025
**Purpose:** Support workflow failure recovery after token issues
