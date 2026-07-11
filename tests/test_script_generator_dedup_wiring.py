"""Integration tests for kanban #2861 (codex delta review round 3, team-lead
P2s): create_digest()'s dedup wiring end-to-end.

Round 1/2 fixed the dedup module's own floor invariant and covered it with
unit + batch-level tests against dedup_episode_batch()'s `combined` return.
The team lead's round-3 review flagged that production DISCARDS that
`combined` return (`dedup_results, _ = dedup_episode_batch(...)` in
create_digest()) and instead rebuilds the writer prompt from the filtered/
mutated `episodes` list -- so the real routing was only covered by a
source-order assertion, not a behavioral one. It also flagged that
too-short-ORIGINAL episodes (dedup never ran) were being permanently
marked digested alongside genuinely-redundant ones, which would silently
lose a uniquely-valuable-but-short episode forever.

These tests exercise the REAL dedup_episode_batch() -> dedup_transcript()
pipeline (only `_call_claude_p` is mocked, same pattern as
test_transcript_chunk_dedup.py) against a REAL in-memory test DB (same
pattern as test_script_generator_theme_emphasis.py: ScriptGenerator
constructed via object.__new__ to skip __init__, unrelated heavy machinery
mocked out), and verify:

  1. generate_script() actually receives the correctly filtered/restored
     episode transcripts -- dropped episodes absent, a restored episode's
     transcript >= the safety-net floor.
  2. A too-short-ORIGINAL episode is excluded from THIS digest's writer
     input but is NOT marked digested afterward (status stays 'scored' for
     reconsideration/retry -- a <500-char transcript is usually a failed or
     partial transcription, not an established duplicate). A genuinely-
     redundant episode (dedup ran, established no new content) DOES get
     marked digested -- siblings cover it.

Note: get_qualifying_episodes() and _get_extra_scored_episodes() both
enforce their own >=1000-char transcript floor upstream of dedup, which is
higher than dedup's own 500-char floor -- so in TODAY's wiring a
too-short-original can only reach dedup_transcript() if that upstream
floor ever drops, or via some other future caller. The safety net is
still correct defense-in-depth at the dedup module's own boundary, so
this test mocks get_qualifying_episodes() directly to inject a
deliberately-short transcript and exercise that boundary regardless of
the current upstream filter value.
"""
from __future__ import annotations

import pytest

pytest.importorskip("sqlalchemy", reason="SQLAlchemy is required for database integration tests")

from datetime import date, datetime, timedelta
from unittest.mock import Mock

from src.database.models import Digest, Episode, Feed
from src.generation import transcript_dedup
from src.generation.script_generator import ScriptGenerator
from src.generation.transcript_dedup import MIN_DEDUPED_CHARS, RESTORE_EXCERPT_CAP_CHARS

TOPIC = "AI and Technology"


def _ep19_style_original() -> str:
    """A transcript that argues a thesis from evidence, long enough that an
    over-aggressive dedup pass plausibly reduces it far below the
    safety-net floor -- mirrors the real kanban #2861 bug case."""
    thesis = (
        "Sonnet 5 is a disappointment. The benchmark numbers tell the story: "
        "on the coding eval it scored well behind the field, and on the "
        "reasoning suite the gap was even wider. "
    )
    return thesis * 60  # a few thousand chars, comfortably under 30k


def _patch_claude_healthy(monkeypatch):
    import importlib

    health = importlib.import_module("src.utils.claude_p_health")
    monkeypatch.setattr(health, "is_claude_p_healthy", lambda: True)


@pytest.fixture
def generator(monkeypatch, test_db_manager, feed_repo, episode_repo, digest_repo):
    """A ScriptGenerator with __init__ skipped (see
    test_script_generator_theme_emphasis.py for the pattern/rationale),
    backed by the REAL in-memory test DB for the dedup DB query and the
    episode-status assertions -- not mocked SQL chains. Unrelated heavy
    machinery (story-arc repetition, extra-episode padding, theme
    emphasis, script generation itself, arc marking, link persistence) is
    mocked out since it isn't what's under test here.
    """
    # create_digest()'s pre-gen dedup block does a LOCAL
    # `from src.database.models import get_database_manager` at call time,
    # so patching the attribute on its origin module (not on script_generator's
    # module-level import) is what actually affects that call site.
    monkeypatch.setattr("src.database.models.get_database_manager", lambda: test_db_manager)

    gen = object.__new__(ScriptGenerator)
    gen.episode_repo = episode_repo
    gen.digest_repo = digest_repo
    gen.digest_episode_link_repo = None  # keeps _persist_digest_links a safe no-op
    gen.story_arc_repo = None
    gen.topic_repo = None
    gen.web_config = None
    gen.min_episodes_per_digest = 1
    gen.max_episodes_per_digest = 9
    gen.topic_instructions = {}

    # Heavy machinery not under test here -- see module docstring.
    gen._check_topic_repetition = Mock(return_value=(False, "", []))
    gen._get_extra_scored_episodes = Mock(return_value=[])
    gen._safe_build_daily_theme_emphasis = Mock(return_value=None)
    gen.save_script = Mock(return_value="/nonexistent/fake_script_path.txt")
    gen._persist_digest_links = Mock()
    gen._record_topic_generation = Mock()
    gen.mark_digest_episodes_as_digested = Mock()
    gen.mark_covered_story_arcs = Mock(return_value=0)

    # Script generation itself is mocked (offline) and returns a script
    # above HARD_FLOOR so create_digest() runs to full completion without
    # entering the expansion loop (extras are mocked to [] anyway).
    gen.generate_script = Mock(return_value=("x" * 11_000, 2_000))

    return gen


