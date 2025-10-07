import os
import logging
from datetime import datetime

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from scripts.run_audio import AudioProcessor_Runner  # noqa: E402


class DummyEpisode:
    def __init__(self, guid: str, title: str, transcript: str = "Sample transcript"):
        self.episode_guid = guid
        self.title = title
        self.transcript_content = transcript
        self.published_date = datetime.now()
        self.audio_url = "http://example.com/audio.mp3"
        self.duration_seconds = 123
        self.description = ""
        self.feed_id = 1


class DummyEpisodeRepo:
    def __init__(self, episodes):
        self._episodes = {ep.episode_guid: ep for ep in episodes}
        self.status_updates = []
        self.scores_updated = []

    def get_by_episode_guid(self, guid):
        return self._episodes.get(guid)

    def update_scores(self, guid, scores):
        self.scores_updated.append((guid, scores))

    def update_status(self, guid, status):
        self.status_updates.append((guid, status))

    def get_by_status(self, status):
        if status != 'pending':
            return []
        return list(self._episodes.values())


class FailingScorer:
    def __init__(self, error: Exception):
        self._error = error

    def score_transcript(self, transcript, episode_guid):
        raise self._error


def _build_runner(episode_repo, scorer):
    runner = object.__new__(AudioProcessor_Runner)
    runner.logger = logging.getLogger("test_audio_runner")
    runner.logger.setLevel(logging.CRITICAL)
    runner.episode_repo = episode_repo
    runner.content_scorer = scorer
    runner.score_threshold = 0.5
    runner.dry_run = False
    return runner


def test_score_episode_immediately_reports_failure_on_exception():
    episode = DummyEpisode("guid-1", "Episode One")
    repo = DummyEpisodeRepo([episode])
    scorer = FailingScorer(RuntimeError("boom"))
    runner = _build_runner(repo, scorer)

    outcome = runner._score_episode_immediately(episode.episode_guid)

    assert outcome["success"] is False
    assert "boom" in outcome["error"]
    assert repo.scores_updated == []


def test_sequential_processing_marks_failure_when_scoring_fails():
    episode = DummyEpisode("guid-2", "Episode Two")
    repo = DummyEpisodeRepo([episode])
    scorer = FailingScorer(RuntimeError("scoring failed"))
    runner = _build_runner(repo, scorer)

    def fake_audio_process(data):
        return {
            "success": True,
            "guid": data["guid"],
            "title": data["title"],
            "status": "transcribed",
            "transcript_words": 10,
        }

    runner._process_episode_audio = fake_audio_process

    result = runner._process_episodes_sequential(max_relevant_episodes=1)

    assert result["failed"], "Expected failed episodes to be reported"
    assert result["failed"][0]["guid"] == "guid-2"
    assert result["not_relevant_episodes_found"] == 0
    assert any(status == "transcribed" for _, status in repo.status_updates)
    assert not any(status == "not_relevant" for _, status in repo.status_updates)
