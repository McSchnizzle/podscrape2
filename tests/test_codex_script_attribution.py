"""Codex attribution: the last line of a script whose words Codex wrote.

Paul listens to each digest blind, then reads the script. When Codex words
remain in the published script, it ends with one attribution line. These
tests pin four promises:

1. RETAINED AUTHORSHIP. Provenance comes from the completion result the
   transport returns (run_claude marks Codex answers provider='codex') and is
   tracked per word: an accepted rewrite keeps the writer of every word it
   left unchanged and owns the words it produced. Rejected, failed and
   superseded Codex output leaves no trace; a Codex draft rewritten by Claude
   is reported as mixed with the share that actually survived.
2. LAST LINE. The marker is the final line of the persisted script, a stale
   marker never survives, and no claim about quota exhaustion is made.
3. NEVER SPOKEN. Every TTS entry point and both metadata readers strip it.
4. NEVER FED BACK. Every reader that hands a stored script to a model
   strips it, including the nightly create_digest dedup (run, not inspected).

All offline: the transport is faked at run_claude, the database is a fake
session, nothing is generated, sent, or written outside tmp_path.
"""
from __future__ import annotations

import inspect
import subprocess
from datetime import date
from types import SimpleNamespace

import pytest

import src.generation.script_generator as sg
from src.audio.audio_generator import AudioGenerator
from src.audio.metadata_generator import MetadataGenerator
from src.generation import lead_repeat_guard as guard
from src.generation.script_attribution import (
    ATTRIBUTION_PREFIX,
    AuthoredText,
    AuthorshipTracker,
    append_attribution,
    attribution_after_rewrite,
    attribution_line,
    strip_attribution,
)
from src.generation.script_generator import ScriptGenerationError, ScriptGenerator
from src.utils.claude_quota_fallback import QuotaFallbackError

CODEX_MODEL = "gpt-6-astra"
CODEX = ("codex", CODEX_MODEL)
CLAUDE = ("claude", "sonnet")
WRITTEN_BY_CODEX = f"Script attribution: written by Codex ({CODEX_MODEL})."
TURNS = "\n\n".join(
    f"SPEAKER_{i % 2 + 1}: turn number {i} with enough words to look like a real turn"
    for i in range(40)
)
WORDS = len(TURNS.split())


def claude_result(text):
    """What run_claude returns when Claude answered: no provider field."""
    return subprocess.CompletedProcess(["claude"], 0, text, "")


def codex_result(text):
    """What run_claude returns when Codex answered (see _finish)."""
    r = subprocess.CompletedProcess(["codex"], 0, text, "")
    r.provider, r.model = "codex", CODEX_MODEL
    r.fallback_reason = "claude_quota_exhausted"
    return r


@pytest.fixture
def transport(monkeypatch):
    """Queue of fake completion results, consumed one per completion call."""
    queue = []

    def fake_run_claude(args, **kwargs):
        item = queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    monkeypatch.setattr(sg, "run_claude", fake_run_claude)
    monkeypatch.setattr("src.generation.dedup_pass.run_claude", fake_run_claude)
    return queue


@pytest.fixture
def gen(monkeypatch):
    g = object.__new__(ScriptGenerator)
    g._authorship_tracker = AuthorshipTracker()
    g.topic_instructions = {}
    # No prior digests: the lead-repeat guard never trips unless a test says so.
    monkeypatch.setattr("src.generation.dedup_pass._fetch_prior_digests", lambda **k: [])
    monkeypatch.setattr("src.utils.claude_p_health.is_claude_p_healthy", lambda: True)
    return g


def last_line(text):
    return text.rstrip().rpartition("\n")[2]


def tracked(text, source):
    t = AuthorshipTracker()
    t.start(text, "draft", source)
    return t


def line_for(gen, final):
    return attribution_line(gen._authorship().finish(final))


def rewrite_fraction(text, every, word="zz"):
    """Replace every Nth word (never a speaker label), keeping line
    structure: a plausible accepted rewrite."""
    out, n = [], 0
    for line in text.splitlines():
        words = []
        for w in line.split():
            words.append(word if n % every == 1 and not w.startswith("SPEAKER_") else w)
            n += 1
        out.append(" ".join(words))
    return "\n".join(out)


# ---------------------------------------------------------------------------
# 1. Marker wording and placement
# ---------------------------------------------------------------------------


def test_no_marker_when_codex_wrote_nothing():
    t = tracked(TURNS, CLAUDE)
    assert attribution_line(t) is None
    assert append_attribution(TURNS, t.finish(TURNS)) == TURNS


