# GitHub Publishing Workflow Learnings

## Why GitHub Releases Are a Fit
- GitHub’s documentation recommends Releases for distributing compiled or binary assets; they sit behind a CDN and avoid bloating commit history.
- Artifacts generated inside GitHub Actions expire after 90 days, so they are useful for debugging but not for podcast distribution.
- Ordinary git blobs are capped at 100 MB and cloning large binaries slows local workflows, so Releases provide a better long-term store for MP3s.

## End-to-End Persistence Checklist
- The simulator workflow generates placeholder audio with FFmpeg inside Actions; duration is configurable (we’re using 600 s to exercise >2 MB downloads).
- After generation the workflow pushes the MP3 to the `daily-YYYY-MM-DD` GitHub Release **and** commits the file under `data/completed-tts/current/` so the repo stays in sync with what publishing expects.
- The same workflow updates `data/rss/daily-digest.xml`, `public/daily-digest.xml`, and mirrors them to `data/rss/test-feed.xml` / `public/test-feed.xml`. That test feed is deployed to `podcast.paulrbrown.org/test-feed.xml`, giving us a live proof point without touching the production feed.

## Lessons from the Simulator Runs
- Very small placeholder MP3s (~5 KB) surfaced “file too small” errors in podcast clients; generating a several-minute tone (~2 MB+) avoids that and exercises the real download path.
- Keeping RSS edits minimal (string splicing instead of regenerating the entire document) makes review diffs readable and avoids churn when only the newest `<item>` changes.
- Branch targeting matters: pushing to a dedicated `simulated-tts` branch keeps repeated experiments isolated, but the test run against `main` proved we can commit and deploy in one flow when needed.

## Next Steps for Production
- Mirror the simulator pattern in the real TTS workflow: generate audio, push to Release, commit to `data/completed-tts/current/`, update RSS, and deploy `public/daily-digest.xml`.
- Consider parameterizing release tags or branch targets so we can run dry-runs on a sandbox branch before touching `main`.
- Retain the simulator workflow as a regression harness—any future changes to publishing can exercise it without burning ElevenLabs/GPT quota.

## Critical Issues Discovered in September 2025

### Root Cause: Silent GitHub Release Creation Failure + Git Push Environment Variable Bug

**Problem Pattern**: TTS phase completes successfully generating MP3 files, but publishing phase fails to update RSS feed with new episodes, leaving them marked as UNPUBLISHED in database.

**Issue 1: GitHub Release Creation Silent Failure**
- `publish_release_assets.py` script runs without visible errors in workflow logs
- Despite `--verbose` flag, no output appears from the script execution
- GitHub Release `daily-2025-09-20` was actually created successfully with MP3 assets
- Database remains UNPUBLISHED because script appeared to fail silently

**Issue 2: Environment Variable Mismatch in Git Push**
- Workflow uses `GH_REPOSITORY` in git push command but environment provides `GITHUB_REPOSITORY`
- Causes bash error: `GH_REPOSITORY: unbound variable`
- Prevents RSS updates from reaching repository even when generated successfully
- Line 267 in phase-tts.yml: `git push "https://x-access-token:${GITHUB_TOKEN}@github.com/${GH_REPOSITORY}.git"`

