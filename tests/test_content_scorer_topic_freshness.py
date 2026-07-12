"""Regression tests for kanban #2856 (scorer source-of-truth root-cause fix).

Root cause: ContentScorer.__init__ loaded topics from the DB ONCE and cached
them in self.topics for the lifetime of the process. A long-lived
run_audio.py process (up to 2h, the podcast-audio cron's timeout) could
therefore score episodes against stale topic text -- wrong description,
wrong active/inactive set -- for as long as it ran after a Web UI edit.
These tests pin: (1) the built prompt reflects the CURRENT DB row verbatim,
(2) a mid-lifetime topic edit is picked up by the next score_transcript()
call, (3) retired (inactive) topics never appear in the prompt, and (4) the
claude -p path is the only live path -- there is no OpenAI client to fall
back to.
"""

import json
from pathlib import Path

import pytest

from src.config.config_manager import ConfigManager
from src.database.models import Topic, TopicRepository
from src.scoring.content_scorer import ContentScorer, SCORING_PROVIDER


@pytest.fixture
def topic_repo(test_db_manager):
    return TopicRepository(test_db_manager)


@pytest.fixture
def scorer(test_db_manager, topic_repo):
    config_manager = ConfigManager(web_config=None, topic_repo=topic_repo)
    return ContentScorer(config_manager=config_manager)


def _seed_topic(topic_repo, name, description, active=True, slug=None):
    return topic_repo.upsert_topic(Topic(
        slug=slug or name.lower().replace(" ", "-"),
        name=name,
        description=description,
        is_active=active,
    ))


def test_prompt_reflects_active_db_topic_description_verbatim(scorer, topic_repo):
    distinctive_text = "UNIQUE_MARKER_governance_and_standards_bodies_xyz123"
    _seed_topic(topic_repo, "AI and Technology", distinctive_text)

    scorer.refresh_topics()
    prompt = scorer._build_claude_p_scoring_prompt("some transcript", scorer.topics)

    assert distinctive_text in prompt


def test_retired_topic_excluded_from_prompt_and_topics_list(scorer, topic_repo):
    _seed_topic(topic_repo, "AI and Technology", "active topic description")
    _seed_topic(topic_repo, "Retired Topic", "RETIRED_MARKER_should_never_appear", active=False)

    scorer.refresh_topics()
    topic_names = {t["name"] for t in scorer.topics}

    assert "AI and Technology" in topic_names
    assert "Retired Topic" not in topic_names

    prompt = scorer._build_claude_p_scoring_prompt("some transcript", scorer.topics)
    assert "RETIRED_MARKER_should_never_appear" not in prompt


def test_mid_lifetime_topic_edit_is_picked_up_by_next_score_call(scorer, topic_repo, monkeypatch):
    """Simulates the exact production bug: one long-lived ContentScorer,
    a topic edited via the Web UI between two score_transcript() calls."""
    topic = _seed_topic(topic_repo, "AI and Technology", "original description v1")

    captured_prompts = []

    def fake_call_claude_p(prompt, timeout=300):
        captured_prompts.append(prompt)
        return '{"AI and Technology": 0.5}'

    monkeypatch.setattr(ContentScorer, "_call_claude_p", staticmethod(fake_call_claude_p))

    result_1 = scorer.score_transcript("transcript one", episode_id="ep1")
    assert result_1.success
    assert "original description v1" in captured_prompts[0]

    # Simulate a Web UI edit landing mid-process, exactly like the
    # governance/standards vocabulary added to the live "AI and Technology"
    # row on 2026-07-10.
    topic.description = "EDITED_description_v2_governance_standards"
    topic_repo.upsert_topic(topic)

    result_2 = scorer.score_transcript("transcript two", episode_id="ep2")
    assert result_2.success
    assert "EDITED_description_v2_governance_standards" in captured_prompts[1]
    assert "original description v1" not in captured_prompts[1]


def test_content_scorer_has_no_openai_client(scorer):
    """Pins the SCORING_PROVIDER contract: claude -p is the only live path.
    The legacy _create_scoring_prompt/_create_json_schema methods reference
    `self.client`, which must never exist -- if it did, that dead code
    would silently become reachable again."""
    assert SCORING_PROVIDER == "claude-p"
    assert not hasattr(scorer, "client")


def test_harold_applicability_parsed_and_kept_out_of_scores_dict(scorer, topic_repo, monkeypatch):
    _seed_topic(topic_repo, "AI and Technology", "some description")

    def fake_call_claude_p(prompt, timeout=300):
        return '{"AI and Technology": 0.4, "harold_applicability": 0.85}'

    monkeypatch.setattr(ContentScorer, "_call_claude_p", staticmethod(fake_call_claude_p))

    result = scorer.score_transcript("transcript", episode_id="ep1")

    assert result.success
    assert result.harold_applicability == pytest.approx(0.85)
    assert "harold_applicability" not in result.scores
    assert result.scores == {"AI and Technology": 0.4}


def test_harold_applicability_missing_is_none_and_scoring_still_succeeds(scorer, topic_repo, monkeypatch):
    _seed_topic(topic_repo, "AI and Technology", "some description")

    def fake_call_claude_p(prompt, timeout=300):
        return '{"AI and Technology": 0.4}'

    monkeypatch.setattr(ContentScorer, "_call_claude_p", staticmethod(fake_call_claude_p))

    result = scorer.score_transcript("transcript", episode_id="ep1")

    assert result.success
    assert result.harold_applicability is None


