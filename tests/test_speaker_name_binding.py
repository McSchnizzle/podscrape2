"""Regression tests for the Ep 691 speaker-name-binding guard.

Ep 691 (2026-07-09) aired with the hosts introducing themselves with swapped
names: SPEAKER_2 (Malcolm's voice) said "I'm Amara" and SPEAKER_1 (Amara's
voice) said "And I'm Malcolm". _enforce_speaker_name_binding repairs
self-introductions deterministically from voice_config and must never touch
hosts referring to each other.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.generation.script_generator import ScriptGenerator

VOICE_CONFIG = {
    "speaker_1": {"name": "Amara", "voice_id": "v1"},
    "speaker_2": {"name": "Malcolm", "voice_id": "v2"},
}


def _guard(script, vc=VOICE_CONFIG):
    sg = ScriptGenerator.__new__(ScriptGenerator)
    return sg._enforce_speaker_name_binding(script, vc)


def test_swapped_intros_are_repaired():
    script = (
        "SPEAKER_2: Welcome to the digest, July ninth. I'm Amara.\n"
        "SPEAKER_1: And I'm Malcolm. Nine episodes today.\n"
    )
    fixed, repairs = _guard(script)
    assert repairs == 2
    assert "SPEAKER_2: Welcome to the digest, July ninth. I'm Malcolm." in fixed
    assert "SPEAKER_1: And I'm Amara. Nine episodes today." in fixed


def test_correct_intros_untouched():
    script = (
        "SPEAKER_1: Welcome. I'm Amara.\n"
        "SPEAKER_2: And I'm Malcolm.\n"
    )
    fixed, repairs = _guard(script)
    assert repairs == 0
    assert fixed == script


def test_cross_references_untouched():
    script = (
        "SPEAKER_1: As Malcolm said earlier, the paper holds up.\n"
        "SPEAKER_2: Amara flagged that too.\n"
    )
    fixed, repairs = _guard(script)
    assert repairs == 0
    assert fixed == script


def test_i_am_variant_repaired():
    script = "SPEAKER_1: I am Malcolm, and this is the digest.\n"
    fixed, repairs = _guard(script)
    assert repairs == 1
    assert "I am Amara" in fixed


def test_missing_voice_config_is_noop():
    script = "SPEAKER_2: I'm Amara.\n"
    fixed, repairs = _guard(script, vc=None)
    assert repairs == 0
    assert fixed == script


def test_tagged_line_repaired():
    script = "SPEAKER_2: [warmly] Welcome back. I'm Amara.\n"
    fixed, repairs = _guard(script)
    assert repairs == 1
    assert "I'm Malcolm" in fixed
