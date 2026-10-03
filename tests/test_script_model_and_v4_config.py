"""Production script-model and TTS-model wiring (2026-10-03).

The configured Claude generation model reaches the CLI verbatim with medium
effort for the draft; polish passes keep the utility alias and low effort;
eleven_v4 dialogue requests stay within the documented 2,000 characters.
"""
from __future__ import annotations

import subprocess

import pytest

import src.generation.script_generator as sg
from src.audio.audio_generator import AudioGenerator
from src.config.models import CATALOG, provider_for
from src.generation.script_generator import ScriptGenerator


@pytest.fixture
def calls(monkeypatch):
    seen = []

    def fake_run_claude(args, **kwargs):
        seen.append(list(args))
        return subprocess.CompletedProcess(args, 0, "SPEAKER_1: " + "words " * 3000, "")
    monkeypatch.setattr(sg, "run_claude", fake_run_claude)
    return seen


def _gen(model):
    g = object.__new__(ScriptGenerator)
    g.ai_model = model
    return g


def _flag(args, name):
    return args[args.index(name) + 1]


def test_draft_uses_configured_claude_id_at_medium_effort(calls):
    _gen("claude-sonnet-5-5")._call_llm("sys", "user", min_chars=100)
    assert _flag(calls[0], "--model") == "claude-sonnet-5-5"
    assert _flag(calls[0], "--effort") == "medium"


def test_non_claude_generation_model_gets_no_cli_override():
    assert _gen("gpt-5")._draft_cli_options() == {}


def test_polish_passes_keep_utility_alias_and_low_effort(calls):
    _gen("claude-sonnet-5-5")._call_claude_p("sys", "user", timeout=360)
    assert _flag(calls[0], "--model") == sg._claude_cli_model()
    assert _flag(calls[0], "--effort") == "low"


def test_catalog_knows_the_activated_models():
    assert provider_for("claude-sonnet-5-5") == "anthropic"
    assert provider_for("claude-opus-5-5") == "anthropic"
    assert CATALOG["elevenlabs"]["eleven_v4"]["max_characters"] == 10000


@pytest.mark.parametrize("model, size", [("eleven_v4", 2000), ("eleven_v3", 2500)])
def test_dialogue_chunk_size_follows_model(monkeypatch, tmp_path, model, size):
    seen = {}

    def capture(script, max_chunk_size):
        seen["size"] = max_chunk_size
        raise RuntimeError("stop")
    monkeypatch.setattr("src.audio.audio_generator.chunk_dialogue_script", capture)
    a = object.__new__(AudioGenerator)
    a.audio_dir = tmp_path
    with pytest.raises(Exception):
        a._generate_chunked_dialogue_audio("SPEAKER_1: hi", topic="T", voice_config={},
                                           dialogue_model=model)
    assert seen["size"] == size