**Sequence of Successful Operations**:
1. ✅ TTS generation completes: `AI_and_Technology_20250920_013057.mp3` (8.9 MB)
2. ✅ GitHub Release created: `daily-2025-09-20` with MP3 asset uploaded
3. ✅ Publishing pipeline detects digest but marks as UNPUBLISHED (can't find local MP3)
4. ✅ RSS generation succeeds with 47 episodes (excludes unpublished ones)
5. ✅ Git commit succeeds: "Add TTS audio files - 2025-09-20 01:32:06"
6. ❌ Git push fails: environment variable error
7. ❌ RSS changes never reach repository or Vercel deployment

**Evidence from Logs**:
```
01:31:35 - Publishing MP3 files to GitHub Release:
01:31:35 -   Release date: 2025-09-20
01:31:35 -   Files to publish:
01:31:35 -     - data/completed-tts/current/AI_and_Technology_20250920_013057.mp3 (exists)
01:31:35 - Creating GitHub Release and uploading MP3 assets...
01:31:38 - Verifying GitHub Release was created...  [NO PUBLISH SCRIPT OUTPUT]
01:32:04 - INFO - Verifying digest: AI and Technology (2025-09-20)
01:32:04 - WARNING -   ⚠️  Digest not yet uploaded to GitHub - skipping RSS generation
01:32:05 - INFO - RSS feed should be available at: https://podcast.paulrbrown.org/daily-digest.xml
01:32:05 - {"success": true, "message": "Publishing pipeline completed successfully", "phase": "publishing"}
01:32:06 - [main e2a316e] Add TTS audio files - 2025-09-20 01:32:06
01:32:06 - /home/runner/work/_temp/...sh: line 68: GH_REPOSITORY: unbound variable
```

**Cost Impact**: Each failed workflow wastes ~$2-5 in ElevenLabs TTS API costs when MP3s are generated but never published.

### Fixes Applied

**Fix 1: Environment Variable Correction**
- Changed line 267 in `.github/workflows/phase-tts.yml`
- From: `"${GH_REPOSITORY}"` → To: `"${GITHUB_REPOSITORY}"`

**Fix 2: Enhanced Debugging for publish_release_assets.py**
- Added `--verbose` flag to script execution
- Added command echo for debugging: `echo "Command: python scripts/publish_release_assets.py --publish-date \"$RELEASE_DATE\" ${FILES[*]}"`
- Added GitHub release verification: `gh release list --repo "$GITHUB_REPOSITORY" --limit 5 || echo "Failed to list releases"`

### Verification Strategy

**Test Approach**: Run publishing-only workflow to verify RSS updates without expensive TTS generation:
1. Verify existing GitHub Release `daily-2025-09-20` contains MP3 asset
2. Create separate publishing workflow that processes existing releases
3. Confirm database status updates from UNPUBLISHED → PUBLISHED
4. Verify RSS feed includes September 20th episode
5. Confirm Vercel deployment updates podcast.paulrbrown.org

**Expected Outcome**: RSS feed should show 48 episodes (not 47) including September 20th AI & Technology digest.

### Pattern for Future Development

**GitHub Release Workflow**:
1. Generate MP3 → Create GitHub Release → Upload MP3 as release asset
2. Publishing phase finds release → Updates database status → Generates RSS
3. Git commit RSS changes → Git push with correct environment variables
4. Vercel deployment → Live RSS feed at podcast.paulrbrown.org

**Error Prevention**:
- Always test environment variable names in workflow files
- Use verbose logging for critical publishing steps
- Verify GitHub Release creation with explicit checks
- Monitor database status updates for UNPUBLISHED → PUBLISHED transitions
- Test publishing pipeline independently from TTS generation

### File References
- **Workflow**: `.github/workflows/phase-tts.yml` (lines 244-267)
- **Publisher**: `scripts/publish_release_assets.py` (GitHub Release creation)
- **Core Logic**: `src/publishing/github_publisher.py` (GitHubPublisher.create_daily_release)
- **Database**: PostgreSQL via Supabase (digest publishing status)

## RSS Publishing Path Issue - September 2025

### Root Cause: RSS Generated to Wrong Directory Location

**Problem Pattern**: Pipeline runs successfully, GitHub Releases created with MP3s, database shows PUBLISHED status, but RSS feed at podcast.paulrbrown.org/daily-digest.xml remains outdated and missing new episodes.

**Investigation Discovery**:
- RSS was being correctly generated but saved to wrong directories
- Publishing script wrote to `./public/daily-digest.xml` and `./data/rss/daily-digest.xml`
- Vercel deployment serves from `web_ui_hosted/public/` directory only
- Live RSS feed remained outdated (September 20) despite successful September 22 pipeline runs

**Core Issue**: Path resolution mismatch between local development expectations and Vercel deployment requirements.

### Evidence of the Problem

**Git Status Issues**:
- Both RSS files had unresolved merge conflict markers from previous rebase
- Repository was stuck in rebase state: `git status` showed "rebase in progress"
- GitHub Actions couldn't commit changes due to conflicted state

**Wrong Directory Usage**:
```python
# scripts/run_publishing.py - INCORRECT paths
rss_file = Path("data") / "rss" / "daily-digest.xml"          # Wrong location
public_file = Path("public") / "daily-digest.xml"             # Wrong location
```

**Expected vs Actual**:
- Expected: `web_ui_hosted/public/daily-digest.xml` (served by Vercel)
- Actual: `./public/daily-digest.xml` (not deployed)

### Fixes Applied

**1. Fixed RSS File Paths in run_publishing.py**:
```python
# Lines 278, 286, 345-346, 359 - CORRECTED paths
rss_file = Path("web_ui_hosted") / "public" / "daily-digest.xml"    # Correct location
# Removed unnecessary data/rss path entirely
```

**2. Updated GitHub Workflow Paths**:
```yaml
# .github/workflows/validated-full-pipeline.yml
# OLD (wrong):
cp data/rss/daily-digest.xml data/rss/test-feed.xml
git add data/completed-tts/current/*.mp3 data/rss/daily-digest.xml public/daily-digest.xml

# NEW (correct):
cp web_ui_hosted/public/daily-digest.xml web_ui_hosted/public/test-feed.xml
git add data/completed-tts/current/*.mp3 web_ui_hosted/public/daily-digest.xml web_ui_hosted/public/test-feed.xml
```

**3. Cleaned Up Git State**:
```bash
git rebase --abort                    # Clear conflicted rebase state
rm -rf ./public ./data/rss           # Delete unnecessary legacy directories
```

**4. Regenerated RSS Correctly**:
- Local publishing run generated RSS with all 73 digests including 4 September 22 episodes
- RSS saved to correct location: `web_ui_hosted/public/daily-digest.xml`
- Successful Vercel deployment updated live feed

### Verification Results

**Before Fix**:
- Live RSS at podcast.paulrbrown.org/daily-digest.xml showed 69 episodes (through Sept 20)
- Local `web_ui_hosted/public/daily-digest.xml` was outdated
- Four September 22 episodes missing from feed despite successful GitHub Releases

**After Fix**:
- Live RSS updated to show all current episodes including September 22
- Correct file location ensures future pipeline runs will update live feed
- GitHub Actions workflow references correct paths for commits

### Key Learnings

**Critical Path Understanding**:
- **ONLY** `web_ui_hosted/public/` directory matters for Vercel deployment
- Legacy `./public/` and `./data/rss/` directories are unnecessary and confusing
- RSS generation logic was perfect - only file paths were wrong

**Development vs Deployment Environment**:
- Local development may work with relative paths like `./public/`
- Vercel static deployment requires specific directory structure
- Always verify deployment paths match where files are actually generated

**Git State Management**:
- Conflicted rebase states block GitHub Actions commits silently
- Always check `git status` before assuming successful pipeline runs
- RSS files with merge conflict markers indicate broader git issues

**Testing Strategy**:
- Verify live RSS feed after local publishing runs
- Check file modification timestamps to confirm updates
- Test both generation logic AND file path correctness

### Prevention for Future Development

**Path Validation Checklist**:
1. Verify all file writes go to `web_ui_hosted/public/` for Vercel files
2. Test local publishing runs update live RSS feed immediately
3. Check GitHub Actions workflow references match script file paths
4. Confirm git state is clean before pipeline runs
5. Validate RSS content AND location after changes

**File Location Standards**:
- **RSS Feed**: `web_ui_hosted/public/daily-digest.xml` (served by Vercel)
- **Test Feed**: `web_ui_hosted/public/test-feed.xml` (for validation)
- **Avoid**: Any other `public/` or `data/rss/` directories

### Updated File References
- **Publishing Script**: `scripts/run_publishing.py` (lines 278, 286, 345-346, 359)
- **GitHub Workflow**: `.github/workflows/validated-full-pipeline.yml` (lines 235, 237-238)
- **Deployed RSS**: `web_ui_hosted/public/daily-digest.xml` (Vercel serving location)
- **Live Feed**: https://podcast.paulrbrown.org/daily-digest.xml
