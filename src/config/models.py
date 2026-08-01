"""Single source of truth for which model does which job.

WHY THIS EXISTS. A model-name survey on 2026-07-31 found 52 real
model-selection sites across the project, in five different shapes:

    an allow-list in web_config.py                     20 literals
    a HAND-COPIED mirror of it in TypeScript           20 literals
    three hardcoded <option> dropdowns in the UI        7 literals
    ~16 scattered default / fallback literals
    11 subprocess sites hardcoding `--model sonnet`

Every model release meant editing all of them, and they had already drifted:
the TS mirror's own comment pointed at "web_config.py lines 109-132" while
AI_MODELS had moved to 160-189.

THE FIX IS TO NAME THE JOB, NOT THE MODEL. Call sites ask for the model that
does scoring; they do not name a model. A release then edits MODEL_ROLES here
and nothing else, because the allow-list, the JSON schema the web UI consumes,
and every dropdown all derive from CATALOG below.

WHAT THIS DOES NOT CHANGE. web_settings still wins at runtime -- these are the
values used when the database has no override, which is what the scattered
literals were. Changing a model in the UI still works exactly as before.
"""
from typing import Dict, Optional

# --------------------------------------------------------------------------
# 1. The catalog: every model this project knows how to talk to.
#    Adding a model = one entry here. Limits feed validation and the UI.
# --------------------------------------------------------------------------
CATALOG: Dict[str, Dict[str, Dict]] = {
    "openai": {
        "gpt-5.6-sol": {"max_output": 128000, "max_input": 400000, "display_name": "GPT-5.6 Sol (flagship)"},
        "gpt-5.6-terra": {"max_output": 128000, "max_input": 400000, "display_name": "GPT-5.6 Terra (balanced)"},
        "gpt-5.6-luna": {"max_output": 128000, "max_input": 400000, "display_name": "GPT-5.6 Luna (fast, low cost)"},
        "gpt-5.2": {"min_effort": "medium", "max_output": 128000, "max_input": 400000, "display_name": "GPT-5.2 Thinking"},
        "gpt-5.2-chat-latest": {"min_effort": "medium", "max_output": 128000, "max_input": 400000, "display_name": "GPT-5.2 Instant"},
        "gpt-5.2-pro": {"min_effort": "medium", "max_output": 128000, "max_input": 400000, "display_name": "GPT-5.2 Pro"},
        "gpt-5.1": {"max_output": 128000, "max_input": 400000, "display_name": "GPT-5.1"},
        "gpt-5": {"max_output": 128000, "max_input": 272000, "display_name": "GPT-5"},
        "gpt-5-mini": {"max_output": 128000, "max_input": 400000, "display_name": "GPT-5 Mini"},
        "gpt-5-nano": {"max_output": 64000, "max_input": 128000, "display_name": "GPT-5 Nano"},
    },
    "anthropic": {
        "claude-opus-5": {"max_output": 128000, "max_input": 1000000, "display_name": "Claude Opus 5"},
        "claude-sonnet-5": {"max_output": 128000, "max_input": 1000000, "display_name": "Claude Sonnet 5"},
        "claude-opus-4-6": {"max_output": 128000, "max_input": 1000000, "display_name": "Claude Opus 4.6 (1M)"},
        "claude-sonnet-4-6": {"max_output": 64000, "max_input": 1000000, "display_name": "Claude Sonnet 4.6 (1M)"},
        "claude-haiku-4-5-20251001": {"max_output": 64000, "max_input": 200000, "display_name": "Claude Haiku 4.5"},
        "claude-opus-4-5-20251101": {"max_output": 64000, "max_input": 200000, "display_name": "Claude Opus 4.5"},
        "claude-sonnet-4-5-20250929": {"max_output": 64000, "max_input": 200000, "display_name": "Claude Sonnet 4.5"},
    },
    "elevenlabs": {
        "eleven_v3": {"max_characters": 5000, "display_name": "v3 (5k chars, highest quality)"},
        "eleven_turbo_v2_5": {"max_characters": 40000, "display_name": "Turbo v2.5 (40k chars)"},
        "eleven_turbo_v2": {"max_characters": 30000, "display_name": "Turbo v2 (30k chars)"},
        "eleven_flash_v2_5": {"max_characters": 40000, "display_name": "Flash v2.5 (40k chars, low latency)"},
        "eleven_flash_v2": {"max_characters": 30000, "display_name": "Flash v2 (30k chars, low latency)"},
        "eleven_multilingual_v2": {"max_characters": 10000, "display_name": "Multilingual v2 (10k chars)"},
        "eleven_multilingual_v1": {"max_characters": 10000, "display_name": "Multilingual v1 (10k chars)"},
    },
    "whisper": {
        "whisper-1": {"max_file_size_mb": 25, "display_name": "Whisper-1 (25MB limit)"},
        "local-whisper": {"max_file_size_mb": 0, "display_name": "Local Whisper (no API limit)"},
    },
    "embedding": {
        "text-embedding-3-small": {"dimensions": 1536, "display_name": "text-embedding-3-small"},
        "text-embedding-3-large": {"dimensions": 3072, "display_name": "text-embedding-3-large"},
    },
}


