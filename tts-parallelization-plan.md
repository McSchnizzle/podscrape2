# TTS Parallelization Implementation Plan

**Created**: 2025-11-20
**Status**: Proposed (Not Implemented)
**Expected Speedup**: 4-6x reduction in TTS phase time

## Executive Summary

Parallelize TTS chunk generation similar to the successful audio transcription parallelization. This will reduce TTS phase time from ~15 minutes to ~3 minutes for typical daily workloads.

## Current State Analysis

### Audio Phase (Parallel - ✅ Working)
- Uses `concurrent.futures.ThreadPoolExecutor` with multiple workers
- Processes multiple audio chunks simultaneously across different episodes
- Successfully reassembles chunks after parallel transcription
- Achieves significant speedup on multi-episode workloads

### TTS Phase (Sequential - Current Bottleneck)
- Currently processes chunks one-by-one within each digest
- Each ElevenLabs API call takes ~30-60 seconds
- Example: Digest with 8 chunks = 8 × 40s = ~320 seconds
- **Bottleneck**: I/O-bound API calls processed serially

## Feasibility Assessment

### ✅ Pros
1. **Massive Speed Gains**: 5x-10x speedup possible with 5-10 concurrent workers
   - 8 chunks @ 40s each: Sequential = 320s, Parallel (5 workers) = ~64s
2. **I/O-Bound Work**: TTS API calls are network-bound (perfect for parallelization)
3. **Proven Pattern**: Audio phase already demonstrates this works
4. **Existing Infrastructure**: Chunking and reassembly logic already handles ordering

### ⚠️ Challenges
1. **Rate Limits**: ElevenLabs API has limits (need to respect them)
2. **Dialogue Mode Complexity**: Dialogue chunks must maintain speaker context
3. **Memory Usage**: Multiple audio chunks held in memory simultaneously
4. **Error Recovery**: Need robust retry logic for individual chunk failures

## Implementation Plan

### Phase 1: Foundation (1-2 hours)
**Goal**: Extract chunk processing into parallelizable function

```python
# src/audio/audio_generator.py

def _process_single_tts_chunk(
    chunk_index: int,
    chunk_text: str,
    voice_config: dict,
    model: str,
    api_key: str,
    is_dialogue: bool
) -> tuple[int, bytes]:
    """
    Process a single TTS chunk (dialogue or narrative).

    Returns:
        (chunk_index, audio_bytes) tuple for ordered reassembly
    """
    # Isolated function - no shared state
    # Makes retry logic simple
    # Can be called from thread pool
```

**Files to modify:**
- `src/audio/audio_generator.py`

**Changes:**
1. Extract current chunk processing logic into standalone function
2. Remove class dependencies (pass all config as parameters)
3. Add proper error handling and return values
4. Test with single chunk to verify isolation

---

### Phase 2: Worker Pool (2-3 hours)
**Goal**: Add parallel execution with configurable workers

```python
# src/audio/audio_generator.py

class ParallelTTSGenerator:
    def __init__(self, max_workers: int = 5, rate_limit_per_second: int = 10):
        self.max_workers = max_workers
        self.rate_limiter = RateLimiter(rate_limit_per_second)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def generate_chunked_audio_parallel(
        self,
        chunks: List[str],
        voice_config: dict,
        model: str
    ) -> bytes:
        """
        Generate audio for multiple chunks in parallel.

        Process:
        1. Submit all chunks to thread pool
        2. Apply rate limiting
        3. Collect results (handles failures)
        4. Sort by index and concatenate
        """
```

**Key components:**
- `concurrent.futures.ThreadPoolExecutor` for worker pool
- `threading.Semaphore` for rate limiting
- `futures.as_completed()` for result collection
- Exponential backoff for retries

---

### Phase 3: Rate Limiting (1 hour)
**Goal**: Respect ElevenLabs API limits without throttling unnecessarily

```python
# src/utils/rate_limiter.py

class AdaptiveRateLimiter:
    """
    Rate limiter that:
    - Tracks API response headers (X-RateLimit-Remaining, etc.)
    - Backs off when approaching limits
    - Recovers automatically when limits reset
    """

    def acquire(self, chunk_index: int):
        """Block until this chunk can be sent"""

    def handle_rate_limit_response(self, headers: dict):
        """Adjust limits based on API response"""
```

**Configuration:**
- Add to `web_settings` table: `tts_max_concurrent_requests` (default: 5)
- Add to `web_settings` table: `tts_rate_limit_per_second` (default: 10)

---

### Phase 4: Error Handling (1-2 hours)
**Goal**: Robust failure recovery without breaking the entire digest

```python
# Retry logic for individual chunks
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=retry_if_exception_type(RateLimitError)
)
def _call_tts_api_with_retry(chunk_data):
    """Retry individual chunks on transient failures"""
```

**Fallback strategy:**
1. Try parallel with max_workers
2. If >30% chunks fail → reduce workers by half, retry
3. If still failing → fall back to sequential
4. Log performance metrics for tuning

---

### Phase 5: Integration & Testing (2-3 hours)
**Goal**: Integrate with existing codebase and test thoroughly

**Test scenarios:**
1. **Single digest, 8 chunks** (baseline)
2. **Multiple digests** (ensure no cross-contamination)
3. **Rate limit simulation** (verify backoff works)
4. **Partial failure** (some chunks fail, others succeed)
5. **Dialogue vs narrative** (both modes work)

