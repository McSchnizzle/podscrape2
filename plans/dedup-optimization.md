# Plan: Dedup Optimization (Rec 1 + Rec 4)

## Why

The podcast pipeline timed out on Apr 23 because the digest phase took 45 min (normally 26 min). The expansion loop -- triggered when dedup strips too much content and the script is too short -- added 18 min by regenerating from scratch with an additional un-deduped episode. The structural variety pass also wastes 6 min on timeouts that produce nothing.

## What

### Rec 1: Pre-dedup more episodes upfront

Dedup 7 episodes (or up to MAX_TRANSCRIPTS) at the start instead of only 4 (`max_episodes_per_digest`). This decouples the dedup batch size from the initial generation batch size. When the expansion loop fires, the extra episodes are already deduped and ready -- no need to regenerate from scratch with raw transcripts.

Changes:
- In `script_generator.create_digest()`, fetch and dedup up to `MAX_TRANSCRIPTS` (9) episodes instead of just the initial `max_episodes_per_digest` (4)
- Store deduped transcripts in a lookup dict keyed by episode ID
- The expansion loop uses deduped versions from the dict instead of raw transcripts

### Rec 4: Skip structural variety pass on non-final expansion iterations

The variety pass times out at 360s on ~50% of runs. When it fails, the original script is kept, meaning 6 wasted minutes. On expansion iterations where the script will be regenerated anyway, skip it entirely. Only run on the final draft.

Changes:
- Add `skip_variety_pass` parameter to `_run_structural_variety_pass()` calls
- In the expansion loop in `create_digest()`, skip variety for intermediate iterations
- Keep variety pass for the final iteration only

## Files to Modify

1. `/srv/projects/podcast/src/generation/script_generator.py`
   - `create_digest()`: Fetch and dedup more episodes upfront, store in lookup
   - `create_digest()` expansion loop: Use pre-deduped transcripts, skip variety on intermediate passes
   - `generate_script()`: Add `skip_variety_pass` parameter

2. `/srv/projects/podcast/src/generation/transcript_dedup.py`
   - No changes expected -- `dedup_episode_batch()` already handles arbitrary batch sizes

## Files NOT Modified

- `run_full_pipeline_orchestrator.py` -- no orchestrator changes
- `scripts/run_digest.py` -- no runner changes
- Database schema -- no migrations needed

## Tests

1. Verify dedup batch processes more than 4 episodes when available
2. Verify expansion loop uses pre-deduped transcripts (not raw)
3. Verify variety pass is skipped on intermediate expansion iterations
4. Verify variety pass still runs on final script
5. Verify no regressions in existing test suite (44 passing baseline)

## Risks & Rollback

- **Risk**: More claude -p calls upfront (3 extra x ~90s). Mitigated: still far less than the 15-20 min expansion regen they prevent.
- **Risk**: Deduping episodes that never get used. Mitigated: claude -p via Max subscription has no API cost.
- **Rollback**: Single commit, single `git revert`.

## Dependencies

None. These are self-contained changes within the digest phase.
