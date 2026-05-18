# Transcript chunk-dedup for >30,000 char episodes

**Linked kanban:** #430

## Why

Currently `dedup_transcript()` sends the full transcript to `claude -p`
in a single call. Long episodes (e.g. the 60,735-char 5/15 episode)
push close to or past practical context/output budgets, leading to
either truncated output, timeouts, or degraded dedup quality. The fix
is to split long transcripts into <=30,000-char chunks at sentence
boundaries, dedup each chunk independently against the same
`prior_content`, then concatenate the cleaned outputs back together in
order. No truncation, ever -- every character of the source transcript
gets a chance to be evaluated.

## What

1. New pure function in `src/generation/transcript_dedup.py`:
   `split_transcript_into_chunks(text: str, max_chunk_chars: int = 30000) -> List[str]`.
   - Returns `[text]` when `len(text) <= max_chunk_chars`.
   - Otherwise splits at sentence boundaries, no mid-sentence cuts.
   - Lossless: `"".join(chunks) == text`.
2. Modify `dedup_transcript()` to use the chunker when transcript
   exceeds 30,000 chars. Each chunk is dedup'd independently via
   `_call_claude_p` with the same `prior_content` + `episode_title` +
   `evergreen_topics`. Cleaned chunks are concatenated in order
   (separated by `\n\n` for readability).
3. If ANY chunk's `_call_claude_p` raises (timeout, runtime error,
   etc.), the whole `dedup_transcript()` returns the original transcript
   with `skipped=True` and `skip_reason="chunk N failed: <reason>"`.
   This is "fail loudly" in the sense that the failure is recorded and
   surfaced -- we do NOT silently keep partial dedup output. (The
   alternative -- raising -- would crash the whole batch; the existing
   single-call code path already swallows per-episode failures into
   `skipped=True`, so this matches existing pipeline semantics.)
4. Regression test in `tests/test_transcript_chunk_dedup.py` exercising
   the pure chunker against a 60,735-char synthetic fixture.

## Files to Create

- `tests/test_transcript_chunk_dedup.py` -- unit tests for the chunker
  and the wiring (mocked `_call_claude_p`).
- `tests/fixtures/transcript_60735.txt` -- synthetic 60,735-char
  transcript fixture (sentence-rich, representative of a real episode).

## Files to Modify

- `src/generation/transcript_dedup.py`:
  - Add `split_transcript_into_chunks()` pure helper near the top of
    the module (after imports, before `_DEDUP_SYSTEM_PROMPT`).
  - Modify `dedup_transcript()` so the existing single-call path
    runs unchanged for transcripts <=30k chars, and the new
    chunk-and-reassemble path kicks in for >30k.

## Tests to Write

1. `test_split_no_split_short_text` -- 5,000 char string returns a
   1-item list equal to the input.
2. `test_split_exact_30k_no_split` -- 30,000 char string returns
   `[input]` (boundary: `<=` means no split at exactly 30k).
3. `test_split_30001_chars_splits` -- 30,001 chars returns >=2 chunks.
4. `test_split_lossless` -- For a 60,735-char fixture,
   `"".join(chunks) == fixture`.
5. `test_split_no_chunk_over_max` -- Every chunk except possibly the
   last is `<= max_chunk_chars`. (We allow the last chunk to be small;
   we also allow a chunk to slightly exceed the max if no sentence
   boundary exists in the window -- documented behavior.)
6. `test_split_breaks_at_sentence_boundary` -- Constructed input with
   known sentence positions; assert chunks end with `.` or `!` or `?`
   followed by whitespace (or end-of-string).
7. `test_split_handles_no_sentence_boundary` -- A 60,000-char string
   with NO `.`/`!`/`?` falls back to hard-splitting at `max_chunk_chars`
   so we don't return one giant chunk (still lossless).
8. `test_dedup_transcript_chunks_when_over_30k` -- Mock
   `_call_claude_p` to return `f"[CLEAN {i}]"` for each call; pass a
   60,735-char transcript; assert `_call_claude_p` was called >=2
   times, the result contains both `[CLEAN 1]` and `[CLEAN 2]` in
   order, and `skipped=False`.
9. `test_dedup_transcript_chunk_failure_marks_skipped` -- Mock
   `_call_claude_p` to raise on the 2nd chunk; assert the result is
   `skipped=True` with `skip_reason` containing `"chunk"`.
10. `test_dedup_transcript_single_call_under_30k` -- Mock
    `_call_claude_p` to count invocations; 25,000-char transcript
    should result in exactly 1 call (no regression of existing path).
11. `test_60735_fixture_roundtrip` -- AC4: load the 60,735-char
    fixture, run it through the chunker, assert lossless roundtrip
    and chunk count (deterministic for the fixture).

## Risks & Rollback

- **Risk:** chunk boundaries land mid-paragraph; claude -p loses
  cross-chunk context for paraphrased content. Mitigation: 30k chars
  is ~5,000 words / ~30 minutes of dialogue -- substantial standalone
  context per chunk. Each chunk still sees the full `prior_content` so
  the "already covered" signal isn't degraded.
- **Risk:** more `claude -p` calls per long episode -> more wall-clock
  time. Acceptable: only episodes >30k chars (rare in production)
  take the slow path; MAX_TRANSCRIPTS=9 caps total episodes per run.
- **Rollback:** revert `transcript_dedup.py` to single-call path.
  The chunker is additive; removing the call site in
  `dedup_transcript()` restores prior behavior.

## Dependencies

None. Pure-Python addition; no new packages.

## Build Strategy

**Dependency order:**
1. `tests/fixtures/transcript_60735.txt` (data, no deps) -- BUILD FIRST.
2. `src/generation/transcript_dedup.py` -- add chunker + wire into
   `dedup_transcript()`.
3. `tests/test_transcript_chunk_dedup.py` -- exercises everything.

**Parallel clusters:** none -- single module + single test file.

**Risk areas:**
- `dedup_transcript()` signature unchanged; existing callers
  (`dedup_episode_batch`) unaffected.
- Existing pipeline keeps single-call behavior for transcripts
  <=30k chars -- no behavior change for the common case.

## Codex Review Feedback

n/a -- single-file change in an external (non-harold) repo; this plan
documents the work but does not go through harold's codex-review-plan
gate.
