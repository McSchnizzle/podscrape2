# Migration Plan: Move Podcast Cron Jobs from GitHub Actions to et01 Server

**Created:** 2026-01-25
**Reference:** This plan follows the successful migration pattern used for the calendar project (see `../calendar/docs/server-cron-setup.md`)

---

## Overview

The podcast project currently runs a daily pipeline via GitHub Actions (`validated-full-pipeline.yml`) at 5:00 AM UTC. This plan migrates that cron job to the et01 server to:
- Eliminate GitHub Actions billing/usage limits
- Provide full control over scheduling
- Enable faster execution (no container spin-up)
- Allow direct log access and monitoring

---

## Current GitHub Actions Cron Jobs

### Primary Cron Job (the only scheduled one)
| Workflow | Schedule | Purpose |
|----------|----------|---------|
| `validated-full-pipeline.yml` | `0 5 * * *` (5 AM UTC / 9 PM Pacific) | Full 6-phase pipeline |

### Manual-Only Workflows (no migration needed)
- `publishing-only.yml` - Manual publishing
- `ci-bootstrap.yml` - Environment validation
- `tts-simulator.yml` - Test audio generation
- `tts-simulator-commit.yml` - Test with commit

---

## Migration Steps

### Step 1: Create Directory Structure on et01

```bash
ssh et01
mkdir -p ~/podcast-pipeline ~/podcast-pipeline/data ~/logs
```

### Step 2: Copy Backend Code

From your local machine:
```bash
rsync -avz --exclude='.venv' --exclude='__pycache__' --exclude='.pytest_cache' \
  --exclude='data/completed-tts' --exclude='data/transcripts' --exclude='*.mp3' \
  /Users/paulbrown/Desktop/coding-projects/podcast/ et01:~/podcast-pipeline/
```

**Note:** Exclude large data directories - they'll be created fresh on the server.

### Step 3: Install System Dependencies

```bash
ssh et01

# Check Python version (needs 3.13+)
python3 --version

# If Python 3.13 not available, install it:
# sudo apt update && sudo apt install python3.13 python3.13-venv

# Install ffmpeg (required for audio processing)
sudo apt update && sudo apt install ffmpeg -y

# Verify ffmpeg
ffmpeg -version
```

### Step 4: Create Virtual Environment and Install Dependencies

```bash
cd ~/podcast-pipeline

# Create virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install torch with CPU-only index to avoid CUDA bloat (~2GB saved)
pip install torch --index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies
pip install -r requirements.txt

# Verify installation
python -c "import openai; import elevenlabs; import sqlalchemy; print('Dependencies OK')"
```

### Step 5: Configure Environment Variables

Create the `.env` file on the server:

```bash
# Option A: Copy from local machine
scp /Users/paulbrown/Desktop/coding-projects/podcast/.env et01:~/podcast-pipeline/.env

# Option B: Or create manually with required variables
ssh et01
cat > ~/podcast-pipeline/.env << 'EOF'
# APIs
OPENAI_API_KEY=sk-...
ELEVENLABS_API_KEY=...

# Database (Supabase PostgreSQL)
DATABASE_URL=postgresql+psycopg://user:password@host:port/db

# GitHub Publishing
GITHUB_TOKEN=ghp_...
GITHUB_REPOSITORY=McSchnizzle/podcast-pipeline

# RSS
RSS_PUBLIC_URL=https://podcast.paulrbrown.org/daily-digest.xml

# Transcription
STT_PROVIDER=openai
WHISPER_MODEL=base

# Logging
LOG_LEVEL=INFO
DATA_ROOT=./data
EOF
```

**Important:** Verify all environment variables are set correctly:
```bash
cd ~/podcast-pipeline
source .venv/bin/activate
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print('DATABASE_URL:', os.getenv('DATABASE_URL')[:50] + '...' if os.getenv('DATABASE_URL') else 'MISSING')"
```

### Step 6: Test Database Connection

```bash
cd ~/podcast-pipeline
source .venv/bin/activate

python -c "
from dotenv import load_dotenv
load_dotenv()
from src.database.connection import get_engine
from sqlalchemy import text
engine = get_engine()
with engine.connect() as conn:
    result = conn.execute(text('SELECT 1'))
    print('Database connection: OK')
"
```

