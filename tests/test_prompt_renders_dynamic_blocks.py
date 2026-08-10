"""The dynamic prompt blocks must actually reach the model. All three of them.

WHY. Until v4.01 `_build_claude_p_dialogue_prompt` accepted `story_arc_context`
and `repetition_instructions` as parameters and interpolated neither into the
prompt it returned. The caller computed both, logged "Adding repetition
avoidance for 5 recently covered arcs", and threw them away. In their place the
prompt asserted unconditionally that "Everything provided is NEW material.
Cover it all thoroughly" -- which is false whenever pre-generation dedup fails
open, and was the instruction that reached Claude on 2026-08-08 when the digest
reopened with the previous day's cold open.

The bug was invisible because the unit under test was the builder helper, whose
return value was correct. These tests assert on the RENDERED PROMPT STRING
instead, which is the only thing that can catch a parameter being dropped.
"""
from __future__ import annotations

from datetime import date

import pytest

from src.generation.script_generator import ScriptGenerator

SATURATED = [
    "Google DeepMind leadership shakeup: Hassabis steps back, Jeff Dean departs",
    "Qwen 3.8 Max launch",
]


@pytest.fixture
def generator():
    """A ScriptGenerator with no __init__ side effects (no DB, no API clients)."""
    return object.__new__(ScriptGenerator)


@pytest.fixture
def repetition_block(generator):
    return generator._build_repetition_avoidance_instructions(SATURATED, topic="AI and Technology")


# ---------------------------------------------------------------------------
# The block itself
# ---------------------------------------------------------------------------


def test_repetition_block_names_the_saturated_topics(repetition_block):
    """It used to be a constant string that discarded its argument."""
    for name in SATURATED:
        assert name in repetition_block


def test_repetition_block_forbids_leading_with_them(repetition_block):
    assert "DO NOT LEAD WITH THESE" in repetition_block
    assert "cold open" in repetition_block.lower()


def test_repetition_block_is_empty_when_nothing_is_saturated(generator):
    assert generator._build_repetition_avoidance_instructions([], topic="X") == ""


# ---------------------------------------------------------------------------
# Renderer 1: the claude -p dialogue prompt (the production path)
# ---------------------------------------------------------------------------


def _render_dialogue(generator, repetition_block, arc_context=""):
    return generator._build_claude_p_dialogue_prompt(
        system_prompt="HARDCODED FALLBACK PROMPT",
        topic="AI and Technology",
        topic_instructions="TOPIC INSTRUCTIONS MARKER",
        story_arc_context=arc_context,
        repetition_instructions=repetition_block,
        digest_date=date(2026, 8, 8),
        speaker_1_name="Natasha",
        speaker_2_name="Malcolm",
        num_episodes=9,
    )


def test_dialogue_prompt_contains_the_repetition_block(generator, repetition_block):
    """The regression. This is the assertion that would have failed since v3.x."""
    prompt = _render_dialogue(generator, repetition_block)
    assert "DO NOT LEAD WITH THESE" in prompt
    for name in SATURATED:
        assert name in prompt, f"saturated topic {name!r} never reached the prompt"


def test_dialogue_prompt_contains_the_story_arc_context(generator, repetition_block):
    prompt = _render_dialogue(generator, repetition_block, arc_context="## STORY ARC MARKER\n")
    assert "STORY ARC MARKER" in prompt


def test_dialogue_prompt_no_longer_asserts_everything_is_new(generator, repetition_block):
    """The false claim that turned a dedup miss into a duplicate intro."""
    prompt = _render_dialogue(generator, repetition_block).lower()
    assert "everything provided is new material" not in prompt
    assert "cover it all thoroughly" not in prompt


def test_dialogue_prompt_still_carries_topic_instructions(generator, repetition_block):
    assert "TOPIC INSTRUCTIONS MARKER" in _render_dialogue(generator, repetition_block)


# ---------------------------------------------------------------------------
# Renderer 2: the hardcoded fallback, used when the skill file is missing
# ---------------------------------------------------------------------------


def test_fallback_branch_also_carries_the_dynamic_blocks(generator, repetition_block, monkeypatch):
    """Returning `system_prompt` bare dropped both blocks on this branch too."""
    import src.generation.script_generator as sg

    class _MissingPath:
        """Stands in for pathlib.Path and reports the skill file as absent."""

        @property
        def parent(self):
            return self

        def __truediv__(self, other):
            return self

        def exists(self):
            return False

    monkeypatch.setattr(sg, "Path", lambda *a, **k: _MissingPath())

    prompt = _render_dialogue(generator, repetition_block, arc_context="## ARC MARKER\n")
    assert "HARDCODED FALLBACK PROMPT" in prompt
    assert "DO NOT LEAD WITH THESE" in prompt
    assert "ARC MARKER" in prompt


# ---------------------------------------------------------------------------
# Renderer 3: narrative interpolates the helper directly in its f-string.
# Guard the source so a refactor cannot quietly drop it.
# ---------------------------------------------------------------------------


def test_narrative_prompt_interpolates_both_blocks():
    import inspect

    import src.generation.script_generator as sg

    src = inspect.getsource(sg.ScriptGenerator._generate_narrative_script)
    assert "{story_arc_context}" in src
    assert "{repetition_instructions}" in src