def _make_episode(feed_repo, episode_repo, *, guid: str, transcript_content: str) -> Episode:
    feed_id = feed_repo.create(Feed(
        feed_url=f"https://example.com/{guid}.xml",
        title=f"Feed for {guid}",
        active=True,
    ))
    episode = Episode(
        episode_guid=guid,
        feed_id=feed_id,
        title=guid,
        published_date=datetime.now() - timedelta(days=1),
        audio_url=f"https://example.com/{guid}.mp3",
        duration_seconds=1800,
        transcript_content=transcript_content,
        scores={TOPIC: 0.8},
        status="scored",
    )
    episode.id = episode_repo.create(episode)
    return episode


def test_create_digest_routes_dedup_results_to_writer_and_marks_status_correctly(
    monkeypatch, generator, feed_repo, episode_repo, digest_repo,
):
    """End-to-end: generate_script() receives the correctly filtered/
    restored transcripts, and the two 'dropped' cases are handled
    differently -- genuinely-redundant gets marked digested, too-short-
    original does not."""
    _patch_claude_healthy(monkeypatch)

    # Seed a prior digest so create_digest()'s dedup DB query returns a
    # non-empty prior_scripts list (otherwise the whole dedup block is a
    # no-op and this test would prove nothing).
    digest_repo.create(Digest(
        topic=TOPIC,
        digest_date=date.today() - timedelta(days=1),
        script_content="Prior digest praising Sonnet 5's strong benchmark performance.",
        episode_count=1,
    ))

    ep_kept = _make_episode(
        feed_repo, episode_repo,
        guid="kept-ep",
        transcript_content="Genuinely novel material not covered anywhere else. " * 100,
    )
    # Early sentence boundary ("Confirmed.") then thousands of unpunctuated
    # chars -- the exact shape that broke the round-2 restore-boundary bug.
    ep_restored = _make_episode(
        feed_repo, episode_repo,
        guid="restored-ep",
        transcript_content="Confirmed. " + ("Sonnet 5 underperforms across every eval " * 200),
    )
    ep_redundant = _make_episode(
        feed_repo, episode_repo,
        guid="redundant-ep",
        transcript_content=_ep19_style_original(),
    )
    ep_tiny_original = _make_episode(
        feed_repo, episode_repo,
        guid="tiny-original-ep",
        transcript_content="Too short to be a real segment. " * 10,  # ~330 chars
    )
    assert len(ep_tiny_original.transcript_content) < MIN_DEDUPED_CHARS
    assert len(ep_restored.transcript_content) > RESTORE_EXCERPT_CAP_CHARS

    # get_qualifying_episodes()/_get_extra_scored_episodes() both enforce a
    # >=1000-char pre-filter upstream of dedup's own 500-char floor (see
    # module docstring) -- mock this directly to inject the deliberately-
    # short episode and exercise dedup's own boundary regardless.
    generator.get_qualifying_episodes = Mock(
        return_value=[ep_kept, ep_restored, ep_redundant, ep_tiny_original]
    )

    # Match ONLY against the CURRENT transcript-to-clean section of the
    # prompt (the part after "## TRANSCRIPT TO CLEAN:"), not the full
    # prompt. dedup's prior_content (which precedes that header) accumulates
    # every already-processed sibling's title AND its deduped/restored
    # output -- so ep_restored's RESTORED excerpt (pulled verbatim from its
    # own original, which repeats "underperforms across every eval") echoes
    # forward into ep_redundant's prior_content too. Matching the full
    # prompt would false-positive on that echo; matching only the transcript
    # section pins each fake response to the episode actually being cleaned
    # this round (same lesson as the title-leakage gotcha in
    # test_transcript_chunk_dedup.py, one structural layer deeper).
    def fake_call(prompt, timeout=300):
        current_section = prompt.split("## TRANSCRIPT TO CLEAN:", 1)[-1]
        if "underperforms across every eval" in current_section:  # ep_restored
            return "Confirmed."  # over-stripped stub -> triggers restore
        if "benchmark numbers tell the story" in current_section:  # ep_redundant
            return "[NO_NEW_CONTENT]"  # genuinely redundant -> dropped
        if "Genuinely novel material not covered anywhere else." in current_section:  # ep_kept
            return "Fresh material not covered by any prior digest or sibling episode. " * 60
        return "unexpected prompt"

    monkeypatch.setattr(transcript_dedup, "_call_claude_p", fake_call)

    digest = generator.create_digest(TOPIC, date.today())
    assert digest is not None

    # --- P2 #2: generate_script() must receive the correctly routed input ---
    assert generator.generate_script.call_count == 1
    call_args = generator.generate_script.call_args
    received_topic, received_episodes, received_date = call_args.args[:3]
    assert received_topic == TOPIC
    received_ids = {ep.id for ep in received_episodes}

    assert ep_kept.id in received_ids
    assert ep_restored.id in received_ids
    assert ep_redundant.id not in received_ids
    assert ep_tiny_original.id not in received_ids

    restored_received = next(ep for ep in received_episodes if ep.id == ep_restored.id)
    assert len(restored_received.transcript_content) >= MIN_DEDUPED_CHARS
    assert restored_received.transcript_content != "Confirmed."
    assert ep_restored.transcript_content.startswith(restored_received.transcript_content)

    # --- P2 #1: dropped-episode status handling must differ by reason ---
    redundant_after = episode_repo.get_by_id(ep_redundant.id)
    tiny_after = episode_repo.get_by_id(ep_tiny_original.id)

    assert redundant_after.status == "digested", (
        "genuinely-redundant episode (dedup ran, established no new "
        "content) must be marked digested -- siblings cover it"
    )
    assert tiny_after.status == "scored", (
        "too-short-original episode (dedup never ran, redundancy never "
        "established) must NOT be marked digested -- it must stay "
        "reconsiderable, not permanently lost"
    )
