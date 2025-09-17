"""
Integration tests for SQLAlchemy database models and repositories.
Tests real database operations using pytest fixtures.
"""

import pytest

pytest.importorskip("sqlalchemy", reason="SQLAlchemy is required for database integration tests")

from datetime import datetime, date, timedelta, UTC
from src.database.models import Episode, Feed, Digest


class TestFeedRepository:
    """Test Feed repository operations"""

    def test_create_and_retrieve_feed(self, feed_repo, sample_feed):
        """Test creating and retrieving a feed"""
        # Create feed
        feed_id = feed_repo.create(sample_feed)
        assert feed_id is not None
        assert isinstance(feed_id, int)

        # Retrieve feed by URL
        retrieved_feed = feed_repo.get_by_url(sample_feed.feed_url)
        assert retrieved_feed is not None
        assert retrieved_feed.id == feed_id
        assert retrieved_feed.title == sample_feed.title
        assert retrieved_feed.active == sample_feed.active

    def test_get_active_feeds(self, feed_repo):
        """Test retrieving active feeds"""
        # Create active and inactive feeds
        active_feed = Feed(
            feed_url="https://active.example.com/feed.xml",
            title="Active Feed",
            active=True
        )
        inactive_feed = Feed(
            feed_url="https://inactive.example.com/feed.xml",
            title="Inactive Feed",
            active=False
        )

        feed_repo.create(active_feed)
        feed_repo.create(inactive_feed)

        # Get active feeds
        active_feeds = feed_repo.get_active_feeds()
        assert len(active_feeds) == 1
        assert active_feeds[0].title == "Active Feed"

    def test_update_feed_timestamps(self, feed_repo, sample_feed):
        """Test updating feed timestamps"""
        feed_id = feed_repo.create(sample_feed)

        now = datetime.now(UTC)
        last_episode = now - timedelta(hours=2)

        feed_repo.update_last_checked(feed_id, now, last_episode)

        retrieved_feed = feed_repo.get_by_url(sample_feed.feed_url)
        assert retrieved_feed.last_checked is not None
        assert retrieved_feed.last_episode_date is not None

    def test_failure_tracking(self, feed_repo, sample_feed):
        """Test failure count tracking"""
        feed_id = feed_repo.create(sample_feed)

        # Increment failures
        feed_repo.increment_failure(feed_id)
        feed_repo.increment_failure(feed_id)

        retrieved_feed = feed_repo.get_by_url(sample_feed.feed_url)
        assert retrieved_feed.consecutive_failures == 2

        # Reset failures
        feed_repo.reset_failures(feed_id)
        retrieved_feed = feed_repo.get_by_url(sample_feed.feed_url)
        assert retrieved_feed.consecutive_failures == 0