def test_unknown_provenance_is_never_attributed_to_codex():
    """The OpenAI path returns plain text: no provenance, no marker."""
    assert attribution_line(tracked(TURNS, None)) is None


def test_all_codex_words_is_written_by_codex_on_the_last_line():
    out = append_attribution(TURNS, tracked(TURNS, CODEX).finish(TURNS))
    assert out == TURNS + "\n\n" + WRITTEN_BY_CODEX
    assert last_line(out) == WRITTEN_BY_CODEX

MIXED_DRAFT = ("Script attribution: Codex contributed to this script. Codex (gpt-6-astra) "
               "wrote the draft; Claude (sonnet) wrote or revised the rest.")


def test_codex_draft_revised_by_claude_says_contributed_without_numbers():
    t = tracked(TURNS, CODEX)
    t.apply("variety", TURNS, rewrite_fraction(TURNS, 4), CLAUDE)
    line = attribution_line(t)
    assert line == MIXED_DRAFT
    assert "%" not in line and "written by" not in line


def test_claude_draft_with_codex_rewrites_names_each_accepted_codex_stage():
    t = tracked(TURNS, CLAUDE)
    for stage in ("variety", "lead_rewrite", "length_repair"):
        t.apply(stage, TURNS, TURNS, CODEX)
    assert attribution_line(t) == (
        "Script attribution: Codex contributed to this script. Codex (gpt-6-astra) wrote "
        "the structural variety rewrite, opening rewrite and length compression; "
        "Claude (sonnet) wrote or revised the rest.")


def test_unrecorded_writer_is_named_honestly():
    t = tracked(TURNS, None)
    t.apply("variety", TURNS, TURNS, CODEX)
    assert attribution_line(t).endswith("an unrecorded writer wrote or revised the rest.")


def test_marker_never_claims_why_codex_ran():
    """The quota circuit can route a call to Codex without that call being
    refused, so the line states authorship only."""
    mixed = tracked(TURNS, CLAUDE)
    mixed.apply("variety", TURNS, rewrite_fraction(TURNS, 3), CODEX)
    for t in (tracked(TURNS, CODEX), mixed):
        line = attribution_line(t).lower()
        for word in ("quota", "token", "exhaust", "limit", "fallback"):
            assert word not in line


def test_stale_marker_removed_when_no_codex_words_remain():
    stale = TURNS + "\n\n" + WRITTEN_BY_CODEX
    assert append_attribution(stale, tracked(TURNS, CLAUDE).finish(TURNS)) == TURNS


def test_stale_marker_replaced_not_duplicated():
    stale = TURNS + "\n\nScript attribution: mixed authorship. Old claim.\n"
    out = append_attribution(stale, tracked(TURNS, CODEX).finish(TURNS))
    assert out.count(ATTRIBUTION_PREFIX) == 1
    assert last_line(out) == WRITTEN_BY_CODEX


def test_strip_removes_only_a_final_marker_line():
    inside = "SPEAKER_1: Script attribution: is what we call credit.\n\n" + TURNS
    assert strip_attribution(inside) == inside
    marked = TURNS + "\n\n" + WRITTEN_BY_CODEX + "\n\n"
    assert strip_attribution(marked) == TURNS
    assert strip_attribution(strip_attribution(marked)) == TURNS
    assert strip_attribution("") == ""
    assert strip_attribution(None) is None


# ---------------------------------------------------------------------------
# 2. Provenance at the transport boundary
# ---------------------------------------------------------------------------


def test_call_claude_p_reports_the_provider_that_actually_answered(transport):
    transport += [claude_result(" from claude \n"), codex_result(" from codex \n")]
    a = ScriptGenerator._call_claude_p("sys", "user")
    b = ScriptGenerator._call_claude_p("sys", "user")
    assert (a, a.provider) == ("from claude", "claude")
    assert (b, b.provider, b.model) == ("from codex", "codex", CODEX_MODEL)


def test_retry_wrapper_passes_provenance_through(gen, transport):
    transport.append(codex_result(TURNS))
    out = gen._call_claude_p_with_retry("sys", "user", context="t", min_chars=10)
    assert out.provider == "codex"


def test_failed_codex_fallback_records_nothing(gen, transport, monkeypatch):
    monkeypatch.setattr(ScriptGenerator, "_notify_claude_p_exhausted", staticmethod(lambda *a: None))
    transport.append(QuotaFallbackError("Codex completion failed"))
    with pytest.raises(QuotaFallbackError):
        gen._call_claude_p_with_retry("sys", "user", context="t")
    assert gen._authorship().stages == {}


