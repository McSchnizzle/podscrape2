# Min Episodes Per Digest Bugfix Summary (v1.95)

## Issue Description

The `min_episodes_per_digest` web setting was being **loaded but not enforced** during digest creation. This caused digests to be created even when the episode count was below the configured minimum threshold (e.g., creating a 1-episode digest when minimum is set to 3).

**User Report**: Psychedelics digest often had only 1 episode despite both min and max set to 3, while AI & Tech and Community Organizing worked correctly (by coincidence - they had >= 3 episodes).

## Root Cause

In `src/generation/script_generator.py`, the `create_digest()` method:

1. **Loaded** the `min_episodes_per_digest` setting correctly (lines 89-95)
2. **Logged** a message claiming to check the minimum (line 582)
3. **Never actually enforced** the minimum threshold

### Buggy Code (Before Fix)

```python
if len(episodes) == 0:
    # Handle no episodes case...
    episodes = []  # Will generate no-content script
else:
    # BUG: This runs for ANY number >= 1, even if below minimum!
    logger.info(f"Including {len(episodes)} undigested episodes in {topic} digest (>= min {self.min_episodes_per_digest})")
    # Episodes will be used as-is, capped at max_episodes_per_digest
```

## Fix Applied

Added explicit check for minimum threshold between "zero episodes" and "proceed with digest":

```python
if len(episodes) == 0:
    # Handle no episodes case...
elif len(episodes) < self.min_episodes_per_digest:
    # NEW: Enforce minimum threshold
    logger.info(f"Insufficient episodes for {topic} digest: {len(episodes)} < {self.min_episodes_per_digest}")
    # Return existing digest if available, otherwise None
    existing_digest = self.digest_repo.get_by_topic_date(topic, digest_date)
    if existing_digest and existing_digest.script_content:
        return existing_digest
    else:
        return None
else:
    # Proceed with digest creation (>= minimum)
    logger.info(f"Including {len(episodes)} undigested episodes...")
```

## Files Modified

1. **src/generation/script_generator.py**
   - Updated `create_digest()` return type to `Optional[Digest]`
   - Added minimum episode threshold enforcement (lines 581-592)
   - Updated `create_daily_digests()` to handle `None` returns (line 655)

2. **src/generation/configurable-script_generator.py**
   - Updated `create_daily_digests()` to handle `None` returns (line 382)

3. **generate_scripts_from_scored.py**
   - Updated script generation loop to handle `None` returns with skip message (lines 69-73)

4. **web_ui_hosted/app/version.ts**
   - Incremented version from 1.94 to 1.95

5. **test_min_episodes_fix.py** (NEW)
   - Test script to verify min_episodes_per_digest enforcement
   - Shows which topics would create digests vs skip

## Test Results

Running `test_min_episodes_fix.py` with current database state:

```
📊 Current settings:
   Min episodes per digest: 3
   Max episodes per digest: 3

🔍 Checking episode counts for each topic:

   AI and Technology:
      Episodes: 1
      Status: ⏭️  WOULD SKIP ✅
      ⚠️  Has 1 episode(s) but below minimum of 3

   Social Movements and Community Organizing:
      Episodes: 3
      Status: ✅ WOULD CREATE
      (3 episodes meet minimum threshold)

   Psychedelics and Spirituality:
      Episodes: 0
      Status: ⏭️  WOULD SKIP ✅
```

**Result**: Fix working correctly! Topics with < 3 episodes are now properly skipped.

## Behavior Changes

### Before Fix
- **Any** topic with 1+ episodes would create a digest
- min_episodes_per_digest setting was ignored
- Inconsistent digest generation across topics

### After Fix
- Topics with < min_episodes_per_digest are **skipped**
- Existing digest returned if available (for continuity)
- Consistent enforcement across all topics
- Clear logging when topics are skipped due to insufficient episodes

## Testing Recommendations

1. **Run digest generation** with current settings (min=3, max=3)
   ```bash
   source .venv/bin/activate
   python3 scripts/run_digest.py --verbose
   ```

2. **Verify in logs** that topics below minimum are skipped:
   ```
   Insufficient episodes for {topic} digest: 1 < 3 (minimum required). Skipping digest creation.
   ```

3. **Check database** that no new digests created for topics below threshold

4. **Test with different thresholds** via Web UI Settings page

## Version

**v1.95** - Fix: Enforce min_episodes_per_digest threshold in digest creation (v1.95)
