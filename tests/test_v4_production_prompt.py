"""Production prompt carries verified Eleven v4 delivery guidance, and the
OpenAI-TTS fallback never reads a v4 tag aloud."""
from pathlib import Path

from src.audio.audio_generator import AudioGenerator

PROMPT = (Path(__file__).parent.parent / ".claude" / "commands" / "generate-digest.md").read_text()


def test_prompt_names_v4_and_its_new_capabilities():
    assert "Eleven v4" in PROMPT
    for new in ("[pause]", "[long pause]", "no training data"):
        assert new in PROMPT


def test_prompt_keeps_ssml_out_and_effects_out():
    assert "`<break>`" in PROMPT and "Neither v3 nor v4 supports" in PROMPT
    assert "Never use sound effects" in PROMPT


def test_prompt_keeps_the_existing_budget():
    for rule in ("No more than 25 tags total", "No more than 35% of turns",
                 "Never use the same tag more than 4 times"):
        assert rule in PROMPT


def test_prompt_host_names_match_new_voices():
    assert "SPEAKER_1 is Alexis, SPEAKER_2 is Brandon" in PROMPT
    assert "Amara" not in PROMPT and "Malcolm" not in PROMPT


def test_openai_fallback_strips_every_v4_tag():
    a = object.__new__(AudioGenerator)
    text = ("[whispers] quiet [sarcastic] sure [laughs harder] ha [long pause] "
            "then [mischievously] yes [exhales] ok [pause] done [excited] go")
    out = a._strip_audio_tags(text)
    assert "[" not in out and "]" not in out
    assert out.split() == ["quiet", "sure", "ha", "then", "yes", "ok", "done", "go"]


def test_openai_fallback_keeps_ordinary_brackets():
    a = object.__new__(AudioGenerator)
    assert a._strip_audio_tags("the [GPT-6] launch") == "the [GPT-6] launch"
