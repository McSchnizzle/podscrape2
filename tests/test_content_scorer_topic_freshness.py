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