def test_too_short_codex_attempt_then_claude_success_is_claude(gen, transport, monkeypatch):
    """A Codex answer rejected by the hard floor must not count."""
    import time as _time  # the retry loop imports time locally
    monkeypatch.setattr(_time, "sleep", lambda s: None)
    transport += [codex_result("short"), claude_result(TURNS)]
    out = gen._call_claude_p_with_retry("sys", "user", context="t", min_chars=1000)
    gen._accept_draft(out)
    assert line_for(gen, TURNS) is None


# ---------------------------------------------------------------------------
# 3. Retained authorship across drafts and rewrites
# ---------------------------------------------------------------------------


def test_superseded_codex_draft_and_its_variety_pass_leave_no_trace(gen):
    """Expansion: the first (Codex) draft and its variety revision are
    discarded; the draft that ships is Claude's."""
    codex_draft = AuthoredText(TURNS, *CODEX)
    gen._accept_draft(codex_draft, (TURNS, AuthoredText(rewrite_fraction(TURNS, 3), *CODEX)))
    assert line_for(gen, rewrite_fraction(TURNS, 3)) == WRITTEN_BY_CODEX
    gen._accept_draft(AuthoredText(TURNS, *CLAUDE), None)
    assert line_for(gen, TURNS) is None


def test_cleanup_variety_pass_kept_only_when_accepted(gen, transport):
    revised = TURNS.replace("turn number", "turn no.")
    transport.append(codex_result(revised))
    gen._apply_anti_ai_cleanup(TURNS)
    before, after = gen._cleanup_variety
    assert (before, after, after.provider) == (TURNS, revised, "codex")

    transport.append(codex_result("SPEAKER_1: too short"))  # rejected: < 50%
    gen._apply_anti_ai_cleanup(TURNS)
    assert gen._cleanup_variety is None

    gen._apply_anti_ai_cleanup(TURNS, skip_variety_pass=True)
    assert gen._cleanup_variety is None


def test_accepted_codex_variety_after_claude_draft_is_mixed(gen, transport):
    gen._accept_draft(AuthoredText(TURNS, *CLAUDE))
    revised = rewrite_fraction(TURNS, 10)
    transport.append(codex_result(revised))
    out = gen.finalize_script(TURNS, topic="T", floor=100, already_varied=False)
    assert out == revised
    assert line_for(gen, out) == (
        "Script attribution: Codex contributed to this script. Codex (gpt-6-astra) "
        "wrote the structural variety rewrite; Claude (sonnet) wrote or revised the rest.")


def test_claude_variety_after_codex_draft_is_contributed_not_written_by(gen, transport):
    gen._accept_draft(AuthoredText(TURNS, *CODEX))
    revised = rewrite_fraction(TURNS, 2)
    transport.append(claude_result(revised))
    out = gen.finalize_script(TURNS, topic="T", floor=100, already_varied=False)
    assert out == revised
    assert line_for(gen, out) == MIXED_DRAFT


@pytest.mark.parametrize("bad", [
    "SPEAKER_1: far too short",                       # under half the length
    TURNS.replace("SPEAKER_2", "HOST"),                # lost speaker labels
    TURNS + "\n\n" + TURNS,                           # grew by over 15%
])
def test_rejected_codex_variety_leaves_no_trace(gen, transport, bad):
    gen._accept_draft(AuthoredText(TURNS, *CLAUDE))
    transport.append(codex_result(bad))
    out = gen.finalize_script(TURNS, topic="T", floor=100, already_varied=False)
    assert out == TURNS
    assert line_for(gen, out) is None


def test_codex_variety_that_breaches_the_floor_leaves_no_trace(gen, transport):
    gen._accept_draft(AuthoredText(TURNS, *CLAUDE))
    transport.append(codex_result(TURNS[: int(len(TURNS) * 0.9)]))
    out = gen.finalize_script(TURNS, topic="T", floor=len(TURNS) - 5, already_varied=False)
    assert out == TURNS
    assert line_for(gen, out) is None


def _tripped(lead):
    return SimpleNamespace(tripped=True, lead=lead, matched_digest_id=1,
                           matched_digest_date="2026-10-01", matched_lead=lead,
                           score=0.9, threshold=0.5)


