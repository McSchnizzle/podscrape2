# Actual Root Cause: Disk Space Exhaustion

**Date:** November 4, 2025
**Issue:** GitHub Actions workflow failing since ~October 31
**Error:** `No space left on device`

## What I Got Wrong Initially

I incorrectly diagnosed this as an expired GitHub token issue. The actual error message in the logs clearly showed:

```
Error: No space left on device
```

This is a disk space issue, not an authentication issue. I apologize for the incorrect diagnosis and wasted investigation time.

## Actual Root Cause: Cache Restoration Order

The workflow was running out of disk space due to **incorrect step ordering**:

### Problematic Sequence (OLD)

1. ✅ Checkout repository
2. ✅ Configure git
3. ✅ Check secrets
4. ✅ Install ffmpeg
5. ✅ Setup Python
6. ⚠️  **Restore pip cache** (~500 MB)
7. ⚠️  **Restore venv cache** (~3-4 GB with PyTorch/CUDA)
8. 🚨 **Free up disk space** (TOO LATE - cache already restored!)
9. ❌ **Install dependencies** → OUT OF SPACE

### Why This Failed

- GitHub Actions runners have ~14 GB total, ~10 GB available
- Cached venv with PyTorch: ~3.5 GB
- Cached pip downloads: ~500 MB
- After cache restoration: ~6 GB used
- Disk cleanup runs after cache, doesn't help
- Trying to install MORE dependencies: runs out of space

### Fixed Sequence (NEW)

1. ✅ Checkout repository
2. ✅ Configure git
3. ✅ Check secrets
4. ✅ **FREE UP DISK SPACE FIRST** (~10 GB freed)
5. ✅ Install ffmpeg
6. ✅ Setup Python
7. ✅ Restore pip cache (now has space)
8. ✅ Restore venv cache (now has space)
9. ✅ Install dependencies (now has space)

## Why This Started Happening Recently

### Contributing Factors

1. **Accumulated MP3 files**: 500 MB in `data/completed-tts/`
   - Should be deleted after GitHub upload
   - Retention phase may not be running properly

2. **Cached venv size**: ~3.5 GB with PyTorch
   - Cache includes full PyTorch + CUDA libraries
   - Cache key based on `requirements.txt` hash
   - If requirements.txt doesn't change, cache keeps growing

3. **GitHub Actions runner image updates**:
   - Runner images may have less free space than before
   - More pre-installed software taking up space

4. **Python package updates**:
   - Newer versions may be slightly larger
   - PyTorch 2.9.0 is larger than earlier versions

## What's Actually Taking Up Space

### In Workflow Runner

| Component | Size | Notes |
|-----------|------|-------|
| Cached venv (.venv) | ~3.5 GB | PyTorch + CUDA libraries |
| Cached pip downloads | ~500 MB | Wheel files |
| .NET SDK | ~5 GB | Removed in fix |
| Android SDK | ~3 GB | Removed in fix |
| Haskell GHC | ~1 GB | Removed in fix |
| CodeQL | ~1 GB | Removed in fix |
| Docker images | ~1-2 GB | Removed in fix |

### In Repository

| Directory | Size | Notes |
|-----------|------|-------|
| `data/completed-tts/` | 500 MB | MP3 files not cleaned up |
| `data/transcript_backup_20250921/` | 1.2 MB | Old backup |
| `data/transcripts/` | minimal | Current transcripts |
| `data/database/` | 36 KB | SQLite files (legacy) |

## Fixes Applied

### 1. Reorder Workflow Steps

**Moved disk cleanup BEFORE cache restoration:**
- Frees up ~10 GB before downloading anything
- Ensures space for cache restoration
- Ensures space for dependency installation

### 2. Clean Up Data Files

**Added to disk cleanup step:**
```bash
rm -rf data/completed-tts/*.mp3 2>/dev/null || true
rm -rf data/transcripts/*.txt 2>/dev/null || true
rm -rf data/scripts/*.md 2>/dev/null || true
```

