# podcast (podscrape2)

## What This Is
RSS podcast digest system - automated daily topic-based digests from podcast transcripts.

**Status:** Production (v1.84, November 2025)  
**GitHub Repo:** https://github.com/McSchnizzle/podscrape2  
**Live RSS Feed:** https://podcast.paulrbrown.org/daily-digest.xml  
**Web UI:** https://podcast.paulrbrown.org (Vercel)

## Architecture Overview

This is a **multi-location project** with a specific workflow:

```
┌─────────────────────────────────────────────────────────┐
│ Local Mac (~/Desktop/coding-projects/podcast)          │
│ - PRIMARY development location                          │
│ - Git repo (origin: github.com/McSchnizzle/podscrape2) │
│ - Code editing happens here                             │
└────────────────┬────────────────────────────────────────┘
                 │
                 │ (git push)
                 ▼
          ┌─────────────┐
          │   GitHub    │
          │  (main)     │──────────► Vercel (auto-deploy)
          └─────────────┘            podcast.paulrbrown.org
                 │
                 │ (manual deploy/sync)
                 ▼
┌─────────────────────────────────────────────────────────┐
│ et01 (/srv/projects/podcast-pipeline)                  │
│ - NOT a git repo (just deployed code)                  │
│ - Runs production cron jobs (6 AM daily)               │
│ - Phase changes deployed from local to keep in sync    │
└─────────────────────────────────────────────────────────┘
```

## Why This Setup?

**Problem:** GitHub Actions bandwidth limits were exceeded by long-running cron jobs  
**Solution:** Move cron execution to et01 (work server Paul controls)

**Development Flow:**
1. Edit code locally on Mac
2. Push to GitHub (triggers Vercel deployment for frontend)
3. Deploy backend changes to et01 manually when phase code changes
4. et01 runs the production pipeline on schedule

## Locations

| Location | Path | Purpose | Git? |
|----------|------|---------|------|
| **Local** | `~/Desktop/coding-projects/podcast` | Development, source of truth | ✅ Yes |
| **GitHub** | `github.com/McSchnizzle/podscrape2` | Remote repo, CI/CD trigger | ✅ Yes |
| **Vercel** | podcast.paulrbrown.org | Frontend hosting (Next.js) | Auto-deploy from main |
| **et01** | `/srv/projects/podcast-pipeline` | Production cron jobs | ❌ No (deployed code) |

## Related Projects

**Calendar:** Similar setup - local development, et01 cron jobs  
See: `~/Desktop/coding-projects/calendar` and et01 calendar-sync

## Deployment Workflow

### Frontend (Vercel)
- **Automatic:** Push to GitHub main branch → Vercel auto-deploys
- **Site:** https://podcast.paulrbrown.org

### Backend (et01)
- **Automatic:** Pre-commit hook deploys changes via `scripts/deploy_to_et01.sh`
- **Method:** `rsync -avz` (excludes .venv, node_modules, data, logs, .env)
- **Schedule:** Cron runs daily at 1:00 PM PST (21:00 UTC)
- **Wrapper Script:** `run_daily_pipeline.sh` (added 2026-02-07)

### CLI Tools Available
- ✅ `vercel` - Vercel CLI (works locally)
- ✅ `gh` - GitHub CLI
- ✅ `supabase` - Supabase CLI
- ✅ `railway` - Railway CLI (works locally, issues on et01)

## Database Access

See: `et01:/srv/projects/podcast-pipeline/MAUDE.md` for:
- Supabase connection details
- Query examples
- Schema documentation

## GitHub Auth

Check with:
```bash
cd ~/Desktop/coding-projects/podcast && gh auth status
```

## Past Work

### 2026-02-07: Production Outage - Missing Cron Script
- **Incident:** No episodes published Feb 6-7 (2 days of missed content)
- **Root Cause:** Cron job referenced non-existent `run_daily_pipeline.sh`
- **Fix:** Created missing wrapper script, committed to git (80daba9)
- **Deployment:** Auto-deployed via pre-commit hook to et01
- **Documentation:** See `PODCAST_OUTAGE_POSTMORTEM_2026-02-07.md`
- **Next Run:** Feb 8 at 1:00 PM PST (will catch up missed episodes)
- **Lesson:** If it's in docs/config, it must be in version control

### 2026-02-05: Architecture Documentation
- Documented multi-location setup (local → GitHub → Vercel + et01)
- Clarified why cron jobs moved to et01 (GitHub Actions bandwidth limits)
- Noted deployment workflow

### 2026-02-05: Database Query Investigation
- See: `et01:/srv/projects/podcast-pipeline/MAUDE.md` for database work

## Recurring Issues

### Infrastructure Drift (2026-02-07)
- **Pattern:** Documentation/config references files that don't exist in git
- **Example:** Cron job called `run_daily_pipeline.sh` which was never committed
- **Prevention:** Always commit infrastructure scripts; use pre-commit hooks
- **Check:** Before deploying, verify file exists in git repo

## Important Context

### 6-Phase Pipeline
1. **Discovery** - Find new episodes from RSS feeds
2. **Audio** - Download, transcribe (OpenAI Whisper), score (GPT-4o-mini)
3. **Digest** - Generate topic-based scripts (GPT-4o)
4. **TTS** - Convert to audio (ElevenLabs)
5. **Publishing** - Upload to GitHub Releases, update database
6. **Retention** - Cleanup old files/records

### Key Files
- **README.md** - Full project documentation
- **run_full_pipeline_orchestrator.py** - Production orchestrator (runs on et01)
- **web_ui_hosted/** - Next.js frontend (deploys to Vercel)

### Cron Schedule (et01)
- **Daily Execution:** 1:00 PM PST (21:00 UTC)
- **Crontab:** `0 21 * * * /srv/projects/podcast-pipeline/run_daily_pipeline.sh`
- **Wrapper:** `run_daily_pipeline.sh` calls orchestrator with proper environment
- **Command:** `timeout 15m python3 run_full_pipeline_orchestrator.py --verbose --days-back 5 --limit 10`
- **Logs:** `/home/pbrown/logs/podcast-cron.log` (wrapper) and `/srv/projects/podcast-pipeline/logs/` (orchestrator)

---

**Last Updated:** 2026-02-07 by Maude 🌻 (Outage investigation & fix)