### Step 7: Test Individual Pipeline Phases

Run each phase manually to verify they work:

```bash
cd ~/podcast-pipeline
source .venv/bin/activate

# Test Phase 1 - Discovery (quick, safe to run)
python scripts/run_discovery.py --verbose --dry-run

# If that works, test Phase 2 with limited scope
# python scripts/run_audio.py --verbose --limit 1
```

### Step 8: Create Pipeline Runner Script

Create a wrapper script that handles logging and error reporting:

```bash
cat > ~/podcast-pipeline/run_daily_pipeline.sh << 'EOF'
#!/bin/bash
# Daily podcast pipeline runner for et01 server
# Runs the full 6-phase pipeline with logging

set -e

PIPELINE_DIR="$HOME/podcast-pipeline"
LOG_DIR="$HOME/logs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/podcast-pipeline-$TIMESTAMP.log"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

cd "$PIPELINE_DIR"
source .venv/bin/activate

echo "========================================" | tee -a "$LOG_FILE"
echo "Podcast Pipeline Started: $(date)" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# Run the full pipeline orchestrator
python run_full_pipeline_orchestrator.py --verbose 2>&1 | tee -a "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}

echo "========================================" | tee -a "$LOG_FILE"
echo "Pipeline Completed: $(date)" | tee -a "$LOG_FILE"
echo "Exit Code: $EXIT_CODE" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# Keep only last 14 days of logs
find "$LOG_DIR" -name "podcast-pipeline-*.log" -mtime +14 -delete

exit $EXIT_CODE
EOF

chmod +x ~/podcast-pipeline/run_daily_pipeline.sh
```

### Step 9: Test the Runner Script

```bash
# Run a test (this will execute the full pipeline - ensure you're ready)
~/podcast-pipeline/run_daily_pipeline.sh

# Or run with dry-run first if the orchestrator supports it
cd ~/podcast-pipeline && source .venv/bin/activate
python run_full_pipeline_orchestrator.py --verbose --dry-run
```

### Step 10: Set Up Cron Job

```bash
crontab -e
```

Add the following entry:

```cron
# ============================================
# PODCAST PIPELINE CRON JOBS
# ============================================

# Full pipeline - 9 PM Pacific daily
# (Server is in Pacific time)
0 21 * * * /home/pbrown/podcast-pipeline/run_daily_pipeline.sh >> /home/pbrown/logs/podcast-cron.log 2>&1
```

### Step 11: Verify Cron Job

```bash
# List cron jobs
crontab -l | grep -A5 'PODCAST PIPELINE'

# Check cron service is running
systemctl status cron
```

### Step 12: Disable GitHub Actions Schedule

Edit `.github/workflows/validated-full-pipeline.yml`:

```yaml
name: Validated Full Pipeline

on:
  # DISABLED: Cron job moved to et01 server (Jan 2026)
  # schedule:
  #   - cron: '0 5 * * *'
  workflow_dispatch:  # Keep manual trigger for emergencies
    inputs:
      # ... keep existing inputs ...
```

Commit and push:
```bash
git add .github/workflows/validated-full-pipeline.yml
git commit -m "chore: Disable GitHub Actions cron - moved to et01 server

Cron job now runs on et01 server at 9 PM Pacific daily.
Manual workflow_dispatch trigger preserved for emergencies.

See docs/server-cron-setup.md for server configuration."
git push
```

---

## Monitoring

### Check Logs

```bash
# Live pipeline log
tail -f ~/logs/podcast-pipeline-*.log

# Cron execution log
tail -f ~/logs/podcast-cron.log

# Most recent pipeline run
ls -lt ~/logs/podcast-pipeline-*.log | head -1 | xargs tail -100
```

### Check Pipeline Status

```bash
# Check if pipeline is currently running
ps aux | grep run_full_pipeline

# Check recent cron executions
grep CRON /var/log/syslog | tail -20
```

### Database Health Check

