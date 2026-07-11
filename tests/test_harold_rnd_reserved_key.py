"""kanban #2855 Tier 1: the _harold_rnd reserved key must never leak into
digest topic selection, the podcast-relevance gate, or (until the R&D miner
has had a chance to read it) retention's age-based episode deletion.

`_harold_rnd` lives inside `episodes.scores`, the SAME JSON dict real topic
scores live in (per the kanban #2855 design), so every consumer that
iterates that dict is a potential landmine. This file pins the contract for
each consumer found during the #2856/#2855 review: exact-key lookups are
safe by construction (an underscore-prefixed key can never equal a real
topic name), but blind iteration (`.values()`, `any(...)`, `max(...)`) is
NOT safe unless it explicitly excludes reserved keys.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from src.database.models import Episode, EpisodeRepository, Feed, FeedRepository
from src.scoring.harold_rnd import HAROLD_RND_SCORE_KEY, is_reserved_score_key
from src.publishing.retention_manager import RetentionManager


# ---------------------------------------------------------------------------
# is_reserved_score_key / is_podcast_relevant (scripts/run_audio.py)
# ---------------------------------------------------------------------------

def test_is_reserved_score_key():
    assert is_reserved_score_key(HAROLD_RND_SCORE_KEY) is True
    assert is_reserved_score_key("_anything_underscore_prefixed") is True
    assert is_reserved_score_key("AI and Technology") is False
    assert is_reserved_score_key("") is False


def test_is_podcast_relevant_ignores_reserved_key_even_when_it_alone_clears_threshold():
    from run_audio import is_podcast_relevant

    scores = {"AI and Technology": 0.2, HAROLD_RND_SCORE_KEY: 0.95}
    assert is_podcast_relevant(scores, threshold=0.65) is False


def test_is_podcast_relevant_true_when_a_real_topic_clears_threshold():
    from run_audio import is_podcast_relevant

    scores = {"AI and Technology": 0.9, HAROLD_RND_SCORE_KEY: 0.1}
    assert is_podcast_relevant(scores, threshold=0.65) is True


def test_is_podcast_relevant_false_for_empty_scores():
    from run_audio import is_podcast_relevant

    assert is_podcast_relevant({}, threshold=0.65) is False


# ---------------------------------------------------------------------------
# Digest topic selection (models.py:546-594, get_scored_episodes_for_topic)
# ---------------------------------------------------------------------------

@pytest.fixture
def feed_repo(test_db_manager):
    return FeedRepository(test_db_manager)


@pytest.fixture
def episode_repo(test_db_manager):
    return EpisodeRepository(test_db_manager)


@pytest.fixture
def seeded_feed_id(feed_repo):
    return feed_repo.create(Feed(
        feed_url="https://example.com/feed.xml",
        title="Test Feed",
        description="",
        active=True,
    ))


def test_digest_selection_never_selects_reserved_key_as_a_topic(episode_repo, seeded_feed_id):
    """An episode with a LOW real topic score but a HIGH _harold_rnd score
    must never be selected for the "AI and Technology" digest -- and
    querying "_harold_rnd" itself as a topic name (which no legitimate
    caller does, since topic names always come from the topics table) must
    return nothing, proving there is no code path where the reserved key
    could be mistaken for a topic."""
    episode_repo.create(Episode(
        episode_guid="ep-reserved-key-test",
        feed_id=seeded_feed_id,
        title="Low relevance, high R&D applicability",
        published_date=datetime.now() - timedelta(days=1),
        audio_url="https://example.com/audio.mp3",
        transcript_content="transcript",
        scores={"AI and Technology": 0.2, HAROLD_RND_SCORE_KEY: 0.95},
        status="not_relevant",
    ))

    qualifying = episode_repo.get_scored_episodes_for_topic(
        "AI and Technology", min_score=0.65, exclude_digested=False
    )
    assert qualifying == []

    qualifying_via_reserved_key = episode_repo.get_scored_episodes_for_topic(
        HAROLD_RND_SCORE_KEY, min_score=0.0, exclude_digested=False
    )
    assert qualifying_via_reserved_key == []


def test_digest_selection_still_selects_real_high_scoring_topic(episode_repo, seeded_feed_id):
    episode_repo.create(Episode(
        episode_guid="ep-real-topic-test",
        feed_id=seeded_feed_id,
        title="Genuinely relevant episode",
        published_date=datetime.now() - timedelta(days=1),
        audio_url="https://example.com/audio.mp3",
        transcript_content="transcript",
        scores={"AI and Technology": 0.9, HAROLD_RND_SCORE_KEY: 0.1},
        status="scored",
    ))

    qualifying = episode_repo.get_scored_episodes_for_topic(
        "AI and Technology", min_score=0.65, exclude_digested=True
    )
    assert len(qualifying) == 1
    assert qualifying[0].episode_guid == "ep-real-topic-test"


# ---------------------------------------------------------------------------
# Retention exemption (src/publishing/retention_manager.py)
# ---------------------------------------------------------------------------

def test_retention_keeps_high_harold_rnd_episode_past_cutoff(test_db_manager, episode_repo, seeded_feed_id):
    old_date = datetime.now() - timedelta(days=400)  # far past any default retention window

    episode_repo.create(Episode(
        episode_guid="ep-exempt-old",
        feed_id=seeded_feed_id,
        title="Old but high R&D applicability",
        published_date=old_date,
        audio_url="https://example.com/audio.mp3",
        transcript_path="ep-exempt-old.txt",
        transcript_content="keep me",
        scores={"AI and Technology": 0.1, HAROLD_RND_SCORE_KEY: 0.85},
        status="not_relevant",
    ))
    episode_repo.create(Episode(
        episode_guid="ep-not-exempt-old",
        feed_id=seeded_feed_id,
        title="Old and low R&D applicability",
        published_date=old_date,
        audio_url="https://example.com/audio2.mp3",
        transcript_path="ep-not-exempt-old.txt",
        transcript_content="delete me",
        scores={"AI and Technology": 0.1, HAROLD_RND_SCORE_KEY: 0.1},
        status="not_relevant",
    ))

    manager = RetentionManager(github_publisher=None, database_manager=test_db_manager)
    stats = manager._cleanup_database_records(dry_run=False)

    remaining_guids = {
        ep.episode_guid for ep in episode_repo.get_by_status_list(["not_relevant", "scored"])
    }
    assert "ep-exempt-old" in remaining_guids
    assert "ep-not-exempt-old" not in remaining_guids
    assert stats.episodes_deleted == 1


def test_retention_dry_run_counts_exclude_exempt_episode(test_db_manager, episode_repo, seeded_feed_id):
    old_date = datetime.now() - timedelta(days=400)

    episode_repo.create(Episode(
        episode_guid="ep-exempt-dry-run",
        feed_id=seeded_feed_id,
        title="Old but high R&D applicability",
        published_date=old_date,
        audio_url="https://example.com/audio.mp3",
        transcript_content="keep me",
        scores={"AI and Technology": 0.1, HAROLD_RND_SCORE_KEY: 0.9},
        status="not_relevant",
    ))

    manager = RetentionManager(github_publisher=None, database_manager=test_db_manager)
    stats = manager._cleanup_database_records(dry_run=True)

    assert stats.episodes_deleted == 0
