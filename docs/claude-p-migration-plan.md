# Migrating Podcast Pipeline to claude -p (Eliminating API Keys)

## Background

Research conducted 2026-02-25 in the meeting-buddy project discovered that `claude -p` (Claude Code's programmatic mode) can replace direct Anthropic API SDK calls for batch/non-realtime workloads. This eliminates per-token API billing for those calls, shifting cost to the existing Claude Code subscription.

**Key finding:** `claude -p` is already installed and authenticated on et01 (`/home/pbrown/.local/bin/claude`, v2.1.56). No setup needed.

**Test results (meeting-buddy action items extraction):**
- Direct API (tool_use): 10 items, 12s, 18k input tokens
- claude -p: 7 items, 28s, $0 API cost
- Quality was solid on both; claude -p was slightly less thorough but found items the API missed too

## Current Anthropic API Usage in This Project

| File | What It Does | Migrate? |
|------|-------------|----------|
| `src/generation/script_generator.py` | Generates podcast scripts (streaming) | YES - high token usage, biggest cost saver |
| `scripts/evaluate_digests.py` | Evaluates digest quality with rubric | YES - batch, JSON output |
| `scripts/smoke_test_deploy.py` | Pre-deploy smoke tests (streaming + large max_tokens) | YES - test script, not production |

### Implementation Pattern

Replace `client.messages.create()` / `client.messages.stream()` calls with:

```python
import subprocess
import json
import os

def call_claude_p(system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
    """Call Claude via claude -p instead of direct API."""
    full_prompt = f"{system_prompt}\n\n{user_prompt}"

    env = os.environ.copy()
    env.pop("CLAUDECODE", None)  # Safety: allow if called from Claude Code context

    result = subprocess.run(
        [os.path.expanduser("~/.local/bin/claude"), "-p", full_prompt],
        capture_output=True,
        text=True,
        timeout=300,  # 5 min for long scripts
        env=env,
    )

    if result.returncode != 0:
        raise RuntimeError(f"claude -p failed (exit {result.returncode}): {result.stderr[:500]}")

    return result.stdout.strip()
```

For the script generator specifically, the `_call_llm` method (line 212) would gain a third provider branch:

```python
def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
    if self._is_anthropic_model():
        # Use claude -p instead of direct API
        return call_claude_p(system_prompt, user_prompt)
    else:
        # OpenAI path unchanged
        ...
```

### For JSON output (evaluate_digests.py)

Use `--output-format json` flag:

```python
result = subprocess.run(
    ["claude", "-p", prompt, "--output-format", "json"],
    capture_output=True, text=True, timeout=120,
)
outer = json.loads(result.stdout)
text = outer.get("result", result.stdout)
# Parse JSON from the text response
```

**Caveat:** claude -p doesn't support `tool_use` with forced `tool_choice`, so structured JSON output relies on prompt instructions rather than schema enforcement. For `evaluate_digests.py` this is fine since it already uses prompt-based JSON ("Return ONLY the JSON, no other text").

## Bigger Opportunity: Consolidate ALL LLM Calls on Claude

Currently the podcast pipeline uses **both** OpenAI and Anthropic API keys. There are significantly more OpenAI calls than Anthropic ones. Consider migrating everything to Claude via `claude -p`, which would eliminate BOTH API keys entirely:

### Current OpenAI API Usage

| File | What It Does | OpenAI Feature Used | Claude -p Viable? |
|------|-------------|--------------------|--------------------|
| `src/generation/script_generator.py` | Script generation (OpenAI path) | `responses.create` | YES - text generation, batch |
| `src/generation/configurable-script_generator.py` | Configurable script gen | `responses.create` | YES - same pattern |
| `src/scoring/content_scorer.py` | Scores episode content quality | `responses.create` | YES - batch scoring |
| `src/audio/metadata_generator.py` | Generates episode titles, descriptions | `responses.create` | YES - batch metadata |
| `src/topic_tracking/topic_extractor.py` | Extracts topics from transcripts | `chat.completions.create` | YES - batch extraction |
| `src/topic_tracking/digest_arc_reconciler.py` | Reconciles digest arcs | `chat.completions.create` | YES - batch reconciliation |
| `src/topic_tracking/novelty_detector.py` | Detects novel topics (embeddings) | `embeddings.create` | NO - claude -p can't do embeddings |
| `src/topic_tracking/semantic_matcher.py` | Semantic similarity (embeddings) | `embeddings.create` | NO - claude -p can't do embeddings |
| `src/pipeline/stt/providers.py` | Whisper transcription | `audio.transcriptions` | NO - claude -p can't do audio |

### Migration Summary

**Can migrate to claude -p (eliminates both API keys for these):**
- Episode titles and metadata generation
- Content scoring
- Topic extraction
- Digest arc reconciliation
- Script generation (both providers)
- Digest evaluation

**Must keep an API key for:**
- Embeddings (novelty_detector, semantic_matcher) - need `text-embedding-3-small`. Could switch to a local embedding model or Anthropic's Voyage embeddings to fully eliminate OpenAI.
- Whisper transcription - needs OpenAI Whisper API. Could switch to local Whisper or Deepgram.

### Recommended Approach

1. **Phase 1:** Migrate the 3 existing Anthropic calls to `claude -p` (quick win, already validated)
2. **Phase 2:** Migrate the 6 OpenAI text-generation calls to `claude -p` (episode titles, scoring, topic extraction, arc reconciliation, metadata)
3. **Phase 3:** Evaluate whether to replace OpenAI embeddings with Voyage or local embeddings, and Whisper with Deepgram or local Whisper

After phases 1-2, the only remaining API key dependency would be OpenAI for embeddings and transcription.

## Constraints and Caveats

- **claude -p adds ~15-20s overhead** per call (process spawn + init). Fine for batch, not for real-time.
- **No streaming support** - claude -p returns complete response. The script generator currently uses streaming to avoid SDK timeout issues; with claude -p the timeout is controlled via subprocess timeout instead.
- **No tool_use/tool_choice** - structured output must be prompt-enforced. Works well in practice but less guaranteed than schema-enforced JSON.
- **No embeddings or audio** - claude -p is text-in/text-out only.
- **et01 only** - claude CLI must be installed and authenticated. Already done on et01.

## Reference

- Full audit spreadsheet: `/Users/paulbrown/Desktop/coding-projects/anthropic-api-audit.xlsx`
- meeting-buddy audit doc: `/Users/paulbrown/Desktop/coding-projects/meeting-buddy/docs/api-key-vs-claude-p-audit.md`
- Test results from et01: claude -p extracted 7 action items in 28s from a 1101-line transcript (vs 10 items in 12s via direct API)
