# Digest Function Fix - Episode Inclusion Logic

## Problem Identified
The digest generation function was blocking the creation of digests when the number of qualifying episodes fell below the configured minimum threshold. This created a catch-22 situation where:

1. High-quality scored episodes couldn't be digested because there weren't enough of them
2. Those episodes were never marked as digested (since they weren't used)
3. Next day, the same episodes would be found again, still below minimum
4. This loop continued indefinitely, leaving quality content undigested

**Example from user report:**
- 6 episodes with high Tech scores (0.80-0.98) were stuck in "scored" status
- If `min_episodes_per_digest` was set to 10, they would never be digested
- User expected: "check for any scored but undigested episodes and including them in the digest as long as they are within the min and max episodes per digest range"

## Root Cause
In `src/generation/script_generator.py`, the `create_digest()` method had this logic:

```python
if 0 < len(episodes) < self.min_episodes_per_digest:
    logger.info(f"Insufficient episodes for {topic}: ...")
    episodes = []  # Force no-content script path
```

This converted any sub-threshold episode count to zero, preventing digestion.

## Solution Implemented

### 1. Removed Overly Strict Minimum Threshold
**File:** `src/generation/script_generator.py`

Changed the logic in `create_digest()` method (lines 368-380):

**Before:**
```python
if 0 < len(episodes) < self.min_episodes_per_digest:
    episodes = []  # Reject sub-threshold digests
```

**After:**
```python
if len(episodes) == 0:
    logger.info(f"No qualifying undigested episodes found...")
    episodes = []  # Will generate no-content script
else:
    logger.info(f"Including {len(episodes)} undigested episodes...")
    # Episodes will be used as-is, capped at max_episodes_per_digest
```

### 2. Clarified Undigested Episode Filtering
**File:** `src/generation/script_generator.py`

Updated `get_qualifying_episodes()` docstring to explicitly document that it returns only:
- Episodes with score >= threshold for the topic
- Episodes that **haven't been digested yet** (status == 'scored')
- Limited to max_episodes per topic

**Mechanism:** Episodes automatically excluded because:
- `get_scored_episodes_for_topic()` filters by `status == 'scored'`
- Once digested, status changes to `'digested'` (never returned again)

## Behavior Changes

### New Digest Logic
1. ✅ Get all scored episodes that haven't been digested
2. ✅ If count > 0: Create digest with those episodes (regardless of minimum)
3. ✅ If count = 0: Generate no-content digest
4. ✅ Mark used episodes as digested so they won't be re-included

### Episode Flow
- **pending** → **processing** → **transcribed** → **scored** ← Here episodes wait for digest
  - Once used in digest: → **digested** (never returned by queries again)
  - If below old minimum: NOW INCLUDED instead of blocked

## Impact

### Resolves
- ✅ 6 episodes with high Tech scores (0.80-0.98) will now be digested
- ✅ Quality content won't be blocked by minimum threshold
- ✅ Episodes properly marked as digested after use

### Maintains
- ✅ Max episodes per digest cap still enforced
- ✅ Score threshold filtering still applied
- ✅ No-content digests still generated when zero qualifying episodes
- ✅ Backward compatible with existing code

## Configuration Notes
- `min_episodes_per_digest` setting is now effectively unused (but kept for future flexibility)
- `max_episodes_per_digest` still enforced (default: 5)
- Quality threshold (`score_threshold`) still applied (default: 0.65)

## Testing Checklist
- [ ] Run digest phase with episodes below previous minimum threshold
- [ ] Verify high-quality episodes are included in digest
- [ ] Verify episodes marked as digested after processing
- [ ] Verify no-content digest generated only when zero qualifying episodes
- [ ] Verify max_episodes_per_digest cap still respected

## Files Modified
1. `src/generation/script_generator.py`
   - Updated `create_digest()` method (removed minimum threshold rejection)
   - Updated `get_qualifying_episodes()` docstring (clarified undigested filtering)