def test_accepted_codex_lead_rewrite_credits_only_the_new_opening(gen, transport, monkeypatch):
    gen._accept_draft(AuthoredText(TURNS, *CLAUDE))
    lead = TURNS[:400]
    checks = iter([_tripped(lead), SimpleNamespace(tripped=False)])
    monkeypatch.setattr(guard, "check_lead_repeat", lambda *a, **k: next(checks))
    monkeypatch.setattr(guard, "build_rewrite_prompt", lambda *a: "rewrite")
    monkeypatch.setattr(guard, "contains_unsupported_numbers", lambda *a: False)
    transport.append(codex_result("SPEAKER_1: a fresh opening " + "word " * 60))
    out = gen.finalize_script(TURNS, topic="T", already_varied=True)
    assert out.startswith("SPEAKER_1: a fresh opening")
    assert "Codex (gpt-6-astra) wrote the opening rewrite;" in line_for(gen, out)


@pytest.mark.parametrize("why", ["short", "numbers", "still_repeats"])
def test_rejected_codex_lead_rewrite_leaves_no_trace(gen, transport, monkeypatch, why):
    gen._accept_draft(AuthoredText(TURNS, *CLAUDE))
    lead = TURNS[:400]
    second = SimpleNamespace(tripped=(why == "still_repeats"), score=0.9)
    checks = iter([_tripped(lead), second])
    monkeypatch.setattr(guard, "check_lead_repeat", lambda *a, **k: next(checks))
    monkeypatch.setattr(guard, "build_rewrite_prompt", lambda *a: "rewrite")
    monkeypatch.setattr(guard, "contains_unsupported_numbers", lambda *a: why == "numbers")
    text = "SPEAKER_1: x" if why == "short" else "SPEAKER_1: a fresh opening " + "word " * 60
    transport.append(codex_result(text))
    out = gen.finalize_script(TURNS, topic="T", already_varied=True)
    assert out == TURNS
    assert line_for(gen, out) is None


def _long_script(gen, monkeypatch):
    monkeypatch.setattr(ScriptGenerator, "_is_dialogue_mode", lambda self, t: True)
    monkeypatch.setattr(guard, "contains_unsupported_numbers", lambda *a: False)
    long_script = "\n\n".join(f"SPEAKER_{i % 2 + 1}: " + "long turn text " * 30 for i in range(90))
    gen._accept_draft(AuthoredText(long_script, *CLAUDE))
    return long_script


COMPRESSED = "\n\n".join(f"SPEAKER_{i % 2 + 1}: " + "short turn text " * 20 for i in range(70))


def test_accepted_codex_length_repair_is_credited(gen, transport, monkeypatch):
    long_script = _long_script(gen, monkeypatch)
    assert len(long_script) > 35000 and 10000 <= len(COMPRESSED) <= 35000
    transport.append(codex_result(COMPRESSED))
    out = gen.enforce_dialogue_length(long_script, "T", floor=10000)
    assert "Codex (gpt-6-astra) wrote the length compression;" in line_for(gen, out)


def test_rejected_codex_length_repair_leaves_no_trace(gen, transport, monkeypatch):
    long_script = _long_script(gen, monkeypatch)
    transport.append(codex_result("SPEAKER_1: too short\n\nSPEAKER_2: yes"))
    with pytest.raises(ScriptGenerationError):
        gen.enforce_dialogue_length(long_script, "T", floor=10000)
    assert line_for(gen, long_script) is None


def test_codex_length_repair_failing_final_validation_is_rolled_back(gen, transport, monkeypatch):
    """Passes the first bounds check, then finalization leaves it unusable:
    the repair is rejected and its provisional credit is undone."""
    long_script = _long_script(gen, monkeypatch)
    transport.append(codex_result(COMPRESSED))
    monkeypatch.setattr(ScriptGenerator, "finalize_script",
                        lambda self, s, **k: "SPEAKER_1: gutted\n\nSPEAKER_2: yes")
    with pytest.raises(ScriptGenerationError):
        gen.enforce_dialogue_length(long_script, "T", floor=10000)
    assert line_for(gen, long_script) is None


def test_apply_attribution_end_to_end_last_line(gen):
    gen._accept_draft(AuthoredText(TURNS, *CODEX))
    out = gen._apply_attribution(TURNS + "\n")
    assert last_line(out) == WRITTEN_BY_CODEX
    gen._authorship_tracker = AuthorshipTracker()
    gen._accept_draft(AuthoredText(TURNS, *CLAUDE))
    assert gen._apply_attribution(out) == TURNS