**Files to modify:**
- `src/audio/audio_generator.py` - Add parallel generation
- `src/audio/dialogue_chunker.py` - No changes needed (chunking logic stays same)
- `src/config/web_config.py` - Add parallel config settings
- `scripts/run_tts.py` - Enable parallel mode flag

---

### Phase 6: Monitoring & Tuning (ongoing)
**Goal**: Measure and optimize performance

**Metrics to track:**
- Average chunk generation time (parallel vs sequential)
- Rate limit hits per digest
- Memory usage with concurrent chunks
- Error rate by chunk size/type

**Configuration tuning:**
```python
# Optimal settings will vary by:
# - ElevenLabs subscription tier
# - Network latency
# - Typical chunk count per digest

# Conservative start:
max_workers = 3
rate_limit_per_second = 5

# Aggressive (with high-tier subscription):
max_workers = 10
rate_limit_per_second = 15
```

---

## Implementation Priority

### High Value, Low Risk
1. ✅ **Narrative mode first** - Simpler than dialogue (no speaker coordination)
2. ✅ **Configurable flag** - Start with `--parallel` flag, default to sequential
3. ✅ **Gradual rollout** - Test locally, then GitHub Actions

### Medium Value, Medium Risk
4. **Dialogue mode** - More complex but worthwhile
5. **Auto-tuning** - Adjust workers based on API responses

### Lower Priority
6. **Cross-digest parallelization** - Process multiple digests simultaneously (bigger change)

---

## Estimated Speedup

**Scenario: 3 digests, 8 chunks each @ 40s per chunk**

| Approach | Time | Speedup |
|----------|------|---------|
| Current (Sequential) | 960s (~16 min) | 1x |
| **Parallel (5 workers)** | **192s (~3.2 min)** | **5x** |
| Parallel (10 workers) | 96s (~1.6 min) | 10x |

**Real-world**: Expect 4-6x speedup with 5 workers accounting for overhead.

---

## Risks & Mitigation

| Risk | Mitigation |
|------|------------|
| Hit rate limits | Adaptive rate limiter, start conservative |
| Higher API costs | No increase (same total requests) |
| Chunk ordering bugs | Comprehensive tests, maintain index tracking |
| Memory pressure | Limit concurrent chunks, stream to disk |
| Dialogue context loss | Keep dialogue chunking logic unchanged |

---

## Recommendation

**✅ Do it!** This is a high-value optimization with proven patterns from the audio phase.

### Suggested Approach
1. Start with **narrative mode only** (AI & Technology digests)
2. Use **3-5 workers** initially (conservative)
3. Add **--parallel flag** to `run_tts.py` for gradual rollout
4. Monitor for 1 week, tune settings
5. Enable for **dialogue mode** once stable
6. Make parallel the default after validation

**Expected outcome**: Reduce TTS phase time from ~15 minutes to ~3 minutes for typical daily workload.

---

## Code Structure Overview

```
src/audio/
├── audio_generator.py          # Main TTS generation (MODIFY)
│   ├── _process_single_tts_chunk()  # NEW: Isolated chunk processor
│   ├── ParallelTTSGenerator()        # NEW: Parallel coordinator
│   └── generate_chunked_audio_parallel()  # NEW: Parallel entry point
├── dialogue_chunker.py         # No changes needed
└── metadata_generator.py       # No changes needed

src/utils/
└── rate_limiter.py             # NEW: Adaptive rate limiting

src/config/
└── web_config.py               # ADD: parallel TTS settings

scripts/
└── run_tts.py                  # ADD: --parallel flag
```

---

## Testing Checklist

Before deploying to production:

- [ ] Single narrative digest (8 chunks) completes successfully
- [ ] Single dialogue digest (12 chunks) completes successfully
- [ ] Multiple digests in one run don't interfere
- [ ] Rate limit simulation triggers backoff correctly
- [ ] Chunk ordering is preserved (verify with known test audio)
- [ ] Memory usage stays under 2GB during generation
- [ ] Error in one chunk doesn't crash entire digest
- [ ] Fallback to sequential works when parallel fails
- [ ] Configuration settings load from database correctly
- [ ] Performance metrics logged properly

---

## Performance Baseline (Before Implementation)

**Test Date**: 2025-11-20

| Digest | Episodes | Chunks | Time (Sequential) | Notes |
|--------|----------|--------|-------------------|-------|
| AI & Tech (Nov 18) | 3 | 8 | ~5 min 20s | Narrative mode |
| AI & Tech (Nov 19) | 3 | 9 | ~6 min | Narrative mode |
| AI & Tech (Nov 20) | 3 | 8 | ~5 min 20s | Narrative mode |
| Social Movements (Nov 18) | 3 | 13 | ~13 min | Dialogue mode |

**Total**: ~30 minutes for 4 digests

**Target (Post-Implementation)**: ~6 minutes for 4 digests (5x speedup)

---

## Next Steps

1. Review and approve plan
2. Create feature branch: `feature/tts-parallelization`
3. Implement Phase 1 (foundation)
4. Test with single digest locally
5. Iterate through phases 2-6
6. Deploy with feature flag
7. Monitor and tune
