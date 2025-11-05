# Workflow Fix Instructions

**Issue:** GitHub App cannot update workflow files (requires `workflows` permission)
**Solution:** Apply workflow changes manually via GitHub UI

## Summary of Root Cause

The workflow was running out of disk space because:
1. **Cache restoration happened BEFORE disk cleanup**
2. Cached venv (~3.5 GB PyTorch) + pip (~500 MB) filled disk
3. No space left for dependency installation

## Changes Required

The workflow file `.github/workflows/validated-full-pipeline.yml` needs these changes:

### 1. Move "Free up disk space" step EARLIER

**Current order (WRONG):**
```
- Check secrets
- Install ffmpeg
- Setup Python
- Restore pip cache ← 500MB restored
- Restore venv cache ← 3.5GB restored
- Cache Whisper models
- Free up disk space ← TOO LATE!
- Install dependencies ← OUT OF SPACE
```

**New order (CORRECT):**
```
- Check secrets
- Free up disk space ← RUNS FIRST (~10GB freed)
- Install ffmpeg
- Setup Python
- Restore pip cache ← Now has space
- Restore venv cache ← Now has space
- Install dependencies ← Now has space
```

### 2. Remove "Cache Whisper models" step

This cache is not needed since disk cleanup frees up enough space.

### 3. Add data file cleanup

Add these lines to the disk cleanup step:
```bash
# Clean up old data files that may have accumulated
rm -rf data/completed-tts/*.mp3 2>/dev/null || true
rm -rf data/transcripts/*.txt 2>/dev/null || true
rm -rf data/scripts/*.md 2>/dev/null || true
```

## Option 1: Apply Via GitHub UI (Recommended)

### Step 1: Go to the workflow file

https://github.com/McSchnizzle/podscrape2/blob/main/.github/workflows/validated-full-pipeline.yml

### Step 2: Click "Edit this file" (pencil icon)

### Step 3: Find the "Ensure required secrets present" step

It should look like this:
```yaml
      - name: Ensure required secrets present
        run: |
          missing=()
          for var in DATABASE_URL OPENAI_API_KEY GITHUB_TOKEN GITHUB_REPOSITORY; do
            if [ -z "${!var}" ]; then
              missing+=("$var")
            fi
          done
          if [ ${#missing[@]} -gt 0 ]; then
            echo "Missing secrets: ${missing[*]}" >&2
            exit 1
          fi
```

### Step 4: Add the "Free up disk space" step RIGHT AFTER IT

Add this entire block:
```yaml
      - name: Free up disk space
        run: |
          echo "Disk space before cleanup:"
          df -h

          # Remove unnecessary software to free up ~10GB
          sudo rm -rf /usr/share/dotnet
          sudo rm -rf /usr/local/lib/android
          sudo rm -rf /opt/ghc
          sudo rm -rf /opt/hostedtoolcache/CodeQL

          # Clean apt cache
          sudo apt-get clean

          # Remove docker images
          docker rmi $(docker images -q) -f 2>/dev/null || true

          # Clean up old data files that may have accumulated
          rm -rf data/completed-tts/*.mp3 2>/dev/null || true
          rm -rf data/transcripts/*.txt 2>/dev/null || true
          rm -rf data/scripts/*.md 2>/dev/null || true

          echo "Disk space after cleanup:"
          df -h
```

### Step 5: Find and DELETE the "Cache Whisper models" step

Find this block and DELETE IT:
```yaml
      - name: Cache Whisper models
        uses: actions/cache@v4
        with:
          path: |
            ~/.cache/whisper
            ~/.cache/torch
          key: whisper-${{ runner.os }}-${{ env.PYTHON_VERSION }}
          restore-keys: |
            whisper-${{ runner.os }}-
```

### Step 6: Update the "Install dependencies" comment

Find this line:
```yaml
          python -m pip install -r requirements.txt
```

Change it to:
```yaml
          # Use regular requirements (disk cleanup step freed up ~10GB)
          python -m pip install -r requirements.txt
```

### Step 7: Commit the changes

- Commit message: `fix: Resolve disk space issue - move cleanup before cache restoration`
- Commit directly to `main` or create a PR

## Option 2: Apply Patch File

If you prefer to apply via command line:

```bash
# Apply the patch
git apply workflow-fix.patch

# Commit
git add .github/workflows/validated-full-pipeline.yml
git commit -m "fix: Resolve disk space issue - move cleanup before cache restoration"

# Push
git push origin main
```

## Verification

After applying the fix:

1. **Trigger manual workflow run:**
   - Go to Actions → Validated Full Pipeline
   - Click "Run workflow"

2. **Check the logs:**
   - Look for "Disk space before cleanup" (should show ~4-5 GB used)
   - Look for "Disk space after cleanup" (should show ~12 GB available)
   - Verify "Installing collected packages" completes without errors

3. **Verify all phases complete:**
   - Phase 1: Discovery
   - Phase 2: Audio Processing
   - Phase 3: Digest Generation
   - Phase 4: TTS Audio Generation
   - Phase 5: Publishing
   - Phase 6: Retention Management

## Expected Results

### Before Fix
```
Disk space before cleanup: 9.8G used, 4.2G avail
[Restore caches: +4GB]
Installing collected packages...
Error: No space left on device
```

### After Fix
```
Disk space before cleanup: 4.2G used, 9.8G avail
[Remove .NET, Android, etc.: -10GB]
Disk space after cleanup: 2.0G used, 12G avail
[Restore caches: +4GB]
Installing collected packages... ✅ SUCCESS
```

## Related Files

- `ACTUAL_ROOT_CAUSE.md` - Detailed explanation of the issue
- `workflow-fix.patch` - Patch file with the changes
- `requirements.txt` - Updated (parakeet-mlx removed)
- `web_ui_hosted/app/version.ts` - Updated to v1.76

## Questions?

If you have questions or the fix doesn't work, check:
1. Did the disk cleanup step run BEFORE cache restoration?
2. Are the data file cleanup commands included?
3. Was the Whisper cache step removed?
4. Do the workflow logs show ~12GB available after cleanup?

---

**Status:** Changes documented, manual application required
**Version:** v1.76
**Date:** November 4, 2025