def test_general_summary_codex_draft_is_marked(gen, monkeypatch, tmp_path):
    gen.max_output_tokens = 2000
    gen.scripts_dir = tmp_path
    gen.ai_model = "claude-sonnet-4-6"
    monkeypatch.setattr(ScriptGenerator, "_call_llm",
                        lambda self, s, u, **k: AuthoredText(TURNS, *CODEX))
    script, _ = gen._generate_general_summary_script(
        [SimpleNamespace(title="t", published_date=date(2026, 10, 1),
                         transcript_content="x " * 50, scores={})], date(2026, 10, 2))
    assert line_for(gen, script) == WRITTEN_BY_CODEX


# ---------------------------------------------------------------------------
# 4. Re-attribution after a later rewrite of a published script
# ---------------------------------------------------------------------------

PUBLISHED_CODEX = TURNS + "\n\n" + WRITTEN_BY_CODEX


def test_claude_dedup_of_codex_script_is_contributed_not_written_by():
    out = attribution_after_rewrite(PUBLISHED_CODEX, rewrite_fraction(TURNS, 4), "dedup", CLAUDE)
    assert last_line(out) == (
        "Script attribution: Codex contributed to this script. Codex (gpt-6-astra) wrote "
        "the earlier version; Claude (sonnet) wrote or revised the rest.")
    assert out.count(ATTRIBUTION_PREFIX) == 1


def test_codex_dedup_of_codex_script_stays_written_by_codex():
    out = attribution_after_rewrite(PUBLISHED_CODEX, rewrite_fraction(TURNS, 4), "dedup", CODEX)
    assert last_line(out) == WRITTEN_BY_CODEX


def test_codex_dedup_of_unattributed_script_names_only_the_dedup():
    out = attribution_after_rewrite(TURNS, rewrite_fraction(TURNS, 4), "dedup", CODEX)
    assert last_line(out) == (
        "Script attribution: Codex contributed to this script. Codex (gpt-6-astra) wrote "
        "the dedup rewrite; an unrecorded writer wrote or revised the rest.")


def test_claude_dedup_of_unattributed_script_has_no_marker():
    after = rewrite_fraction(TURNS, 4)
    assert attribution_after_rewrite(TURNS, after, "dedup", CLAUDE) == after


def test_codex_dedup_of_mixed_script_is_still_contributed():
    """A mixed earlier script is never upgraded to "written by Codex"."""
    out = attribution_after_rewrite(TURNS + "\n\n" + MIXED_DRAFT, TURNS, "dedup", CODEX)
    assert "Codex contributed to this script" in last_line(out)
    assert "another writer wrote or revised the rest." in last_line(out)


def _load_script(name):
    import importlib.util
    from pathlib import Path
    path = Path(__file__).parent.parent / "scripts" / name
    spec = importlib.util.spec_from_file_location(name[:-3] + "_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("dedup_writer, expected", [
    (claude_result, "Codex contributed to this script"),
    (codex_result, WRITTEN_BY_CODEX),
])
def test_run_script_dedup_apply_strips_input_and_reattributes(
        monkeypatch, transport, dedup_writer, expected):
    """Manual CLI: the model sees the body only, and --apply stores the
    rewrite with re-measured authorship as its last line."""
    import src.utils.phase_bootstrap as boot
    monkeypatch.setattr(boot, "bootstrap_phase", lambda *a, **k: None)
    monkeypatch.setattr("src.utils.claude_p_health.is_claude_p_healthy", lambda: True)
    tool = _load_script("run_script_dedup.py")
    digest = SimpleNamespace(id=5, topic="T", digest_date=date(2026, 10, 2),
                             script_content=PUBLISHED_CODEX, script_content_predupe=None,
                             script_word_count=0)
    session = _FakeSession(rows=[digest])
    commits = []
    session.commit = lambda: commits.append(True)
    monkeypatch.setattr("src.database.models.get_database_manager", _fake_db(session))
    monkeypatch.setattr("src.generation.dedup_pass._fetch_prior_digests",
                        lambda **k: [{"id": 1, "date": "2026-10-01", "content": "SPEAKER_1: old"}])
    prompts = []
    real_build = __import__("src.generation.dedup_pass", fromlist=["x"])._build_user_prompt
    monkeypatch.setattr("src.generation.dedup_pass._build_user_prompt",
                        lambda draft, prior: prompts.append(draft) or real_build(draft, prior))
    rewritten = rewrite_fraction(TURNS, 4)
    transport.append(dedup_writer(rewritten))
    monkeypatch.setattr("sys.argv", ["run_script_dedup.py", "--digest-id", "5", "--apply"])
    assert tool.main() == 0
    assert prompts == [TURNS]
    assert commits and digest.script_content_predupe == PUBLISHED_CODEX
    assert digest.script_content.startswith(rewritten)
    assert digest.script_content.count(ATTRIBUTION_PREFIX) == 1
    assert expected in last_line(digest.script_content)


