#!/usr/bin/env python3
"""Model selection must stay a one-file change.

A survey on 2026-07-31 found 52 real model-selection sites in five shapes: a
Python allow-list, a HAND-COPIED TypeScript mirror of it, three hardcoded UI
dropdowns, ~16 scattered fallbacks, and 11 subprocess sites hardcoding
`--model sonnet`. They had already drifted -- the TS mirror's comment pointed at
"web_config.py lines 109-132" while AI_MODELS had moved to 160-189.

These tests pin the properties that keep that from happening again.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.config.models import (  # noqa: E402
    CATALOG, MODEL_ROLES, all_model_ids, model_limit, provider_for,
    reasoning_effort, role,
)

GENERATED = REPO / "web_ui_hosted" / "generated" / "settings-schema.json"


def test_every_role_points_at_a_catalogued_model():
    """A role naming a model the catalog does not know is a silent 404 at
    runtime. The claude_cli alias is exempt: `claude -p` takes aliases."""
    for name, model_id in MODEL_ROLES.items():
        if name == "claude_cli":
            continue
        assert provider_for(model_id) is not None, (
            f"role {name!r} -> {model_id!r} is not in CATALOG"
        )


def test_role_rejects_unknown_names():
    """A typo must raise, not resolve to some default model."""
    with pytest.raises(KeyError):
        role("scorring")


def test_ai_models_is_derived_not_a_second_copy():
    """web_config.AI_MODELS must BE the catalog, not a parallel dict."""
    from src.config.web_config import AI_MODELS
    assert set(AI_MODELS) == set(CATALOG)
    for provider in CATALOG:
        assert set(AI_MODELS[provider]) == set(CATALOG[provider])


def test_generated_schema_is_in_sync():
    """The JSON the web UI imports must match the Python. If this fails, run
    scripts/regen-settings-schema.sh."""
    assert GENERATED.exists(), "generated schema missing; run scripts/regen-settings-schema.sh"
    on_disk = json.loads(GENERATED.read_text())
    fresh = json.loads(subprocess.run(
        [sys.executable, str(REPO / "scripts" / "export_settings_schema.py")],
        capture_output=True, text=True, cwd=str(REPO), check=True).stdout)
    assert on_disk == fresh, (
        "web_ui_hosted/generated/settings-schema.json is stale -- "
        "run scripts/regen-settings-schema.sh"
    )


# --- the reasoning-effort trap --------------------------------------------

def test_gpt52_still_gets_medium_effort():
    """GPT-5.2 rejects 'minimal'. Behaviour must be identical to the three
    startswith() branches this replaced."""
    for m in ("gpt-5.2", "gpt-5.2-pro", "gpt-5.2-chat-latest"):
        assert reasoning_effort("scoring", m) == "medium"
        assert reasoning_effort("metadata", m) == "medium"


def test_older_models_still_get_minimal():
    for m in ("gpt-5-mini", "gpt-5", "gpt-5-nano"):
        assert reasoning_effort("scoring", m) == "minimal"


def test_a_new_model_does_not_silently_downgrade(monkeypatch):
    """THE POINT OF THE REFACTOR. Under `model.startswith("gpt-5.2")` a job
    could not express "I want medium" at all -- effort was decided purely by
    whether the model NAME matched, so every newer model fell through to
    'minimal'. Now a job that asks for medium keeps it on a brand-new model.

    Uses monkeypatch rather than a real role because every shipped job is
    deliberately 'minimal' today (behaviour-preserving); this tests the
    mechanism that makes raising one safe later."""
    import src.config.models as M
    monkeypatch.setitem(M.REASONING_EFFORT, "generation", "medium")
    for m in ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"):
        assert M.reasoning_effort("generation", m) == "medium", (
            f"{m} silently downgraded a job that asked for medium"
        )


def test_model_floor_raises_a_cheaper_job_preference():
    """Floor wins when it is higher; preference stands when it is."""
    assert reasoning_effort("scoring", "gpt-5.2") == "medium"      # floor raises
    assert reasoning_effort("scoring", "gpt-5-mini") == "minimal"  # pref stands


# --- no re-inlining -------------------------------------------------------

def test_no_hardcoded_sonnet_argv_remains():
    """Eleven subprocess sites hardcoded the alias. If one comes back, the
    UI's Anthropic picker silently stops mattering again."""
    hits = []
    for f in (REPO / "src").rglob("*.py"):
        if f.name == "models.py":
            continue
        if '"--model", "sonnet"' in f.read_text(encoding="utf-8"):
            hits.append(str(f.relative_to(REPO)))
    assert not hits, f"hardcoded sonnet argv reappeared in {hits}"


def test_catalog_covers_current_frontier():
    ids = all_model_ids()
    for m in ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"):
        assert m in ids["openai"], f"{m} missing from the catalog"
    for m in ("claude-opus-5", "claude-sonnet-5"):
        assert m in ids["anthropic"], f"{m} missing from the catalog"


def test_model_limit_matches_previous_contract():
    """get_model_limit() returned 0 for unknown ids; keep that."""
    assert model_limit("gpt-5") > 0
    assert model_limit("sonnet") == 0
    assert model_limit("nope-not-a-model") == 0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
