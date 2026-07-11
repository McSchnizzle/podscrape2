"""Regression test for the codex-flagged #2856 follow-up: ConfigManager
must treat the DB as authoritative for topics, not just "DB-first with a
JSON safety net."

Before this fix, `_get_database_topics` returned `[]` for BOTH "the query
succeeded and found zero active topics" and "the query raised" -- so
`get_topics()`/`get_all_topics()` (which fell back to config/topics.json
whenever `_get_database_topics` returned a falsy `[]`) couldn't tell them
apart. Disabling the last active DB topic would silently resurrect
config/topics.json's legacy topic set (AI and Technology / Social
Movements and Community Organizing / Psychedelics and Spirituality --
different names and descriptions than whatever the DB currently says),
which is exactly the kind of "topics that exist nowhere in the current DB"
symptom the #2856 investigation went looking for.
"""

import pytest

from src.config.config_manager import ConfigManager
from src.database.models import Topic, TopicRepository


@pytest.fixture
def topic_repo(test_db_manager):
    return TopicRepository(test_db_manager)


def test_zero_active_db_topics_returns_empty_not_json_fallback(topic_repo):
    """DB is reachable and has topics, but none are active -- must return
    [], never fall back to config/topics.json's legacy topic set."""
    topic_repo.upsert_topic(Topic(
        slug="ai-and-technology",
        name="AI and Technology",
        description="some description",
        is_active=False,
    ))

    config_manager = ConfigManager(web_config=None, topic_repo=topic_repo)
    topics = config_manager.get_topics()

    assert topics == []
    topic_names = {t["name"] for t in topics}
    # None of the legacy JSON topic names should ever appear here.
    assert "Social Movements and Community Organizing" not in topic_names
    assert "Psychedelics and Spirituality" not in topic_names


def test_no_topics_at_all_in_db_returns_empty_not_json_fallback(topic_repo):
    """DB is reachable (topic_repo present, query succeeds) but the topics
    table is completely empty -- still authoritative []."""
    config_manager = ConfigManager(web_config=None, topic_repo=topic_repo)

    topics = config_manager.get_topics()
    assert topics == []

    all_topics = config_manager.get_all_topics()
    assert all_topics == []


def test_db_unavailable_falls_back_to_json_topics():
    """When the DB genuinely can't be queried (topic_repo raises), falling
    back to config/topics.json is still the correct, intentional behavior
    -- this pins the OTHER half of the contract so the fix doesn't
    overcorrect into never falling back at all."""

    class BrokenTopicRepo:
        def get_active_topics(self):
            raise RuntimeError("DB connection lost")

        def get_all_topics(self):
            raise RuntimeError("DB connection lost")

    config_manager = ConfigManager(web_config=None, topic_repo=BrokenTopicRepo())

    topics = config_manager.get_topics()
    assert len(topics) > 0
    assert any(t["name"] == "AI and Technology" for t in topics)


def test_no_topic_repo_at_all_falls_back_to_json_topics():
    """No topic_repo wired up (topic_repo=None is explicitly requested,
    not just "query returned nothing") -- also a fall-back case, not an
    authoritative-empty case."""
    config_manager = ConfigManager(web_config=None, topic_repo=None)
    # Force topic_repo to stay None instead of the constructor's normal
    # get_topic_repo() auto-wiring.
    config_manager.topic_repo = None

    topics = config_manager.get_topics()
    assert len(topics) > 0


def test_active_db_topics_present_returns_db_topics_not_json(topic_repo):
    topic_repo.upsert_topic(Topic(
        slug="distinctive-topic",
        name="Distinctive DB Topic",
        description="DB_MARKER_xyz",
        is_active=True,
    ))

    config_manager = ConfigManager(web_config=None, topic_repo=topic_repo)
    topics = config_manager.get_topics()

    assert len(topics) == 1
    assert topics[0]["name"] == "Distinctive DB Topic"
    assert topics[0]["description"] == "DB_MARKER_xyz"