# ---------------------------------------------------------------------------
# 5. Never spoken: every TTS entry point, and metadata
# ---------------------------------------------------------------------------

MARKED = TURNS + "\n\n" + WRITTEN_BY_CODEX


class _Captured(Exception):
    pass


@pytest.fixture
def audio(tmp_path):
    a = object.__new__(AudioGenerator)
    a.audio_dir = tmp_path
    return a


def _assert_unspoken(text):
    assert ATTRIBUTION_PREFIX not in text
    assert "Codex" not in text


def test_tts_dialogue_route_never_receives_marker(audio, monkeypatch):
    seen = {}
    cfg = SimpleNamespace(use_dialogue_api=True, voice_config={"speaker_1": {}}, dialogue_model="eleven_v3")
    monkeypatch.setattr(AudioGenerator, "_get_topic_config", lambda self, t: cfg)

    def capture(self, script_content, **k):
        seen["text"] = script_content
        raise _Captured
    monkeypatch.setattr(AudioGenerator, "_generate_chunked_dialogue_audio", capture)
    with pytest.raises(_Captured):
        audio.generate_audio_for_script(MARKED, topic="T")
    _assert_unspoken(seen["text"])


def test_tts_single_voice_route_never_receives_marker(audio, monkeypatch):
    seen = {}
    monkeypatch.setattr(AudioGenerator, "_get_topic_config", lambda self, t: None)

    def capture(self, script_content):
        seen["text"] = script_content
        raise _Captured
    monkeypatch.setattr(AudioGenerator, "_clean_script_for_tts", capture)
    with pytest.raises(_Captured):
        audio.generate_audio_for_script(MARKED, topic="T")
    _assert_unspoken(seen["text"])


def test_tts_chunked_dialogue_entry_strips_marker(audio, monkeypatch):
    seen = {}

    def capture(script, max_chunk_size):
        seen["text"] = script
        raise _Captured
    monkeypatch.setattr("src.audio.audio_generator.chunk_dialogue_script", capture)
    with pytest.raises(Exception):
        audio._generate_chunked_dialogue_audio(MARKED, topic="T", voice_config={},
                                               dialogue_model="eleven_v3")
    _assert_unspoken(seen["text"])


def test_tts_openai_dialogue_fallback_strips_marker(audio, monkeypatch, tmp_path):
    """Its turn regex runs to end of text, so an unstripped marker would be
    read aloud as part of the final speaker's line."""
    spoken = []
    monkeypatch.setattr("tempfile.mkdtemp", lambda prefix="": str(tmp_path))

    def capture(self, text, voice="nova", model="tts-1"):
        spoken.append(text)
        raise _Captured
    monkeypatch.setattr(AudioGenerator, "_generate_openai_tts_chunk", capture)
    turns = []
    real_strip = AudioGenerator._strip_audio_tags
    monkeypatch.setattr(AudioGenerator, "_strip_audio_tags",
                        lambda self, t: turns.append(real_strip(self, t)) or turns[-1])
    with pytest.raises(Exception):
        audio._generate_dialogue_audio_openai(MARKED, voice_config={}, topic="T")
    assert turns, "the parser should have produced turns"
    for t in turns:
        _assert_unspoken(t)


def test_tts_openai_narrative_fallback_strips_marker(audio, monkeypatch):
    seen = {}

    def capture(self, script_content):
        seen["text"] = script_content
        raise _Captured
    monkeypatch.setattr(AudioGenerator, "_clean_script_for_tts", capture)
    with pytest.raises(_Captured):
        audio._generate_narrative_audio_openai(MARKED, topic="T")
    _assert_unspoken(seen["text"])


def test_digest_tts_path_routes_through_stripping_entry_points():
    """generate_audio_for_digest reads digest.script_content and must hand it
    only to the four entry points tested above."""
    src = inspect.getsource(AudioGenerator)
    start = src.index("if not digest.script_content:")
    block = src[start:start + 3000]
    called = {name for name in (
        "_generate_chunked_dialogue_audio", "_generate_dialogue_audio_openai",
        "generate_audio_for_script", "_generate_narrative_audio_openai",
        "_generate_tts_audio", "_clean_script_for_tts", "chunk_dialogue_script",
    ) if f"{name}(" in block}
    assert called == {"_generate_chunked_dialogue_audio", "_generate_dialogue_audio_openai",
                      "generate_audio_for_script", "_generate_narrative_audio_openai"}


