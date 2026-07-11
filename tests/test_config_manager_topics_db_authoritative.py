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
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.config.config_manager import ConfigManager
from src.database.models import DatabaseManager, Topic, TopicRepository
from src.database.sqlalchemy_models import Base, Topic as TopicModel


@pytest.fixture
def topic_repo(test_db_manager):
    return TopicRepository(test_db_manager)


@pytest.fixture
def db_manager_without_topics_table():
    """A real DatabaseManager whose engine has every table EXCEPT
    `topics` -- reproduces the actual ProgrammingError TopicRepository
    hits when the table is missing/unavailable (migrations not yet run,
    schema drift, etc.), as opposed to a fake repo that raises directly."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TopicModel.__table__.drop(engine)

    db_manager = DatabaseManager()
    db_manager.engine = engine
    db_manager.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return db_manager


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


def test_missing_topics_table_falls_back_to_json_with_real_repo(db_manager_without_topics_table):
    """The regression this fix actually targets: TopicRepository swallows
    ProgrammingError (missing table) into [] for its OTHER callers by
    design, but ConfigManager must not receive that [] as if it were a
    genuine "zero active topics" result. Uses the REAL TopicRepository
    against a DB engine missing the topics table (not a fake repo that
    raises directly) -- a fake repo can't reproduce TopicRepository's own
    except-ProgrammingError-and-swallow behavior, which is exactly the
    layer this test needs to exercise."""
    topic_repo = TopicRepository(db_manager_without_topics_table)

    # Confirm the repo itself still swallows-and-returns-[] by default,
    # matching its other (non-ConfigManager) callers unchanged -- e.g.
    # src/audio/audio_generator.py and
    # scripts/apply_ai_tech_instructions_v5_engineering_depth.py all call
    # get_all_topics()/get_active_topics() with no arguments and must keep
    # seeing [] rather than an exception.
    assert topic_repo.get_active_topics() == []
    assert topic_repo.get_all_topics() == []

    config_manager = ConfigManager(web_config=None, topic_repo=topic_repo)
    topics = config_manager.get_topics()

    assert len(topics) > 0
    assert any(t["name"] == "AI and Technology" for t in topics)


def test_is_missing_table_error_does_not_match_unrelated_operational_errors():
    """Precision check on the dialect-portable missing-table detector: an
    OperationalError from something else entirely (lock timeout, etc.)
    must NOT be treated as "table missing" and silently swallowed."""
    from src.database.models import _is_missing_table_error

    assert _is_missing_table_error(Exception("no such table: topics")) is True
    assert _is_missing_table_error(Exception('relation "topics" does not exist')) is True
    assert _is_missing_table_error(Exception("database is locked")) is False
    assert _is_missing_table_error(Exception("connection refused")) is False


def test_unrelated_operational_error_still_propagates_through_safe_query_topics(test_db_manager):
    """An unrelated OperationalError (not a missing-table message, e.g. a
    lock timeout) must propagate out of _safe_query_topics, not be
    swallowed into [] -- confirms the fix is scoped to missing-table
    detection and didn't become a blanket except OperationalError."""
    import unittest.mock

    topic_repo = TopicRepository(test_db_manager)

    fake_session = unittest.mock.MagicMock()
    fake_session.__enter__ = unittest.mock.Mock(return_value=fake_session)
    fake_session.__exit__ = unittest.mock.Mock(return_value=False)
    fake_session.query.return_value.filter.return_value.order_by.return_value.all.side_effect = \
        OperationalError("SELECT ...", None, Exception("database is locked"))
    fake_session.query.return_value.order_by.return_value.all.side_effect = \
        OperationalError("SELECT ...", None, Exception("database is locked"))

    with unittest.mock.patch.object(test_db_manager, "get_session", return_value=fake_session):
        with pytest.raises(OperationalError):
            topic_repo.get_active_topics()


def test_db_unavailable_falls_back_to_json_topics():
    """When the DB genuinely can't be queried (topic_repo raises), falling
    back to config/topics.json is still the correct, intentional behavior
    -- this pins the OTHER half of the contract so the fix doesn't
    overcorrect into never falling back at all."""

    class BrokenTopicRepo:
        def get_active_topics(self, raise_on_unavailable: bool = False):
            raise RuntimeError("DB connection lost")

        def get_all_topics(self, raise_on_unavailable: bool = False):
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