def _legacy_json_topics(scorer):
    """The exact legacy topic set baked into config/topics.json -- the
    'phantom' source #2856 guards against. Read from the same file the JSON
    fallback would load (scorer.config_manager._topics_config_path) so this
    test tracks the real on-disk artifact instead of a hardcoded copy that
    could silently drift."""
    path = Path(scorer.config_manager._topics_config_path)
    data = json.loads(path.read_text())
    return data.get("topics", [])


def test_scoring_prompt_sources_topics_only_from_db_never_phantom_json(scorer, topic_repo):
    """End-to-end anti-phantom proof (kanban #2856).

    The bug #2856 chased was episode-scoring prompts carrying topic
    definitions that matched NO current DB artifact -- the legacy
    config/topics.json topic set (AI and Technology / Social Movements and
    Community Organizing / Psychedelics and Spirituality) leaking into
    scoring instead of the live `topics` table, so topic/vocabulary edits
    never reached selection.

    This pins the guarantee at the prompt-build layer: seed a DB topic set
    deliberately DISJOINT from config/topics.json, build the prompt exactly
    the way score_transcript() does (refresh_topics() -> DB-authoritative
    ConfigManager.get_topics()), and assert the prompt contains ONLY the
    live DB topic and NONE of the legacy JSON topics. Any legacy name or
    description in the prompt would prove the scorer fell back to (or
    hardcoded) the phantom source instead of the DB."""
    legacy = _legacy_json_topics(scorer)
    legacy_names = {t["name"] for t in legacy}
    legacy_descs = {t["description"] for t in legacy if t.get("description")}
    # Guard the fixture itself: config/topics.json really is the multi-topic
    # legacy set this test is protecting against.
    assert len(legacy_names) >= 2

    # DB topic set chosen to collide with NONE of the legacy JSON names.
    db_name = "Quantum Networking DB_ONLY_TOPIC"
    db_desc = "DB_ONLY_DESCRIPTION_quantum_repeaters_entanglement_swapping_9f3a"
    assert db_name not in legacy_names
    _seed_topic(topic_repo, db_name, db_desc)

    # Build the prompt via the exact path score_transcript() uses.
    scorer.refresh_topics()
    prompt = scorer._build_claude_p_scoring_prompt("transcript body", scorer.topics)

    # 1. The live DB topic reaches the prompt verbatim (name + description).
    assert db_name in prompt
    assert db_desc in prompt

    # 2. Isolate the actual "## Topics to Score" section -- the only place
    #    topic DEFINITIONS render (one "- name: description" line each).
    #    Checking the whole prompt would false-positive on incidental
    #    phrases (e.g. the hardcoded R&D rubric text mentions "AI and
    #    Technology" as prose), so scope the assertion to the topic block.
    topics_section = prompt.split("## Topics to Score", 1)[1]
    topics_section = topics_section.split("## Additional Rating", 1)[0]
    assert f"- {db_name}: {db_desc}" in topics_section

    # NONE of config/topics.json's legacy topics appear as topic definitions.
    for name in legacy_names:
        assert (
            f"- {name}:" not in topics_section
        ), f"legacy JSON topic definition leaked into scoring prompt: {name!r}"
    # Legacy descriptions are long and distinctive -- their presence anywhere
    # in the prompt would be unambiguous proof of a phantom-source fall-back.
    for desc in legacy_descs:
        assert desc not in prompt, f"legacy JSON topic description leaked into scoring prompt: {desc!r}"

    # 3. The topics the scorer will score against came from the DB path, not
    #    the JSON fallback: _topic_to_config_dict stamps source="database",
    #    which config/topics.json topics never carry.
    assert {t["name"] for t in scorer.topics} == {db_name}
    assert all(t.get("source") == "database" for t in scorer.topics)


def test_db_topic_vocabulary_change_reaches_freshly_built_prompt(scorer, topic_repo):
    """Complements the mid-lifetime score_transcript() test: proves that a
    DB topic-vocabulary EDIT reaches the prompt the scorer builds, and that
    the superseded vocabulary is gone -- i.e. topic/vocabulary changes in
    the canonical `topics` table actually reach the scoring prompt (kanban
    #2856 goal), verified directly at the _build_claude_p_scoring_prompt
    layer rather than only through a mocked full scoring call."""
    topic = _seed_topic(
        topic_repo, "AI and Technology", "vocabulary_v1_machine_learning_only"
    )

    scorer.refresh_topics()
    prompt_v1 = scorer._build_claude_p_scoring_prompt("t", scorer.topics)
    assert "vocabulary_v1_machine_learning_only" in prompt_v1

    # Simulate a Web UI vocabulary edit to the canonical DB row.
    topic.description = "vocabulary_v2_governance_standards_bodies_agents"
    topic_repo.upsert_topic(topic)

    scorer.refresh_topics()
    prompt_v2 = scorer._build_claude_p_scoring_prompt("t", scorer.topics)
    assert "vocabulary_v2_governance_standards_bodies_agents" in prompt_v2
    assert "vocabulary_v1_machine_learning_only" not in prompt_v2