def test_metadata_from_database_never_sees_marker(monkeypatch):
    seen = {}
    m = object.__new__(MetadataGenerator)

    def capture(self, script_content, **k):
        seen["text"] = script_content
        return "ok"
    monkeypatch.setattr(MetadataGenerator, "_generate_metadata_with_claude_p", capture)
    digest = SimpleNamespace(id=1, script_content=MARKED, topic="T", digest_date=None)
    assert m.generate_metadata_for_digest(digest, episodes=[]) == "ok"
    _assert_unspoken(seen["text"])


def test_metadata_from_file_never_sees_marker(tmp_path):
    m = object.__new__(MetadataGenerator)
    f = tmp_path / "script.md"
    f.write_text(MARKED, encoding="utf-8")
    _assert_unspoken(m._extract_script_content(str(f)))


# ---------------------------------------------------------------------------
# 6. Never fed back to a model: stored scripts read as downstream input
# ---------------------------------------------------------------------------

SHORT_MARKED = "SPEAKER_1: a short prior script\n\n" + WRITTEN_BY_CODEX


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def __getattr__(self, name):          # filter, filter_by, order_by, limit...
        return lambda *a, **k: self

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeSession:
    def __init__(self, rows=(), executed=()):
        self.rows, self.executed = list(rows), list(executed)

    def query(self, *a, **k):
        return _FakeQuery(self.rows)

    def get(self, *a, **k):
        return None

    def execute(self, *a, **k):
        return SimpleNamespace(fetchall=lambda: list(self.executed))

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _fake_db(session):
    return lambda: SimpleNamespace(get_session=lambda: session)


def test_creator_briefing_material_excludes_marker():
    from src.publishing.creator_briefing import gather_material
    digest = SimpleNamespace(id=1, script_content=MARKED, mp3_summary="summary",
                             mp3_title="title", digest_date="2026-10-02",
                             github_url="https://example.invalid/r")
    material = gather_material(_FakeSession(), digest)
    assert material.script == TURNS
    _assert_unspoken(material.script)


def test_prior_digests_for_lead_guard_and_dedup_pass_are_stripped(monkeypatch):
    from src.generation.dedup_pass import _fetch_prior_digests
    row = SimpleNamespace(id=7, digest_date=None, script_content=MARKED)
    monkeypatch.setattr("src.database.models.get_database_manager",
                        _fake_db(_FakeSession(rows=[row])))
    out = _fetch_prior_digests(topic="T", limit=3)
    assert [d["content"] for d in out] == [TURNS]


def test_arc_reconciler_prior_scripts_are_stripped(monkeypatch):
    from src.topic_tracking.digest_arc_reconciler import DigestArcReconciler
    rec = object.__new__(DigestArcReconciler)
    rec.lookback = 3
    row = SimpleNamespace(digest_date=None, script_content=SHORT_MARKED)
    monkeypatch.setattr("src.database.models.get_database_manager",
                        _fake_db(_FakeSession(rows=[row])))
    out = rec._get_recent_digest_scripts("T")
    assert out[0]["content"] == "SPEAKER_1: a short prior script"


def _load_replay():
    return _load_script("replay_digest.py")


def test_replay_lead_guard_priors_are_stripped(monkeypatch):
    replay = _load_replay()
    monkeypatch.setattr(replay, "get_database_manager",
                        _fake_db(_FakeSession(executed=[(9, "2026-10-01", MARKED)])))
    seen = {}

    def capture(script, topic, prior_digests):
        seen["priors"] = prior_digests
        raise _Captured
    monkeypatch.setattr(replay.guard, "check_lead_repeat", capture)
    gen = SimpleNamespace(generate_script=lambda *a, **k: (TURNS, 0),
                          finalize_script=lambda s, **k: s,
                          _is_dialogue_mode=lambda t: True)
    with pytest.raises(_Captured):
        replay.run_one(gen, "T", [], None, None, SimpleNamespace(digest_id=10), 1)
    assert [p["content"] for p in seen["priors"]] == [TURNS]


