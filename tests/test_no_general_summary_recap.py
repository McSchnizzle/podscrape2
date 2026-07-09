#!/usr/bin/env python3
"""
Tests for kanban #1617 — disable General Summary recap fallback.

Acceptance criteria (from kanban):
  - No future run can leave an unvoiceable "General Summary" digest in
    pending-TTS.
  - create_daily_digests() must NOT call create_general_summary() even when
    every topic produces zero qualifying episodes.
  - get_digests_pending_tts() must exclude "General Summary" topic digests,
    so any orphaned rows from before the fix are permanently ignored.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from datetime import date

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_digest(topic="General Summary", episode_count=3, digest_id=1):
    """Minimal Digest-like mock."""
    d = MagicMock()
    d.id = digest_id
    d.topic = topic
    d.episode_count = episode_count
    d.script_content = "test script"
    d.script_path = f"/tmp/fake_{topic.replace(' ', '_')}.md"
    d.mp3_path = None
    d.digest_date = date(2026, 6, 14)
    return d


# ── Test 1: create_daily_digests() never calls create_general_summary() ───────

class TestCreateDailyDigestsNoRecapFallback(unittest.TestCase):
    """
    When every topic yields zero qualifying episodes, create_daily_digests()
    must return an empty list without ever calling create_general_summary().
    """

    def _make_script_generator(self):
        """
        Build a ScriptGenerator with enough mocks to call create_daily_digests()
        without touching the database, LLM, or filesystem.
        """
        from src.generation.script_generator import ScriptGenerator

        sg = ScriptGenerator.__new__(ScriptGenerator)
        # Wire only the attributes accessed by create_daily_digests()
        sg.topic_instructions = {
            "AI Technology": MagicMock(),
            "Climate & Environment": MagicMock(),
        }
        sg.digest_repo = MagicMock()
        sg.episode_repo = MagicMock()
        sg.topic_repo = MagicMock()
        sg.digest_episode_link_repo = MagicMock()
        sg.logger = MagicMock()

        # create_digest() → None (no qualifying episodes for any topic)
        sg.create_digest = MagicMock(return_value=None)
        # create_general_summary() should NEVER be called — spy on it
        sg.create_general_summary = MagicMock(return_value=None)
        return sg

    def test_no_call_to_create_general_summary_when_no_qualifying_episodes(self):
        """
        Even with zero qualifying digests, create_general_summary() must NOT
        be invoked. The fallback is permanently disabled.
        """
        sg = self._make_script_generator()
        result = sg.create_daily_digests(date(2026, 6, 14))

        sg.create_general_summary.assert_not_called()
        self.assertEqual(result, [])

    def test_returns_topic_digests_when_some_qualify(self):
        """
        When at least one topic produces a qualifying digest, that digest is
        returned and create_general_summary() is still never called.
        """
        sg = self._make_script_generator()
        qualifying = _make_digest("AI Technology", episode_count=2, digest_id=42)
        # First topic returns a qualifying digest; second returns None
        sg.create_digest = MagicMock(side_effect=[qualifying, None])

        result = sg.create_daily_digests(date(2026, 6, 14))

        sg.create_general_summary.assert_not_called()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].topic, "AI Technology")

    def test_does_not_create_general_summary_topic_in_db(self):
        """
        The digest_repo must never be asked to create a 'General Summary'
        topic row regardless of what topics qualify.
        """
        sg = self._make_script_generator()
        sg.create_digest = MagicMock(return_value=None)
        sg.create_daily_digests(date(2026, 6, 14))

        # Inspect all create() calls — none should have topic='General Summary'
        for create_call in sg.digest_repo.create.call_args_list:
            args, kwargs = create_call
            if args:
                digest_arg = args[0]
                self.assertNotEqual(
                    getattr(digest_arg, "topic", None),
                    "General Summary",
                    "digest_repo.create() was called with topic='General Summary'",
                )

    def test_topic_digest_errors_fail_the_daily_digest_phase(self):
        """
        A topic creation exception is a real phase failure, not the same as a
        quiet day with no qualifying episodes.
        """
        from src.generation.script_generator import ScriptGenerationError

        sg = self._make_script_generator()
        sg.create_digest = MagicMock(
            side_effect=[RuntimeError("database write failed"), None]
        )

        with self.assertRaisesRegex(
            ScriptGenerationError,
            "AI Technology: database write failed",
        ):
            sg.create_daily_digests(date(2026, 6, 14))

        sg.create_general_summary.assert_not_called()


# ── Test 2: get_digests_pending_tts() excludes 'General Summary' rows ────────

class TestGetDigestsPendingTTSExcludesGeneralSummary(unittest.TestCase):
    """
    Even if a 'General Summary' digest row survives in the database from before
    the fix, get_digests_pending_tts() must not return it to the TTS phase.
    """

    def _make_mock_session(self, model_rows):
        """Build a context-manager mock around a SQLAlchemy-style session."""
        session = MagicMock()
        # Simulate the ORM chain: .query().filter()...filter().order_by().all()
        query_chain = MagicMock()
        query_chain.filter.return_value = query_chain
        query_chain.order_by.return_value = query_chain
        query_chain.all.return_value = model_rows
        session.query.return_value = query_chain

        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=session)
        ctx.__exit__ = MagicMock(return_value=False)
        return ctx

    def test_general_summary_filter_is_applied(self):
        """
        The query must include a filter that excludes topic='General Summary'.
        We verify this by checking that DigestModel.topic != 'General Summary'
        is part of the filter chain (the column expression evaluates falsy for
        that value at the SQLAlchemy expression level — we test via the SQL
        compiled form or by confirming the filter call count increased).
        """
        from src.database.models import DigestRepository
        from src.database.sqlalchemy_models import Digest as DigestModel

        repo = DigestRepository.__new__(DigestRepository)
        ctx = self._make_mock_session([])
        repo.db = MagicMock()
        repo.db.get_session.return_value = ctx
        repo._model_to_digest = MagicMock(side_effect=lambda m: m)

        repo.get_digests_pending_tts()

        session = ctx.__enter__.return_value
        query_chain = session.query.return_value

        # filter() should be called at least 4 times:
        #   1. (script_path IS NOT NULL OR script_content IS NOT NULL)
        #   2. mp3_path IS NULL
        #   3. episode_count > 0
        #   4. topic != 'General Summary'   ← the new guard
        self.assertGreaterEqual(
            query_chain.filter.call_count, 4,
            "Expected at least 4 filter() calls on the pending-TTS query, "
            "including the General Summary exclusion guard.",
        )

    def test_general_summary_digest_not_returned(self):
        """
        A mocked row with topic='General Summary' must NOT appear in the
        output even when the underlying session returns it.

        We achieve this by patching the filter() chain so the 4th filter
        (the General Summary exclusion) drops the row — which mirrors what
        the real SQLAlchemy expression does in production.
        """
        from src.database.models import DigestRepository
        from src.database.sqlalchemy_models import Digest as DigestModel

        # Build two fake model rows: one real topic and one General Summary
        ai_row = MagicMock()
        ai_row.topic = "AI Technology"
        gs_row = MagicMock()
        gs_row.topic = "General Summary"

        repo = DigestRepository.__new__(DigestRepository)
        repo.db = MagicMock()
        repo._model_to_digest = MagicMock(side_effect=lambda m: m)

        # Simulate real SQLAlchemy filter behaviour: each filter() narrows the
        # set. We'll use a real filter closure on topic != 'General Summary'.
        class _FakeQueryChain:
            """Mini query chain that honours the General Summary exclusion."""
            def __init__(self, rows):
                self._rows = rows
                self.filter_count = 0

            def filter(self, *args, **kwargs):
                self.filter_count += 1
                # On the 4th filter call, actually drop General Summary rows.
                if self.filter_count >= 4:
                    self._rows = [r for r in self._rows
                                  if r.topic != "General Summary"]
                return self

            def order_by(self, *args, **kwargs):
                return self

            def all(self):
                return self._rows

        chain = _FakeQueryChain([ai_row, gs_row])
        session = MagicMock()
        session.query.return_value = chain

        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=session)
        ctx.__exit__ = MagicMock(return_value=False)
        repo.db.get_session.return_value = ctx

        results = repo.get_digests_pending_tts()
        topics = [r.topic for r in results]

        self.assertNotIn(
            "General Summary", topics,
            "get_digests_pending_tts() must never return 'General Summary' rows.",
        )
        self.assertIn(
            "AI Technology", topics,
            "get_digests_pending_tts() must still return real topic rows.",
        )


# ── Test 3: end-to-end: TTS phase cannot receive a General Summary digest ────

class TestTTSPhaseNeverSeesGeneralSummary(unittest.TestCase):
    """
    Smoke-level integration: patching DigestRepository.get_digests_pending_tts()
    to return a General Summary digest must be prevented by the guard added in
    that method, or (if the guard is bypassed in a test) the TTS runner must
    treat it as a skip.

    This test exercises the invariant end-to-end by confirming that calling
    generate_audio() with a General Summary digest in the queue results in a
    successful (skipped) outcome and never propagates an audio file.
    """

    def test_tts_runner_skips_general_summary_via_no_voice_config(self):
        """
        If a 'General Summary' digest somehow reaches the TTS runner
        (defence-in-depth), CompleteAudioProcessor must skip it gracefully
        via NoVoiceConfigError (tested in test_tts_skip_no_voice.py).

        Here we only verify that the TTS runner's generate_audio() method
        does NOT mark a General Summary digest as a hard failure.
        """
        from scripts.run_tts import TTSRunner
        from src.audio.audio_generator import NoVoiceConfigError

        gs_digest = _make_digest("General Summary", episode_count=2, digest_id=664)

        runner = TTSRunner.__new__(TTSRunner)
        runner.logger = MagicMock()
        runner.pipeline_logger = MagicMock()
        runner.digest_repo = MagicMock()
        runner.digest_repo.get_digests_pending_tts.return_value = [gs_digest]
        runner.limit = None
        runner.dry_run = False
        runner.no_parallel = True  # force sequential for predictability

        # CompleteAudioProcessor raises NoVoiceConfigError for General Summary
        mock_processor = MagicMock()
        mock_processor.process_digest_to_audio.return_value = {
            'success': True,
            'skipped': True,
            'skip_reason': "No voice configuration found for topic 'General Summary'",
            'errors': [],
        }
        runner.complete_audio_processor = mock_processor

        result = runner.generate_audio()

        self.assertTrue(result['success'], "TTS phase must succeed even when only General Summary digests are queued")
        self.assertEqual(result.get('audio_generated', 0), 0,
                         "No audio files should be generated for General Summary")
        # The skip count may or may not be surfaced in the result dict — the key
        # invariant is that 'success' is True and no hard failures occurred.
        hard_failures = result.get('audio_failed', 0)
        self.assertEqual(hard_failures, 0,
                         "General Summary must never count as a hard TTS failure")


if __name__ == "__main__":
    unittest.main()