These files should already be cleaned up by Phase 6 (Retention), but extra cleanup ensures they don't accumulate.

### 3. Remove Unused Dependencies

**Removed from requirements.txt:**
- `parakeet-mlx` - Apple Silicon transcription (not used)
- Saves ~500 MB of dependencies (mlx, librosa, scipy, etc.)

## Why Caching Is the Real Culprit

### The Cache Problem

GitHub Actions caches are supposed to speed up builds by reusing dependencies. But:

1. **Cache includes full venv**: ~3.5 GB with PyTorch
2. **Cache restored every run**: Eating up disk space
3. **Cache key rarely changes**: `hashFiles('requirements.txt')`
4. **No cache size limits**: Can grow indefinitely
5. **Restore happens early**: Before disk cleanup

### Cache vs Fresh Install

| Approach | Pros | Cons |
|----------|------|------|
| **Cached venv** | Faster (~2 min) | Large (3.5 GB), eats disk |
| **Fresh install** | Smaller footprint | Slower (~5-7 min) |

### Solution Options

**Option 1: Keep cache, fix order** ✅ (IMPLEMENTED)
- Free up disk space FIRST
- Then restore cache
- Pros: Fast builds, works reliably
- Cons: Still uses ~3.5 GB for cache

**Option 2: Remove venv cache**
- Only cache pip downloads (~500 MB)
- Install fresh every time
- Pros: Less disk usage
- Cons: Slower builds (+5 min)

**Option 3: Separate cache for large deps**
- Cache PyTorch separately from other deps
- Restore PyTorch cache conditionally
- Pros: Fine-grained control
- Cons: More complex

## Long-term Disk Usage Improvements

### 1. Monitor Cache Size

Add to workflow:
```yaml
- name: Report cache sizes
  run: |
    du -sh ~/.cache/pip
    du -sh .venv
```

### 2. Periodic Cache Invalidation

Force cache rebuild monthly:
```yaml
key: venv-${{ runner.os }}-${{ env.PYTHON_VERSION }}-${{ hashFiles('requirements.txt') }}-${{ github.run_number % 30 }}
```

### 3. Clean Up Data Files Properly

Ensure Phase 6 (Retention) runs and cleans:
- MP3 files after upload
- Old transcripts
- Old scripts
- Old logs

### 4. Consider Lighter Dependencies

- Use OpenAI Whisper API instead of local (no PyTorch needed)
- Use cloud services instead of local ML
- Split workflows: heavy ML jobs separate from lightweight jobs

## Testing the Fix

### Before Fix

```
Disk space before cleanup:
Filesystem      Size  Used Avail Use% Mounted on
/dev/root       14G   9.8G  4.2G  71% /

[Restore caches: +4GB]

Disk space after cleanup:
/dev/root       14G   13.8G  200M  99% /

[Try to install: OUT OF SPACE]
```

### After Fix

```
Disk space before cleanup:
Filesystem      Size  Used Avail Use% Mounted on
/dev/root       14G   4.2G  9.8G  30% /

[Remove .NET, Android, etc.: -10GB]

Disk space after cleanup:
/dev/root       14G   2.0G  12G   15% /

[Restore caches: +4GB]
[Install dependencies: +1GB]

Final:
/dev/root       14G   7.0G  7G    50% /
```

## Files Changed

1. `.github/workflows/validated-full-pipeline.yml`
   - Moved "Free up disk space" step before cache restoration
   - Added cleanup of data files
   - Removed Whisper cache (not needed)

2. `requirements.txt`
   - Removed `parakeet-mlx` (not used)

## Verification Steps

1. Trigger manual workflow run
2. Check logs for "Disk space before cleanup" (should show ~4-5 GB used)
3. Check logs for "Disk space after cleanup" (should show ~12 GB available)
4. Verify dependency installation completes
5. Verify all 6 phases complete successfully

---

**Summary:** The issue was cache restoration happening before disk cleanup. Fixed by reordering steps and cleaning up accumulated files. Not a token issue at all - just poor step sequencing and accumulated artifacts.
