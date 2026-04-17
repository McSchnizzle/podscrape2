# Audio Pipeline Incident Log

Running log of audio-generation incidents, diagnoses, and the instrumentation
we added in response. Keep terse — one entry per incident.

## 2026-04-17 — Ep 611 duplicate-outro

**Symptom**: The generated MP3 for ep 611 had the closing repeated twice at the
end, despite the source script containing only one closing.

**Artifacts checked**:
- `digests.script_content` for id=611 → single clean closing, no duplication
- `src/audio/dialogue_chunker.py` → produced 16 clean chunks, chunk 16 with a
  single outro
- `src/audio/audio_generator._generate_chunked_dialogue_audio` →
  `logs/tts_20260416_220117.log` on et01 shows 16 chunks generated with no
  retries, single concatenation
- `dedup_pass.py` → not involved; `script_content_predupe` was NULL for this
  digest, confirming pre-gen dedup (v3.34+) is the active path

**Root cause**: The script ended with
`SPEAKER_1: That's the digest for April 16th. Back tomorrow.` (59 chars)
followed by `SPEAKER_2: See you then.` (15 chars). ElevenLabs v3
Text-to-Dialogue API occasionally hallucinates a duplicated outro when a final
turn has very little text — there isn't enough anchor content for the model
and it pads by repeating.

**Fix (v3.37)**:
1. `src/audio/audio_generator.guard_final_turn_length()` — new helper that
   detects a final turn shorter than `FINAL_TURN_MIN_CHARS` (40) and appends
   `FINAL_TURN_PADDING` (" Take care, and catch you tomorrow.").
2. Called once at the top of `_generate_chunked_dialogue_audio`, before the
   chunker sees the script.
3. Chunk manifest writing — new JSON file written next to the final MP3 as
   `<filename>.chunks.json` containing per-chunk text, char_count, turn_count,
   speakers, and timing. Makes future incidents diagnosable without log
   archaeology or temp-dir forensics.

**Verification plan**: Next dialogue digest should show the manifest file on
disk; if any digest has a sub-40-char final turn, the log line
"Padding to prevent ElevenLabs v3 duplicate-outro hallucination" appears and
the pad is applied before chunking.

**Not addressed** (intentionally): we are not attempting to detect duplicate
audio segments post-generation. That would require decoding every digest,
which adds CPU cost for a probabilistic issue that the pre-TTS guard should
largely eliminate. If duplicate outros recur despite the guard, revisit.