```bash
cd ~/podcast-pipeline && source .venv/bin/activate
python -c "
from dotenv import load_dotenv
load_dotenv()
from src.database.connection import get_engine
from sqlalchemy import text
engine = get_engine()
with engine.connect() as conn:
    # Check recent pipeline runs
    result = conn.execute(text('''
        SELECT created_at, status, phase
        FROM pipeline_logs
        ORDER BY created_at DESC
        LIMIT 5
    '''))
    print('Recent pipeline runs:')
    for row in result:
        print(f'  {row[0]} - {row[1]} - {row[2]}')
"
```

---

## Updating the Code

When the podcast code changes, sync the updates:

```bash
# From local machine
rsync -avz --exclude='.venv' --exclude='__pycache__' --exclude='.pytest_cache' \
  --exclude='data/completed-tts' --exclude='data/transcripts' --exclude='*.mp3' \
  /Users/paulbrown/Desktop/coding-projects/podcast/ et01:~/podcast-pipeline/

# Then on the server, update dependencies if needed:
ssh et01 "cd ~/podcast-pipeline && source .venv/bin/activate && pip install -r requirements.txt"
```

---

## Troubleshooting

### Pipeline Not Running

1. Check cron service: `systemctl status cron`
2. Check cron logs: `grep CRON /var/log/syslog | tail -20`
3. Verify script permissions: `ls -la ~/podcast-pipeline/run_daily_pipeline.sh`
4. Test script manually: `~/podcast-pipeline/run_daily_pipeline.sh`

### Database Connection Issues

1. Test connection:
   ```bash
   cd ~/podcast-pipeline && source .venv/bin/activate
   python -c "from src.database.connection import get_engine; get_engine().connect(); print('OK')"
   ```
2. Check `.env` file exists and has correct values
3. Verify Supabase credentials haven't expired

### API Errors (OpenAI/ElevenLabs)

1. Check API keys in `.env`
2. Verify API quotas/limits aren't exceeded
3. Test API connectivity:
   ```bash
   cd ~/podcast-pipeline && source .venv/bin/activate
   python -c "import openai; client = openai.OpenAI(); print('OpenAI OK')"
   ```

### Disk Space Issues

The pipeline can use significant disk space for audio files. Monitor and clean up:

```bash
# Check disk usage
df -h ~

# Check data directory size
du -sh ~/podcast-pipeline/data/*

# Manual cleanup if needed (retention script should handle this)
cd ~/podcast-pipeline && source .venv/bin/activate
python scripts/run_retention.py --verbose
```

### GitHub Publishing Failures

1. Verify `GITHUB_TOKEN` is valid and has `contents: write` permission
2. Check token hasn't expired
3. Test GitHub API:
   ```bash
   cd ~/podcast-pipeline && source .venv/bin/activate
   python -c "
   from github import Github
   import os
   from dotenv import load_dotenv
   load_dotenv()
   g = Github(os.getenv('GITHUB_TOKEN'))
   repo = g.get_repo(os.getenv('GITHUB_REPOSITORY'))
   print(f'GitHub OK: {repo.full_name}')
   "
   ```

---

## Rollback to GitHub Actions

If needed, re-enable GitHub Actions by uncommenting the schedule trigger in:
- `.github/workflows/validated-full-pipeline.yml`

Note: Address any GitHub billing issues first.

---

## Server Details

- **Server**: et01 (vtmp-hst-et01)
- **User**: pbrown
- **Code Location**: `/home/pbrown/podcast-pipeline`
- **Log Location**: `/home/pbrown/logs/`
- **Python**: 3.13+ (verify with `python3 --version`)
- **Virtual Environment**: `/home/pbrown/podcast-pipeline/.venv`

---

## Checklist

- [ ] Directory structure created on et01
- [ ] Code synced via rsync
- [ ] Python 3.13+ available
- [ ] ffmpeg installed
- [ ] Virtual environment created
- [ ] Dependencies installed
- [ ] `.env` file configured with all required variables
- [ ] Database connection tested
- [ ] Individual pipeline phases tested
- [ ] Runner script created and tested
- [ ] Cron job added
- [ ] GitHub Actions schedule disabled
- [ ] Documentation updated
- [ ] First automated run verified

---

## Related Documentation

- Calendar project server setup: `../calendar/docs/server-cron-setup.md`
- Pipeline architecture: `README.md`
- Environment variables: `CLAUDE.md`