class TestEpisodeRepository:
    """Test Episode repository operations"""

    def test_create_and_retrieve_episode(self, episode_repo, sample_episode):
        """Test creating and retrieving an episode"""
        episode_id = episode_repo.create(sample_episode)
        assert episode_id is not None

        # Retrieve by GUID
        retrieved_episode = episode_repo.get_by_episode_guid(sample_episode.episode_guid)
        assert retrieved_episode is not None
        assert retrieved_episode.id == episode_id
        assert retrieved_episode.title == sample_episode.title

        # Retrieve by ID
        retrieved_by_id = episode_repo.get_by_id(episode_id)
        assert retrieved_by_id is not None
        assert retrieved_by_id.episode_guid == sample_episode.episode_guid

    def test_status_filtering(self, episode_repo):
        """Test filtering episodes by status"""
        # Create episodes with different statuses
        episode1 = Episode(
            episode_guid="pending-1",
            feed_id=1,
            title="Pending Episode",
            published_date=datetime.now(),
            audio_url="https://example.com/1.mp3",
            status='pending'
        )
        episode2 = Episode(
            episode_guid="scored-1",
            feed_id=1,
            title="Scored Episode",
            published_date=datetime.now(),
            audio_url="https://example.com/2.mp3",
            status='scored'
        )

        episode_repo.create(episode1)
        episode_repo.create(episode2)

        # Filter by status
        pending_episodes = episode_repo.get_by_status('pending')
        scored_episodes = episode_repo.get_by_status('scored')

        assert len(pending_episodes) == 1
        assert len(scored_episodes) == 1
        assert pending_episodes[0].title == "Pending Episode"
        assert scored_episodes[0].title == "Scored Episode"

    def test_update_transcript(self, episode_repo, sample_episode):
        """Test updating transcript information"""
        episode_id = episode_repo.create(sample_episode)

        transcript_path = "/tmp/test_transcript.txt"
        word_count = 1500

        episode_repo.update_transcript(sample_episode.episode_guid, transcript_path, word_count)

        updated_episode = episode_repo.get_by_episode_guid(sample_episode.episode_guid)
        assert updated_episode.transcript_path == transcript_path
        assert updated_episode.transcript_word_count == word_count
        assert updated_episode.status == 'transcribed'
        assert updated_episode.transcript_generated_at is not None

    def test_update_scores(self, episode_repo, sample_episode):
        """Test updating AI scores"""
        episode_id = episode_repo.create(sample_episode)

        scores = {
            "AI and Technology": 0.85,
            "Politics": 0.25,
            "Climate": 0.60
        }

        episode_repo.update_scores(sample_episode.episode_guid, scores)

        updated_episode = episode_repo.get_by_episode_guid(sample_episode.episode_guid)
        assert updated_episode.scores == scores
        assert updated_episode.status == 'scored'
        assert updated_episode.scored_at is not None

    def test_scored_episodes_for_topic(self, episode_repo):
        """Test filtering scored episodes by topic and score threshold"""
        # Create episodes with different scores
        episodes_data = [
            ("high-score", {"AI and Technology": 0.90, "Politics": 0.20}),
            ("medium-score", {"AI and Technology": 0.70, "Politics": 0.30}),
            ("low-score", {"AI and Technology": 0.40, "Politics": 0.80}),
        ]

        for guid, scores in episodes_data:
            episode = Episode(
                episode_guid=guid,
                feed_id=1,
                title=f"Episode {guid}",
                published_date=datetime.now(),
                audio_url=f"https://example.com/{guid}.mp3",
                status='scored',
                scores=scores,
                scored_at=datetime.now()
            )
            episode_repo.create(episode)

        # Test filtering by topic and score threshold
        ai_episodes = episode_repo.get_scored_episodes_for_topic("AI and Technology", min_score=0.65)
        politics_episodes = episode_repo.get_scored_episodes_for_topic("Politics", min_score=0.65)

        assert len(ai_episodes) == 2  # high-score and medium-score
        assert len(politics_episodes) == 1  # low-score only

        # Check ordering (highest score first)
        assert ai_episodes[0].episode_guid == "high-score"
        assert ai_episodes[1].episode_guid == "medium-score"

    def test_failure_tracking(self, episode_repo, sample_episode):
        """Test episode failure tracking"""
        episode_id = episode_repo.create(sample_episode)

        # Mark failure
        episode_repo.mark_failure(sample_episode.episode_guid, "Network timeout")

        failed_episode = episode_repo.get_by_episode_guid(sample_episode.episode_guid)
        assert failed_episode.failure_count == 1
        assert failed_episode.failure_reason == "Network timeout"
        assert failed_episode.last_failure_at is not None
        assert failed_episode.status == 'pending'  # Not failed yet (< 3 failures)

        # Mark more failures to trigger failed status
        episode_repo.mark_failure(sample_episode.episode_guid, "Second failure")
        episode_repo.mark_failure(sample_episode.episode_guid, "Third failure")

        failed_episode = episode_repo.get_by_episode_guid(sample_episode.episode_guid)
        assert failed_episode.failure_count == 3
        assert failed_episode.status == 'failed'

    def test_get_recent_episodes(self, episode_repo):
        """Test getting recent episodes"""
        # Create episodes with different dates
        for i in range(5):
            episode = Episode(
                episode_guid=f"recent-{i}",
                feed_id=1,
                title=f"Recent Episode {i}",
                published_date=datetime.now() - timedelta(days=i),
                audio_url=f"https://example.com/recent-{i}.mp3"
            )
            episode_repo.create(episode)

        recent_episodes = episode_repo.get_recent_episodes(limit=3)
        assert len(recent_episodes) == 3

        # Should be ordered by published_date desc (most recent first)
        assert recent_episodes[0].episode_guid == "recent-0"
        assert recent_episodes[1].episode_guid == "recent-1"
        assert recent_episodes[2].episode_guid == "recent-2"


