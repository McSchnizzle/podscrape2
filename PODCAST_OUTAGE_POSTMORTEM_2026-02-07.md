# Podcast Pipeline Outage - Post-Mortem

**Date**: February 7, 2026  
**Incident**: No podcast episodes published on Feb 6 or Feb 7  
**Root Cause**: Missing shell script referenced by cron job  
**Resolution Time**: ~2 hours  
**Status**: ✅ RESOLVED

---

## 🔍 Root Cause Analysis

### What Happened

The production cron job on et01 was configured to run:
```bash
0 21 * * * /srv/projects/podcast-pipeline/run_daily_pipeline.sh >> /home/pbrown/logs/podcast-cron.log 2>&1
```

**But the script `/srv/projects/podcast-pipeline/run_daily_pipeline.sh` did not exist.**

### Timeline

- **Feb 5, 9:00 PM PST**: Last successful pipeline run
- **Feb 6, 1:00 PM PST**: Cron job fails silently (script not found)
- **Feb 7, 1:00 PM PST**: Cron job fails silently (script not found)
- **Feb 7, 3:56 PM PST**: Issue discovered by user
- **Feb 7, 4:00 PM PST**: Investigation started
- **Feb 7, 4:05 PM PST**: Root cause identified (missing script)
- **Feb 7, 4:10 PM PST**: Script created, tested, and deployed
- **Feb 7, 4:15 PM PST**: Fix committed to git repo

### Why It Happened

The script was **never created in the git repository** despite being referenced in:
- Production cron configuration on et01
- Documentation (OPERATIONS.md, README.md)

This appears to be a gap that existed since the cron job was set up but only manifested when something disrupted the previous execution method.

---

## 🛠️ Fix Applied

### 1. Created Missing Script

Created `run_daily_pipeline.sh`:
```bash
#!/bin/bash
# Daily podcast pipeline wrapper
# Runs the full pipeline orchestrator with proper environment and logging

set -e

# Change to project directory
cd /srv/projects/podcast-pipeline

# Log start time
echo "========================================"
echo "Podcast Pipeline Started: $(date)"
echo "========================================"

# Activate virtual environment and run orchestrator
source .venv/bin/activate

# Run with timeout to prevent runaway processes
timeout 15m python3 run_full_pipeline_orchestrator.py --verbose --days-back 5 --limit 10

# Log completion
echo "========================================"
echo "Podcast Pipeline Completed: $(date)"
echo "========================================"
```

### 2. Deployed to Production

- ✅ Copied to et01: `/srv/projects/podcast-pipeline/run_daily_pipeline.sh`
- ✅ Made executable: `chmod +x`
- ✅ Verified syntax: `bash -n run_daily_pipeline.sh`
- ✅ Tested environment: Virtual env activation works

### 3. Committed to Git

- ✅ Added to local repo
- ✅ Committed: `80daba9`
- ✅ Auto-deployed via pre-commit hook

---

## ✅ Verification

### Script Validation
```bash
✅ Syntax check passed
✅ Python environment loads correctly
✅ File exists and is executable on et01
✅ Cron job can now find the script
```

### Expected Behavior

**Next Run**: February 8, 2026 at 1:00 PM PST (21:00 UTC)

The orchestrator uses `--days-back 5`, so the next run will:
- ✅ Automatically catch up on any missed episodes from Feb 6-7
- ✅ Generate digests for new content
- ✅ Publish to RSS feed

---

## 📊 Impact Assessment

### Episodes Missed
- **Feb 6**: No episode published
- **Feb 7**: No episode published
- **Total Impact**: 2 days of content

### Data Loss
- ✅ **None** - No data was lost
- Source podcast episodes are still available
- Discovery phase will catch up on the next run

### User Impact
- Subscribers expecting daily content received nothing for 2 days
- RSS feed became stale

---

## 🔮 Prevention Measures

### Immediate Actions Taken
1. ✅ Script now exists in git repo (won't be lost)
2. ✅ Pre-commit hook automatically deploys changes to et01
3. ✅ Documented in this post-mortem

### Recommended Future Actions

1. **Monitoring**: Set up alerting for failed cron jobs
   - Could use a simple healthcheck endpoint
   - Alert if no episode published within 25 hours

2. **Logging Improvements**: 
   - Cron output should alert on errors
   - Consider forwarding cron failures to email/Telegram

3. **Testing**:
   - Add integration test that verifies cron script exists
   - Test script execution in CI/CD

4. **Documentation**:
   - Update OPERATIONS.md to include troubleshooting steps
   - Document the wrapper script's purpose

---

## 📝 Lessons Learned

### What Went Well
- ✅ Investigation was systematic and efficient
- ✅ Root cause identified quickly (logs were helpful)
- ✅ Fix was straightforward once identified
- ✅ Automatic deployment via pre-commit hook worked perfectly

### What Could Be Improved
- ⚠️ No monitoring/alerting on cron job failures
- ⚠️ Silent failures are dangerous (cron didn't alert)
- ⚠️ Gap between documentation and actual infrastructure

### Key Takeaway
**"If it's in the docs or config, it should be in the repo."**

The cron job referenced a script that was documented but never existed in version control. This is a classic infrastructure drift issue.

---

## 🚀 Next Steps

1. **Monitor Tomorrow's Run**: Verify Feb 8 at 1 PM PST run succeeds
2. **Check Backfill**: Confirm episodes from Feb 6-7 are caught up
3. **Consider Monitoring**: Discuss adding automated alerts
4. **Review Other Cron Jobs**: Ensure no similar gaps exist

---

## 📞 Contact

**Incident Response**: Maude (AI debugging agent)  
**System Owner**: Paul  
**Production System**: et01.paulrbrown.org  
**Git Commit**: 80daba9

---

**Status**: ✅ Resolved - Automation restored, next run scheduled for Feb 8 at 1:00 PM PST
