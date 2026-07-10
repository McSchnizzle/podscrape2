"""Tests for src/watch/theme_scan.py (watch-themes daily emphasis, Paul 2026-07-10).

Covers both entry points -- scan_episode_for_theme (weekly, one episode per
call) and scan_episodes_for_daily_emphasis (daily, batched across many
episodes in one call) -- with the claude -p subprocess call mocked out per
tests/README.md conventions (no network, no real subprocess).
"""
from __future__ import annotations

import json
import subprocess
from unittest.mock import patch

from src.watch import theme_scan


class _FakeEpisode:
    def __init__(self, title: str, transcript_content: str):
        self.title = title
        self.transcript_content = transcript_content


class TestScanEpisodeForTheme:
    """Weekly path: one episode x one theme per claude -p call."""

    @patch("src.watch.theme_scan._call_claude_p")
    def test_returns_matches_on_valid_json(self, mock_call):
        mock_call.return_value = json.dumps([
            {"excerpt": "AI stocks surged today", "note": "matches theme"},
        ])
        matches = theme_scan.scan_episode_for_theme(
            transcript="some transcript text",
            theme_name="AI stocks",
            theme_description="AI's effect on stock prices",
            episode_title="Episode 1",
        )
        assert len(matches) == 1
        assert matches[0]["excerpt"] == "AI stocks surged today"
        mock_call.assert_called_once()

    @patch("src.watch.theme_scan._call_claude_p")
    def test_empty_array_means_no_matches(self, mock_call):
        mock_call.return_value = "[]"
        matches = theme_scan.scan_episode_for_theme(
            "transcript", "theme", "description", "Episode 1",
        )
        assert matches == []

    @patch("src.watch.theme_scan._call_claude_p")
    def test_timeout_fails_open_to_empty_list(self, mock_call):
        mock_call.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=300)
        matches = theme_scan.scan_episode_for_theme(
            "transcript", "theme", "description", "Episode 1",
        )
        assert matches == []

    @patch("src.watch.theme_scan._call_claude_p")
    def test_non_json_response_fails_open_to_empty_list(self, mock_call):
        mock_call.return_value = "not json at all"
        matches = theme_scan.scan_episode_for_theme(
            "transcript", "theme", "description", "Episode 1",
        )
        assert matches == []

    @patch("src.watch.theme_scan._call_claude_p")
    def test_subprocess_error_fails_open_to_empty_list(self, mock_call):
        mock_call.side_effect = RuntimeError("claude -p failed (1): boom")
        matches = theme_scan.scan_episode_for_theme(
            "transcript", "theme", "description", "Episode 1",
        )
        assert matches == []


class TestScanEpisodesForDailyEmphasis:
    """Daily path: many episodes x one theme, ONE batched claude -p call."""

    @patch("src.watch.theme_scan._call_claude_p")
    def test_one_call_regardless_of_episode_count(self, mock_call):
        mock_call.return_value = "[]"
        episodes = [_FakeEpisode(f"Episode {i}", f"transcript {i}") for i in range(9)]
        theme_scan.scan_episodes_for_daily_emphasis(episodes, "Theme", "Description")
        assert mock_call.call_count == 1

    @patch("src.watch.theme_scan._call_claude_p")
    def test_returns_matches_with_episode_title(self, mock_call):
        mock_call.return_value = json.dumps([
            {"episode_title": "Episode 2", "excerpt": "standards consortium news",
             "note": "matches governance theme"},
        ])
        episodes = [_FakeEpisode("Episode 1", "x"), _FakeEpisode("Episode 2", "y")]
        matches = theme_scan.scan_episodes_for_daily_emphasis(episodes, "Theme", "Description")
        assert len(matches) == 1
        assert matches[0]["episode_title"] == "Episode 2"

    @patch("src.watch.theme_scan._call_claude_p")
    def test_no_matches_returns_empty_list(self, mock_call):
        mock_call.return_value = "[]"
        episodes = [_FakeEpisode("Episode 1", "x")]
        matches = theme_scan.scan_episodes_for_daily_emphasis(episodes, "Theme", "Description")
        assert matches == []

    def test_no_usable_episodes_returns_empty_without_calling_claude(self):
        with patch("src.watch.theme_scan._call_claude_p") as mock_call:
            episodes = [_FakeEpisode("Episode 1", ""), _FakeEpisode("Episode 2", None)]
            matches = theme_scan.scan_episodes_for_daily_emphasis(episodes, "Theme", "Description")
            assert matches == []
            mock_call.assert_not_called()

    @patch("src.watch.theme_scan._call_claude_p")
    def test_timeout_fails_open(self, mock_call):
        mock_call.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=300)
        episodes = [_FakeEpisode("Episode 1", "x")]
        matches = theme_scan.scan_episodes_for_daily_emphasis(episodes, "Theme", "Description")
        assert matches == []

    @patch("src.watch.theme_scan._call_claude_p")
    def test_generic_error_fails_open(self, mock_call):
        mock_call.side_effect = RuntimeError("claude -p failed (1): boom")
        episodes = [_FakeEpisode("Episode 1", "x")]
        matches = theme_scan.scan_episodes_for_daily_emphasis(episodes, "Theme", "Description")
        assert matches == []

    @patch("src.watch.theme_scan._call_claude_p")
    def test_transcripts_are_trimmed_per_episode(self, mock_call):
        mock_call.return_value = "[]"
        long_transcript = "x" * 20_000
        episodes = [_FakeEpisode("Episode 1", long_transcript)]
        theme_scan.scan_episodes_for_daily_emphasis(
            episodes, "Theme", "Description", max_chars_per_episode=100,
        )
        sent_prompt = mock_call.call_args[0][1]  # user_prompt positional arg
        assert "x" * 101 not in sent_prompt
        assert "x" * 100 in sent_prompt
