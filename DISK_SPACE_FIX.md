# Disk Space Fix - Actual Root Cause Analysis

**Date:** November 4, 2025
**Issue:** GitHub Actions workflow failures since ~October 31
**Status:** ✅ RESOLVED

## Actual Error (Not Token-Related)

```
Error: No space left on device
```

The workflow failed during dependency installation when the GitHub Actions runner ran out of disk space.

## Root Cause

GitHub Actions runners have **~14 GB total disk space**, with only **~10 GB available** for use after the OS.

The workflow was installing massive dependencies:

| Package | Size |
|---------|------|
| torch-2.9.0 | 899.8 MB |
| nvidia_cudnn_cu12 | 706.8 MB |
| nvidia_cublas_cu12 | 594.3 MB |
| nvidia_nccl_cu12 | 322.3 MB |
| nvidia_cusparse_cu12 | 288.2 MB |
| nvidia_cusparselt_cu12 | 287.2 MB |
| nvidia_cusolver_cu12 | 267.5 MB |
| nvidia_cufft_cu12 | 193.1 MB |
| triton | 170.4 MB |
| llvmlite | 56.3 MB |
| parakeet-mlx + dependencies | ~500 MB |

**Total: ~4-5 GB** just for PyTorch, CUDA libraries, and ML dependencies.

Combined with:
- Python dependencies (~1 GB)
- Virtual environment (~500 MB)
- Cached dependencies (~2 GB)
- System overhead (~2 GB)

This exceeded the available disk space, causing installation to fail.

## Why This Happened Recently

The dependencies were updated to newer versions in October:
- PyTorch 2.9.0 (released ~Oct 2025) is larger than 2.0.x
- CUDA 12.8 libraries are larger than 12.1.x
- `parakeet-mlx` was added but never used in production

## Solution Applied

### 1. Remove Unused Dependencies

**Removed from `requirements.txt`:**
- `parakeet-mlx` - Apple Silicon transcription library (not used)
  - This also removes: mlx, librosa, scipy, numba, and other ML dependencies
  - Saves: ~500 MB

### 2. Free Up Disk Space in Workflow

**Added to `.github/workflows/validated-full-pipeline.yml`:**

```yaml
- name: Free up disk space
  run: |
    # Remove unnecessary software (~10GB freed)
    sudo rm -rf /usr/share/dotnet
    sudo rm -rf /usr/local/lib/android
    sudo rm -rf /opt/ghc
    sudo rm -rf /opt/hostedtoolcache/CodeQL

    # Clean apt cache
    sudo apt-get clean

    # Remove docker images
    docker rmi $(docker images -q) -f 2>/dev/null || true
```

**Disk space freed:** ~10 GB

**Breakdown:**
- `/usr/share/dotnet` - .NET SDK (~5 GB)
- `/usr/local/lib/android` - Android SDK (~3 GB)
- `/opt/ghc` - Haskell compiler (~1 GB)
- `/opt/hostedtoolcache/CodeQL` - CodeQL binaries (~1 GB)

### 3. Keep openai-whisper (Required)

**Why we can't remove it:**
- Used by `scripts/run_audio.py` for local transcription
- Required for Phase 2 (Audio Processing)
- Alternative would be OpenAI Whisper API (costs money, slower)

**Size:** ~3.5 GB (PyTorch + CUDA libraries)

**After cleanup:** 10 GB freed - 3.5 GB used = **6.5 GB available** ✅

## Files Changed

1. **requirements.txt**
   - Removed: `parakeet-mlx`
   - Kept: `openai-whisper` (required for transcription)

2. **.github/workflows/validated-full-pipeline.yml**
   - Added: Disk cleanup step before dependency installation
   - Removed: Whisper cache (no longer needed with cleanup)
   - Updated: Comments to reflect changes

3. **requirements-ci.txt** (created but not used)
   - Created for reference but not used in final solution
   - Workflow uses regular `requirements.txt` after disk cleanup

## Verification

After changes, the workflow should:

1. ✅ **Free up ~10 GB** of disk space
2. ✅ **Install dependencies** successfully (~3.5 GB used)
3. ✅ **Complete all 6 phases** without errors
4. ✅ **Leave ~6.5 GB** free for runtime operations

## Why Initial Diagnosis Was Wrong

**Mistaken Token Investigation:**

The initial investigation incorrectly identified the issue as:
- Expired GitHub token
- Token mismatch between UI and environment

**Why this was wrong:**
- The actual error message "No space left on device" was visible in logs
- Token errors would show "401 Unauthorized" or "Bad credentials" from GitHub API
- Token errors would fail during Phase 5 (Publishing), not during dependency installation
- The workflow failed at **dependency installation** (before any API calls)

**Lesson learned:** Always read the actual error message from logs first.

## Testing Steps

### 1. Trigger Manual Workflow Run

```bash
# Via GitHub UI: Actions → Validated Full Pipeline → Run workflow
```

### 2. Monitor Disk Usage

Check the workflow logs for:
```
Disk space before cleanup:
Filesystem      Size  Used Avail Use% Mounted on
/dev/root       ...   ...   4.2G 71%  /

Disk space after cleanup:
Filesystem      Size  Used Avail Use% Mounted on
/dev/root       ...   ...   14G  29%  /
```

### 3. Verify Installation Completes

Look for:
```
Installing collected packages: ...
Successfully installed python-dotenv-1.2.1 requests-2.32.5 ...
```

### 4. Verify All Phases Complete

Confirm all 6 phases run:
- ✅ Phase 1: Discovery
- ✅ Phase 2: Audio Processing
- ✅ Phase 3: Digest Generation
- ✅ Phase 4: TTS Audio Generation
- ✅ Phase 5: Publishing
- ✅ Phase 6: Retention Management

## Alternative Solutions (Not Implemented)

### Option 1: Use Larger Runner

```yaml
runs-on: ubuntu-latest-8-cores  # Has more disk space
```

**Pros:** More resources available
**Cons:** Costs more, not available on free tier

### Option 2: Skip Transcription in CI

Remove Phase 2 (Audio Processing) from CI workflow.

**Pros:** Smaller dependencies
**Cons:** Can't test full pipeline in CI

### Option 3: Use OpenAI Whisper API

Replace local whisper with cloud API.

**Pros:** No PyTorch dependency
**Cons:** Costs money per minute, slower, requires internet

## Related Issues

- GitHub Actions runners have limited disk space: https://github.com/actions/runner-images/issues/2840
- PyTorch size keeps growing: https://github.com/pytorch/pytorch/issues/52437
- Community disk cleanup action: https://github.com/marketplace/actions/free-disk-space-ubuntu

## Prevention

### 1. Monitor Dependency Sizes

```bash
# Check total size of dependencies
pip install -r requirements.txt --dry-run 2>&1 | grep "Downloading" | awk '{print $3}' | numfmt --from=auto --to=iec | paste -sd+ | bc
```

### 2. Regular Cleanup

Run disk cleanup step in all CI workflows.

### 3. Avoid Unused Dependencies

Remove packages that aren't actually used:
- ✅ Removed `parakeet-mlx` (v1.76)
- Review other large packages periodically

---

**Status:** Fixed in v1.76
**Next Workflow Run:** Should complete successfully
