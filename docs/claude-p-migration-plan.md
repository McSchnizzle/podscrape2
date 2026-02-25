# Migrating Podcast Pipeline to claude -p (Eliminating API Keys)

## Background

Research conducted 2026-02-25 in the meeting-buddy project discovered that `claude -p` (Claude Code's programmatic mode) can replace direct Anthropic and OpenAI API SDK calls for batch/non-realtime workloads. This eliminates per-token API billing for those calls, shifting cost to the existing Claude Code subscription.

**Key finding:** `claude -p` is already installed and authenticated on et01 (`/home/pbrown/.local/bin/claude`). No setup needed.

---

## Status (as of 2026-02-25)

### Phase 1: Anthropic API calls — COMPLETE ✅

| File | What It Does | Status |
|------|-------------|--------|
| `scripts/evaluate_digests.py` | Evaluates digest quality with rubric | ✅ Migrated v3.09 |
| `scripts/smoke_test_deploy.py` | Pre-deploy smoke tests | ✅ Migrated v3.09 |
| `src/generation/script_generator.py` | Generates dialogue podcast scripts (Anthropic path) | ✅ Migrated v3.09 |

### Phase 2: OpenAI API calls — PARTIAL ✅

| File | What It Does | Status |
|------|-------------|--------|
| `src/audio/metadata_generator.py` | Generates episode titles, descriptions, episode links | ✅ Migrated v3.10 |
| `src/scoring/content_scorer.py` | Scores episode transcript relevance per topic | ✅ Migrated v3.12 |
| `src/generation/script_generator.py` (OpenAI path) | Script generation via OpenAI model config | Not yet |
| `src/generation/configurable_script_generator.py` | Configurable script gen | Not yet |
| `src/topic_tracking/topic_extractor.py` | Extracts story arcs from transcripts | Not yet |
| `src/topic_tracking/digest_arc_reconciler.py` | Reconciles digest arcs | Not yet |

### Phase 3: Cannot migrate (structural limitations)

| File | What It Does | Why Not |
|------|-------------|---------|
| `src/topic_tracking/novelty_detector.py` | Novel topic detection | Embeddings — claude -p is text only |
| `src/topic_tracking/semantic_matcher.py` | Semantic similarity | Embeddings — claude -p is text only |
| `src/pipeline/stt/providers.py` | Whisper transcription | Audio — claude -p is text only |

---

## Skill Files

Each migrated call loads a skill file from `.claude/commands/` for prompt engineering separation. This keeps prompts out of production code and lets you tune them without code changes.

| Skill | File | Used By |
|-------|------|---------|
| Digest generator | `.claude/commands/generate-digest.md` | `script_generator.py` |
| Metadata generator | `.claude/commands/generate-metadata.md` | `metadata_generator.py` |
| Topic scorer | `.claude/commands/score-topic.md` | `content_scorer.py` |

**Skill vs topic DB instructions (important distinction):**
The `generate-digest.md` skill does NOT override database topic instructions. The skill provides structural rules (format, audio tag budget, length, quality standards). The database `instructions_md` field for each topic is injected immediately after as `## Topic-Specific Instructions`. The model sees both — skill sets the frame, DB content fills it.

**Skill files must be on et01.** The deploy script (`scripts/deploy_to_et01.sh`) now deploys `.claude/commands/` to et01 while still excluding `.claude/settings.json`, hooks, agents, memory, etc. (fixed in v3.11).

**Resilient fallbacks:** Each `_load_*_skill()` method embeds a minimal fallback prompt for the case where the skill file is missing. This prevents silent failures.

---

## Canonical Implementation Pattern

**CRITICAL: Use stdin, not args.** Large prompts (transcripts, scripts) exceed OS ARG_MAX limits (~130K chars). Always pass via `input=`:

```python
@staticmethod
def _call_claude_p(prompt: str, timeout: int = 120) -> str:
    """Call claude -p with prompt via stdin."""
    claude_path = os.path.expanduser("~/.local/bin/claude")
    if not os.path.exists(claude_path):
        claude_path = "claude"
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)  # Required: prevents conflict with Claude Code session
    result = subprocess.run(
        [claude_path, "-p", "-"],   # "-" = read prompt from stdin
        input=prompt,               # Pass prompt here, not as arg
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude -p failed (exit {result.returncode}): {result.stderr[:500]}")
    return result.stdout.strip()
```

**JSON parsing:** claude -p wraps JSON output in markdown code fences (`\n\n```json\n...\n```\n`). The `.strip()` call on stdout handles leading newlines, then:

```python
raw = self._call_claude_p(prompt)
if raw.startswith('```json'):
    raw = raw.replace('```json', '').replace('```', '').strip()
elif raw.startswith('```'):
    raw = raw.replace('```', '').strip()
result = json.loads(raw)
```

No `--output-format json` flag needed (and it's not reliable for this use case anyway).

---

## What We Learned

### Performance (measured on et01)
- **Scoring**: ~15–20 seconds per episode — acceptable for nightly batch
- **Metadata generation**: ~50 seconds — acceptable (runs once per digest)
- **Digest generation**: ~15–20 minutes — the nightly run can absorb this
- **subprocess timeout**: Set generously; use 90s for scoring, 120s for metadata, 600–900s for digest

### Quality (vs OpenAI/Anthropic API baselines)
- **Digest generation**: After prompt tuning via skill file, claude -p scored 9.05 vs 6.80 for the Sonnet API baseline on the same transcripts. Tag discipline and analytical depth improved significantly.
- **Topic scoring**: Score deltas vs stored OpenAI scores were ±0.02–0.09. All qualify/exclude threshold decisions (≥0.65) agreed.
- **Metadata generation**: Notably better titles and summaries than the OpenAI path — more specific, uses actual facts from the script rather than generic filler.

### Revert strategy
All migrated calls preserve the old implementation in clearly marked bordered comment blocks:
```
# ┌─────────────────────────────────────────────────────────────────────┐
# │ PREVIOUS IMPLEMENTATION: ...                                        │
# │ To revert: ...                                                      │
# └─────────────────────────────────────────────────────────────────────┘
```

### Cannot call claude -p from within Claude Code
`claude -p` doesn't work from inside a Claude Code session (env conflict). All testing must be done directly on et01 via SSH. The `env.pop("CLAUDECODE", None)` line handles this safely.

### Model selection
`claude -p` uses the CLI's configured default model on et01. You can change it globally with `claude config set model claude-opus-4-6` (or sonnet/haiku). There is no per-call model override. Currently et01 uses Sonnet 4.6.

---

## Remaining Phase 2 Work

### `src/generation/script_generator.py` — OpenAI path
The Anthropic streaming path is already migrated. The OpenAI path (`_generate_dialogue_script` when `_is_anthropic_model()` is False) still uses `openai.responses.create()`. This path is used when the topic's `dialogue_model` setting points to a GPT model. Migrating it means the existing `generate-digest.md` skill covers all topics regardless of model config.

### `src/generation/configurable_script_generator.py`
Similar to script_generator.py — uses OpenAI for narrative-mode script generation. Needs the same `_call_claude_p()` + skill approach.

### `src/topic_tracking/topic_extractor.py`
Uses `chat.completions.create()` for story arc extraction from transcripts. A `extract-story-arcs.md` skill would capture the extraction prompt. Output is more complex (nested JSON with arc objects and events), so prompt clarity matters.

### `src/topic_tracking/digest_arc_reconciler.py`
Uses `chat.completions.create()` for reconciling story arcs across digests. Similar pattern to topic_extractor. A `reconcile-arcs.md` skill would apply.

---

## After Full Phase 2 Completion

The only remaining API key dependency will be:
- **OpenAI** — for embeddings (`text-embedding-3-small`) used by `novelty_detector.py` and `semantic_matcher.py`, and for Whisper transcription
- **ElevenLabs** — TTS (cannot be replaced with claude -p)

To fully eliminate OpenAI, embeddings could be replaced with Voyage AI (Anthropic's embedding service) or a local model. Whisper could be replaced with Deepgram or local Whisper. These are Phase 3.

---

## Reference

- Full audit spreadsheet: `/Users/paulbrown/Desktop/coding-projects/anthropic-api-audit.xlsx`
- meeting-buddy audit doc: `/Users/paulbrown/Desktop/coding-projects/meeting-buddy/docs/api-key-vs-claude-p-audit.md`
- Test scripts: `scripts/test_claude_p_digest.py`, `scripts/test_claude_p_metadata.py`, `scripts/test_claude_p_scoring.py`