class TestDigestRepository:
    """Test Digest repository operations"""

    def test_create_and_retrieve_digest(self, digest_repo, sample_digest):
        """Test creating and retrieving a digest"""
        digest_id = digest_repo.create(sample_digest)
        assert digest_id is not None

        # Retrieve by ID
        retrieved_digest = digest_repo.get_by_id(digest_id)
        assert retrieved_digest is not None
        assert retrieved_digest.topic == sample_digest.topic
        assert retrieved_digest.digest_date == sample_digest.digest_date

        # Retrieve by topic and date
        retrieved_by_topic_date = digest_repo.get_by_topic_date(
            sample_digest.topic, sample_digest.digest_date
        )
        assert retrieved_by_topic_date is not None
        assert retrieved_by_topic_date.id == digest_id

    def test_get_by_date(self, digest_repo):
        """Test retrieving all digests for a specific date"""
        test_date = date.today()

        # Create multiple digests for the same date
        topics = ["AI and Technology", "Politics", "Climate"]
        for topic in topics:
            digest = Digest(
                topic=topic,
                digest_date=test_date,
                episode_count=2
            )
            digest_repo.create(digest)

        digests = digest_repo.get_by_date(test_date)
        assert len(digests) == 3

        topic_names = {d.topic for d in digests}
        assert topic_names == set(topics)

    def test_update_script(self, digest_repo, sample_digest):
        """Test updating script information"""
        digest_id = digest_repo.create(sample_digest)

        script_path = "/tmp/test_script.md"
        word_count = 750

        digest_repo.update_script(digest_id, script_path, word_count)

        updated_digest = digest_repo.get_by_id(digest_id)
        assert updated_digest.script_path == script_path
        assert updated_digest.script_word_count == word_count

    def test_update_audio(self, digest_repo, sample_digest):
        """Test updating audio information"""
        digest_id = digest_repo.create(sample_digest)

        mp3_path = "/tmp/test_audio.mp3"
        duration = 300
        title = "Test Audio Title"
        summary = "Test audio summary"

        digest_repo.update_audio(digest_id, mp3_path, duration, title, summary)

        updated_digest = digest_repo.get_by_id(digest_id)
        assert updated_digest.mp3_path == mp3_path
        assert updated_digest.mp3_duration_seconds == duration
        assert updated_digest.mp3_title == title
        assert updated_digest.mp3_summary == summary

    def test_update_published(self, digest_repo, sample_digest):
        """Test updating publishing information"""
        digest_id = digest_repo.create(sample_digest)

        github_url = "https://github.com/test/repo/releases/download/test/audio.mp3"

        digest_repo.update_published(digest_id, github_url)

        updated_digest = digest_repo.get_by_id(digest_id)
        assert updated_digest.github_url == github_url
        assert updated_digest.published_at is not None

    def test_get_recent_digests(self, digest_repo):
        """Test getting recent digests for RSS generation"""
        # Create digests with different dates and mp3 paths
        for i in range(7):
            digest = Digest(
                topic=f"Topic {i}",
                digest_date=date.today() - timedelta(days=i),
                episode_count=1,
                mp3_path=f"/tmp/audio_{i}.mp3" if i < 5 else None  # Only some have mp3
            )
            digest_repo.create(digest)

        # Get recent digests (should only return those with mp3_path)
        recent_digests = digest_repo.get_recent_digests(days=7)
        assert len(recent_digests) == 5  # Only those with mp3_path

        # Should be ordered by date desc
        assert recent_digests[0].digest_date == date.today()
        assert recent_digests[1].digest_date == date.today() - timedelta(days=1)


class TestDatabaseIntegration:
    """Integration tests across multiple repositories"""

    def test_complete_episode_workflow(self, feed_repo, episode_repo, digest_repo):
        """Test complete workflow from feed to digest"""
        # 1. Create feed
        feed = Feed(
            feed_url="https://workflow.example.com/feed.xml",
            title="Workflow Test Feed",
            active=True
        )
        feed_id = feed_repo.create(feed)

        # 2. Create episode
        episode = Episode(
            episode_guid="workflow-episode-1",
            feed_id=feed_id,
            title="Workflow Test Episode",
            published_date=datetime.now(),
            audio_url="https://workflow.example.com/audio.mp3",
            status='pending'
        )
        episode_id = episode_repo.create(episode)

        # 3. Update episode through workflow stages
        episode_repo.update_transcript(episode.episode_guid, "/tmp/transcript.txt", 1000)

        scores = {"AI and Technology": 0.85}
        episode_repo.update_scores(episode.episode_guid, scores)

        # 4. Create digest with episode
        digest = Digest(
            topic="AI and Technology",
            digest_date=date.today(),
            episode_ids=[episode_id],
            episode_count=1
        )
        digest_id = digest_repo.create(digest)

        # 5. Update digest with content
        digest_repo.update_script(digest_id, "/tmp/script.md", 500)
        digest_repo.update_audio(digest_id, "/tmp/audio.mp3", 180, "Test Title", "Test Summary")
        digest_repo.update_published(digest_id, "https://github.com/test/repo/audio.mp3")

        # 6. Verify final state
        final_episode = episode_repo.get_by_id(episode_id)
        final_digest = digest_repo.get_by_id(digest_id)

        assert final_episode.status == 'scored'
        assert final_episode.scores == scores
        assert final_digest.mp3_path == "/tmp/audio.mp3"
        assert final_digest.published_at is not None

    def test_database_connection_and_transactions(self, test_db_manager):
        """Test database connectivity and transaction handling"""
        assert test_db_manager.test_connection() is True

        # Test that sessions work
        session = test_db_manager.get_session()
        assert session is not None
        session.close()