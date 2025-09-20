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
