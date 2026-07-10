"""Tests for ScriptGenerator's Tier B daily-emphasis injection (watch-themes
daily emphasis, Paul 2026-07-10).

Exercises _build_daily_theme_emphasis / _safe_build_daily_theme_emphasis
directly against the in-memory SQLite test DB, with
scan_episodes_for_daily_emphasis mocked so no real claude -p subprocess
runs (tests/README.md: no network in tests). ScriptGenerator is constructed
via object.__new__ to skip __init__ (which touches OpenAI client, web
config, topic instructions, etc.) since neither method under test reads
`self` state -- both are pure functions of (episodes) / (topic, episodes)
plus the module-level get_database_manager()/scan function.
"""
from __future__ import annotations

import pytest

pytest.importorskip("sqlalchemy", reason="SQLAlchemy is required for database integration tests")

from unittest.mock import patch

from src.database.sqlalchemy_models import WatchTheme
from src.generation import script_generator as sg_mod
from src.generation.script_generator import ScriptGenerator, WATCH_THEME_TOPIC


class _FakeEpisode:
    def __init__(self, ep_id: int, title: str, transcript_content: str):
        self.id = ep_id
        self.title = title
        self.transcript_content = transcript_content


@pytest.fixture
def generator():
    """A ScriptGenerator instance with __init__ skipped (see module docstring)."""
    return object.__new__(ScriptGenerator)


@pytest.fixture
def patched_db(monkeypatch, test_db_manager):
    monkeypatch.setattr(sg_mod, "get_database_manager", lambda: test_db_manager)
    return test_db_manager


def _add_theme(db_manager, *, name, description, scope, active=True):
    with db_manager.get_session() as session:
        session.add(WatchTheme(name=name, description=description, scope=scope, active=active))
        session.commit()


class TestBuildDailyThemeEmphasis:
    def test_no_active_daily_or_both_themes_returns_none(self, generator, patched_db):
        _add_theme(patched_db, name="Weekly only", description="d", scope="weekly")
        episodes = [_FakeEpisode(1, "Ep 1", "transcript")]
        assert generator._build_daily_theme_emphasis(episodes) is None

    def test_inactive_daily_theme_is_ignored(self, generator, patched_db):
        _add_theme(patched_db, name="Inactive daily", description="d", scope="daily", active=False)
        episodes = [_FakeEpisode(1, "Ep 1", "transcript")]
        assert generator._build_daily_theme_emphasis(episodes) is None

    def test_no_episodes_with_transcript_returns_none(self, generator, patched_db):
        _add_theme(patched_db, name="Governance", description="standards bodies", scope="both")
        episodes = [_FakeEpisode(1, "Ep 1", ""), _FakeEpisode(2, "Ep 2", None)]
        assert generator._build_daily_theme_emphasis(episodes) is None

    @patch("src.generation.script_generator.scan_episodes_for_daily_emphasis")
    def test_matches_populate_emphasis_block(self, mock_scan, generator, patched_db):
        _add_theme(
            patched_db, name="AI standards, governance, and industry consortiums",
            description="standards-body and consortium coverage", scope="both",
        )
        mock_scan.return_value = [
            {"episode_title": "Ep 1", "excerpt": "FIDO Alliance ships new spec",
             "note": "consortium spec release"},
        ]
        episodes = [_FakeEpisode(1, "Ep 1", "some transcript content")]

        result = generator._build_daily_theme_emphasis(episodes)

        assert result is not None
        assert "AI standards, governance, and industry consortiums" in result
        assert "FIDO Alliance ships new spec" in result
        assert "WATCH THEME EMPHASIS" in result
        mock_scan.assert_called_once()

    @patch("src.generation.script_generator.scan_episodes_for_daily_emphasis")
    def test_no_matches_returns_none_not_empty_block(self, mock_scan, generator, patched_db):
        _add_theme(patched_db, name="Governance", description="d", scope="daily")
        mock_scan.return_value = []
        episodes = [_FakeEpisode(1, "Ep 1", "transcript")]

        assert generator._build_daily_theme_emphasis(episodes) is None

    @patch("src.generation.script_generator.scan_episodes_for_daily_emphasis")
    def test_one_scan_call_per_active_theme(self, mock_scan, generator, patched_db):
        _add_theme(patched_db, name="Theme A", description="d", scope="daily")
        _add_theme(patched_db, name="Theme B", description="d", scope="both")
        mock_scan.return_value = []
        episodes = [_FakeEpisode(i, f"Ep {i}", "transcript") for i in range(5)]

        generator._build_daily_theme_emphasis(episodes)

        assert mock_scan.call_count == 2  # bounded by theme count, not episode count


class TestSafeBuildDailyThemeEmphasisFailOpen:
    def test_non_watch_topic_short_circuits_without_db_call(self, generator, patched_db):
        # No theme rows needed -- topic gating should skip the DB entirely.
        episodes = [_FakeEpisode(1, "Ep 1", "transcript")]
        result = generator._safe_build_daily_theme_emphasis("Politics", episodes)
        assert result is None

    @patch("src.generation.script_generator.scan_episodes_for_daily_emphasis")
    def test_matching_topic_with_matches_returns_block(self, mock_scan, generator, patched_db):
        _add_theme(patched_db, name="Governance", description="d", scope="daily")
        mock_scan.return_value = [{"episode_title": "Ep 1", "excerpt": "quoted material", "note": ""}]
        episodes = [_FakeEpisode(1, "Ep 1", "transcript")]

        result = generator._safe_build_daily_theme_emphasis(WATCH_THEME_TOPIC, episodes)

        assert result is not None
        assert "quoted material" in result

    def test_scan_error_fails_open_generation_proceeds(self, generator, patched_db, monkeypatch):
        """The nightly digest must never fail because of this feature."""
        def _boom(self, episodes):
            raise RuntimeError("simulated DB outage")

        monkeypatch.setattr(ScriptGenerator, "_build_daily_theme_emphasis", _boom)
        episodes = [_FakeEpisode(1, "Ep 1", "transcript")]

        result = generator._safe_build_daily_theme_emphasis(WATCH_THEME_TOPIC, episodes)

        assert result is None  # did not raise -- caller can proceed to generate_script


class TestGenerateScriptThreadsThemeEmphasis:
    """Confirms theme_emphasis reaches the actual prompt text sent to the model,
    for BOTH the claude -p (skill-based) path and the fallback hardcoded path."""

    def test_dialogue_prompt_includes_emphasis_when_skill_file_present(self, generator):
        prompt = generator._build_claude_p_dialogue_prompt(
            system_prompt="fallback prompt text",
            topic="AI and Technology",
            topic_instructions="cover AI news",
            story_arc_context="",
            repetition_instructions="",
            digest_date=__import__("datetime").date(2026, 7, 10),
            speaker_1_name="Host",
            speaker_2_name="Analyst",
            num_episodes=3,
            theme_emphasis="## WATCH THEME EMPHASIS\n\nquoted material here",
        )
        assert "WATCH THEME EMPHASIS" in prompt
        assert "quoted material here" in prompt

    def test_dialogue_prompt_omits_emphasis_when_none(self, generator):
        prompt = generator._build_claude_p_dialogue_prompt(
            system_prompt="fallback prompt text",
            topic="AI and Technology",
            topic_instructions="cover AI news",
            story_arc_context="",
            repetition_instructions="",
            digest_date=__import__("datetime").date(2026, 7, 10),
            speaker_1_name="Host",
            speaker_2_name="Analyst",
            num_episodes=3,
            theme_emphasis=None,
        )
        assert "WATCH THEME EMPHASIS" not in prompt