def test_replay_dedup_prior_scripts_are_stripped(monkeypatch):
    replay = _load_replay()
    ep = SimpleNamespace(id=1, title="t", transcript_content="x")
    monkeypatch.setattr(replay, "load_digest_pool", lambda i: ("T", None, [ep]))
    monkeypatch.setattr(replay, "ScriptGenerator", lambda: SimpleNamespace(
        _check_topic_repetition=lambda e, t: (False, "", None)))
    monkeypatch.setattr(replay, "get_database_manager",
                        _fake_db(_FakeSession(executed=[(MARKED,), (SHORT_MARKED,)])))
    seen = {}

    def capture(episodes, prior_digest_scripts, **k):
        seen["priors"] = prior_digest_scripts
        raise _Captured
    monkeypatch.setattr("src.generation.transcript_dedup.dedup_episode_batch", capture)
    monkeypatch.setattr("sys.argv", ["replay_digest.py", "--digest-id", "10"])
    with pytest.raises(_Captured):
        replay.main()
    assert seen["priors"] == [TURNS, "SPEAKER_1: a short prior script"]


# ---------------------------------------------------------------------------
# 7. The nightly path, run end to end: create_digest
# ---------------------------------------------------------------------------

LONG_TURNS = "\n\n".join(
    f"SPEAKER_{i % 2 + 1}: nightly turn {i}" + " with plenty of real sounding words" * 5
    for i in range(140)
)


@pytest.mark.parametrize("draft_writer, expect_marker", [
    (codex_result, True),
    (claude_result, False),
])
def test_create_digest_strips_priors_and_marks_only_retained_codex_text(
        gen, transport, monkeypatch, tmp_path, draft_writer, expect_marker):
    """Runs the real create_digest with the database and model faked: prior
    scripts reach the dedup model without markers, and the persisted script
    ends with the marker exactly when the draft that shipped was Codex's."""
    assert 25000 <= len(LONG_TURNS) <= 35000      # no expansion, no length repair
    ep = SimpleNamespace(id=11, title="Episode", transcript_content="words " * 400,
                         scores={"T": 0.9})
    created = {}
    gen.min_episodes_per_digest = 1
    gen.scripts_dir = tmp_path
    gen.digest_repo = SimpleNamespace(get_by_topic_date=lambda *a: None,
                                      create=lambda d: created.setdefault("digest", d) and 42)
    gen.episode_repo = SimpleNamespace(get_by_id=lambda i: None)
    for name, value in {
        "get_qualifying_episodes": lambda self, *a: [ep],
        "_check_topic_repetition": lambda self, e, t: (False, "", None),
        "_is_dialogue_mode": lambda self, t: True,
        "_get_extra_scored_episodes": lambda self, *a, **k: [],
        "_safe_build_daily_theme_emphasis": lambda self, *a: None,
        "_persist_digest_links": lambda self, *a: None,
        "_record_topic_generation": lambda self, *a: None,
        "mark_digest_episodes_as_digested": lambda self, *a: None,
        "mark_covered_story_arcs": lambda self, *a: 0,
    }.items():
        monkeypatch.setattr(ScriptGenerator, name, value)

    def generate_script(self, topic, episodes, digest_date, **kwargs):
        # The real draft path's provenance hand-off: completion, then accept.
        draft = self._call_claude_p_with_retry("sys", "user", context="draft")
        self._accept_draft(draft)
        return draft, len(draft)
    monkeypatch.setattr(ScriptGenerator, "generate_script", generate_script)
    transport.append(draft_writer(LONG_TURNS))

    prior_rows = [SimpleNamespace(script_content=MARKED),
                  SimpleNamespace(script_content=SHORT_MARKED)]
    monkeypatch.setattr("src.database.models.get_database_manager",
                        _fake_db(_FakeSession(rows=prior_rows)))
    seen = {}

    def fake_dedup(episodes, prior_digest_scripts, **k):
        seen["priors"] = prior_digest_scripts
        return [SimpleNamespace(below_floor_action=None, skipped=True)], None
    monkeypatch.setattr("src.generation.transcript_dedup.dedup_episode_batch", fake_dedup)

    digest = gen.create_digest("T", date(2026, 10, 2))

    assert seen["priors"] == [TURNS, "SPEAKER_1: a short prior script"]
    stored = created["digest"].script_content
    assert digest is created["digest"] and stored.startswith(LONG_TURNS)
    if expect_marker:
        assert stored == LONG_TURNS + "\n\n" + WRITTEN_BY_CODEX
    else:
        assert stored == LONG_TURNS and ATTRIBUTION_PREFIX not in stored
    assert created["digest"].script_content_predupe is None