# --------------------------------------------------------------------------
# 2. The roles: which model does which JOB.
#    THIS IS THE BLOCK A MODEL RELEASE EDITS. Nothing else should need to change.
# --------------------------------------------------------------------------
MODEL_ROLES: Dict[str, str] = {
    # High-volume classification. Cheapest tier that can do the job.
    "scoring": "gpt-5-mini",
    # Quality-critical long-form generation.
    "generation": "gpt-5",
    # Story-arc / entity extraction from transcripts.
    "extraction": "gpt-5-mini",
    # Episode titles and descriptions.
    "metadata": "gpt-5-mini",
    # Semantic similarity for arc dedup and novelty.
    "embedding": "text-embedding-3-small",
    # Speech to text.
    "stt": "whisper-1",
    # Text to speech.
    "tts": "eleven_turbo_v2_5",
    # Per-topic dialogue TTS default.
    "dialogue_tts": "eleven_turbo_v2_5",
    # The alias passed to `claude -p --model`. NOT a full model id: the CLI
    # takes aliases, and this path deliberately runs on the Max subscription
    # (ANTHROPIC_API_KEY is popped before the subprocess), not API billing.
    "claude_cli": "sonnet",
}


# --------------------------------------------------------------------------
# 3. Reasoning effort: a JOB preference, raised to a MODEL floor.
#
# Replaces three `model.startswith("gpt-5.2")` branches. Those encoded a real
# constraint (GPT-5.2 rejects "minimal") but expressed it as a name prefix,
# which fails in the dangerous direction: a newer model whose name does not
# match drops silently to the cheaper setting. Declaring the floor on the model
# entry means a new catalog line carries its own constraint.
# --------------------------------------------------------------------------
# What each JOB would like to spend, if the model allows it.
#
# All "minimal" today, which is EXACTLY the behaviour of the three prefix gates
# this replaced: they returned "medium" only for gpt-5.2* (a model constraint)
# and "minimal" for everything else. Raising a job here is a deliberate,
# separately-reviewable decision -- an earlier cut of this refactor set
# research/generation to "medium" and a pre-existing test caught it as the
# silent behaviour change it was.
REASONING_EFFORT: Dict[str, str] = {
    "scoring": "minimal",
    "metadata": "minimal",
    "extraction": "minimal",
    "generation": "minimal",
    "research": "minimal",
}

DEFAULT_REASONING_EFFORT = "minimal"

# Ordered cheapest-first, so a model FLOOR can be applied against a job
# preference by taking whichever is higher.
_EFFORT_ORDER = ["minimal", "low", "medium", "high"]


def role(name: str) -> str:
    """Model id for a job. Raises on an unknown role -- a typo must not
    silently resolve to some default model."""
    try:
        return MODEL_ROLES[name]
    except KeyError:
        raise KeyError(
            f"unknown model role {name!r}; known roles: {sorted(MODEL_ROLES)}"
        ) from None


def reasoning_effort(role_name: str, model_id: Optional[str] = None) -> str:
    """Effort to request: the job's preference, raised to the model's floor.

    This replaces three copies of `if model.startswith("gpt-5.2"): return
    "medium"`. That test encoded a real constraint -- GPT-5.2 models reject
    "minimal" -- but as a NAME PREFIX, which fails open in the wrong direction:
    any newer model whose name does not start with "gpt-5.2" silently drops to
    "minimal", so a model upgrade looks successful while quietly spending less
    thought. Declaring the floor on the model in CATALOG means a new entry
    carries its own constraint and no call site has to know about versions.
    """
    want = REASONING_EFFORT.get(role_name, DEFAULT_REASONING_EFFORT)
    if not model_id:
        return want
    floor = None
    for models in CATALOG.values():
        if model_id in models:
            floor = models[model_id].get("min_effort")
            break
    if not floor:
        return want
    return max(want, floor, key=lambda e: _EFFORT_ORDER.index(e)
               if e in _EFFORT_ORDER else 0)


def provider_for(model_id: str) -> Optional[str]:
    """Which provider serves this model id, by catalog lookup rather than by
    string prefix. Returns None if the model is not in the catalog."""
    for provider, models in CATALOG.items():
        if model_id in models:
            return provider
    # Fall back to a prefix test only for ids the catalog has not seen yet, so
    # an unlisted claude-* still routes to the Anthropic path.
    if model_id.startswith("claude-"):
        return "anthropic"
    if model_id.startswith(("gpt-", "o1", "o3", "o4")):
        return "openai"
    return None


def model_limit(model_id: str, key: str = "max_output") -> int:
    """Look up a declared limit for a model. 0 when unknown, matching the
    previous get_model_limit() contract."""
    for models in CATALOG.values():
        if model_id in models:
            return int(models[model_id].get(key, 0) or 0)
    return 0


def all_model_ids() -> Dict[str, list]:
    """Provider -> [model id], for validation and UI rendering."""
    return {provider: sorted(models) for provider, models in CATALOG.items()}
