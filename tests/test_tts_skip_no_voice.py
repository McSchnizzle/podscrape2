#!/usr/bin/env python3
"""
Tests for kanban #1618 — TTS hardening:
  (1) SKIP-NOT-FAIL: topics with no voice config are skipped, not failed,
      so one unconfigurable topic never fails the whole TTS phase.
  (2) ERROR-KEY FIX: orchestrator surfaces real error text from nested
      audio_results[i]['errors'] when the top-level 'error' key is absent.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import date

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ── helpers ──────────────────────────────────────────────────────────────────

def _make_digest(digest_id=664, topic="General Summary", episode_count=3, script_content="Test script."):
    """Build a minimal Digest-like object for testing (no DB required)."""
    d = MagicMock()
    d.id = digest_id
    d.topic = topic
    d.episode_count = episode_count
    d.script_content = script_content
    d.script_path = f"/tmp/fake_{topic.replace(' ', '_')}_20260614_000000.md"
    d.mp3_path = None
    return d


# ── Test 1: NoVoiceConfigError is defined and is-a AudioGenerationError ──────

class TestNoVoiceConfigError(unittest.TestCase):
    """NoVoiceConfigError must be importable and subclass AudioGenerationError."""

    def test_exception_hierarchy(self):
        from src.audio.audio_generator import NoVoiceConfigError, AudioGenerationError
        err = NoVoiceConfigError("no voice for 'General Summary'")
        self.assertIsInstance(err, AudioGenerationError)
        self.assertIsInstance(err, Exception)

    def test_exception_message(self):
        from src.audio.audio_generator import NoVoiceConfigError
        msg = "No voice configuration found for topic 'General Summary'"
        err = NoVoiceConfigError(msg)
        self.assertEqual(str(err), msg)


# ── Test 2: _get_voice_id_for_topic raises NoVoiceConfigError when missing ───

class TestGetVoiceIdNoConfig(unittest.TestCase):
    """_get_voice_id_for_topic should raise NoVoiceConfigError (not AudioGenerationError)
    when the topic has no voice in either the database or config/topics.json."""

    def _make_generator(self):
        """Create an AudioGenerator with all external dependencies mocked."""
        with patch("src.audio.audio_generator.WebConfigManager"), \
             patch("src.audio.audio_generator.VoiceManager"), \
             patch("src.audio.audio_generator.get_digest_repo"), \
             patch("src.audio.audio_generator.get_topic_repo"):
            from src.audio.audio_generator import AudioGenerator
            gen = AudioGenerator.__new__(AudioGenerator)
            gen.web_config = None
            gen.ai_model = "eleven_turbo_v2_5"
            gen.max_characters = 35000
            gen.audio_dir = Path("/tmp")
            gen.api_key = None
            gen._api_key_checked = False
            gen.request_delay = 1.0
            gen.elevenlabs_timeout = 60
            gen.elevenlabs_dialogue_timeout = 300
            gen.ffmpeg_timeout = 300
            gen.last_request_time = 0
            gen.voice_manager = MagicMock()
            gen.digest_repo = MagicMock()
            return gen

    def test_raises_no_voice_config_error_when_db_and_json_both_miss(self):
        """If neither DB nor JSON has voice config, NoVoiceConfigError is raised."""
        from src.audio.audio_generator import NoVoiceConfigError

        gen = self._make_generator()

        # DB returns topic with no voice_1_id
        db_topic = MagicMock()
        db_topic.name = "General Summary"
        db_topic.voice_1_id = None

        with patch("src.database.models.get_topic_repo") as mock_repo_fn:
            mock_repo = MagicMock()
            mock_repo.get_all_topics.return_value = [db_topic]
            mock_repo_fn.return_value = mock_repo

            # JSON file exists but doesn't list "General Summary"
            json_data = '{"topics": [{"name": "AI and Technology", "voice_id": "some-id"}]}'
            with patch("builtins.open", unittest.mock.mock_open(read_data=json_data)):
                with self.assertRaises(NoVoiceConfigError) as ctx:
                    gen._get_voice_id_for_topic("General Summary")

        self.assertIn("General Summary", str(ctx.exception))

    def test_returns_db_voice_id_when_present(self):
        """Returns voice_1_id from DB when available (database-first).

        _get_voice_id_for_topic uses 'from src.database.models import get_topic_repo'
        inside the function body, so we patch at that module path.
        """
        gen = self._make_generator()

        db_topic = MagicMock()
        db_topic.name = "AI and Technology"
        db_topic.voice_1_id = "db-voice-id-123"

        # Patch where get_topic_repo is imported inside the function
        with patch("src.database.models.get_topic_repo") as mock_repo_fn:
            mock_repo = MagicMock()
            mock_repo.get_all_topics.return_value = [db_topic]
            mock_repo_fn.return_value = mock_repo

            result = gen._get_voice_id_for_topic("AI and Technology")

        self.assertEqual(result, "db-voice-id-123")

    def test_falls_back_to_json_when_db_has_no_voice(self):
        """Falls back to config/topics.json when DB topic has no voice_1_id."""
        gen = self._make_generator()

        db_topic = MagicMock()
        db_topic.name = "AI and Technology"
        db_topic.voice_1_id = None

        with patch("src.database.models.get_topic_repo") as mock_repo_fn:
            mock_repo = MagicMock()
            mock_repo.get_all_topics.return_value = [db_topic]
            mock_repo_fn.return_value = mock_repo

            json_data = '{"topics": [{"name": "AI and Technology", "voice_id": "json-voice-id"}]}'
            with patch("builtins.open", unittest.mock.mock_open(read_data=json_data)):
                result = gen._get_voice_id_for_topic("AI and Technology")

        self.assertEqual(result, "json-voice-id")


# ── Test 3: CompleteAudioProcessor treats NoVoiceConfigError as SKIP ──────────

class TestCompleteAudioProcessorSkip(unittest.TestCase):
    """process_digest_to_audio must return success=True, skipped=True when
    NoVoiceConfigError is raised during audio generation."""

    def test_no_voice_config_becomes_skip_not_failure(self):
        """NoVoiceConfigError during TTS → skip result, NOT an error result."""
        from src.audio.audio_generator import NoVoiceConfigError

        digest = _make_digest(topic="General Summary")

        with patch("src.audio.complete_audio_processor.AudioGenerator") as MockGen, \
             patch("src.audio.complete_audio_processor.MetadataGenerator") as MockMeta, \
             patch("src.audio.complete_audio_processor.AudioManager"), \
             patch("src.audio.complete_audio_processor.get_digest_repo"):

            # Metadata succeeds
            meta = MagicMock()
            meta.title = "Test Title"
            meta.summary = "Test summary."
            meta.episode_links = []
            MockMeta.return_value.generate_metadata_for_digest.return_value = meta

            # Audio generation raises NoVoiceConfigError
            MockGen.return_value.generate_audio_for_script.side_effect = NoVoiceConfigError(
                "No voice configuration found for topic 'General Summary'"
            )

            from src.audio.complete_audio_processor import CompleteAudioProcessor
            processor = CompleteAudioProcessor.__new__(CompleteAudioProcessor)
            processor.audio_generator = MockGen.return_value
            processor.metadata_generator = MockMeta.return_value
            processor.audio_manager = MagicMock()
            processor.digest_repo = MagicMock()

            result = processor.process_digest_to_audio(digest)

        self.assertTrue(result['success'], "success must be True for a skip")
        self.assertTrue(result.get('skipped'), "skipped must be True")
        self.assertIn("General Summary", result.get('skip_reason', ''))
        self.assertEqual(result.get('errors'), [], "errors list must be empty on skip")

    def test_real_tts_error_still_fails(self):
        """A genuine TTS error (e.g. network) should still mark the digest as failed."""
        from src.audio.audio_generator import AudioGenerationError

        digest = _make_digest(topic="AI and Technology")

        with patch("src.audio.complete_audio_processor.AudioGenerator") as MockGen, \
             patch("src.audio.complete_audio_processor.MetadataGenerator") as MockMeta, \
             patch("src.audio.complete_audio_processor.AudioManager"), \
             patch("src.audio.complete_audio_processor.get_digest_repo"):

            meta = MagicMock()
            meta.title = "Test Title"
            meta.summary = "Test."
            meta.episode_links = []
            MockMeta.return_value.generate_metadata_for_digest.return_value = meta

            MockGen.return_value.generate_audio_for_script.side_effect = AudioGenerationError(
                "ElevenLabs API returned 503"
            )

            from src.audio.complete_audio_processor import CompleteAudioProcessor
            processor = CompleteAudioProcessor.__new__(CompleteAudioProcessor)
            processor.audio_generator = MockGen.return_value
            processor.metadata_generator = MockMeta.return_value
            processor.audio_manager = MagicMock()
            processor.digest_repo = MagicMock()

            result = processor.process_digest_to_audio(digest)

        self.assertFalse(result['success'], "success must be False for a real error")
        self.assertFalse(result.get('skipped', False))
        self.assertTrue(len(result.get('errors', [])) > 0)

    def test_zero_episode_count_still_skips_before_no_voice(self):
        """episode_count=0 must skip before we ever reach voice lookup."""
        digest = _make_digest(topic="General Summary", episode_count=0)

        with patch("src.audio.complete_audio_processor.AudioGenerator") as MockGen, \
             patch("src.audio.complete_audio_processor.MetadataGenerator"), \
             patch("src.audio.complete_audio_processor.AudioManager"), \
             patch("src.audio.complete_audio_processor.get_digest_repo"):

            from src.audio.complete_audio_processor import CompleteAudioProcessor
            processor = CompleteAudioProcessor.__new__(CompleteAudioProcessor)
            processor.audio_generator = MockGen.return_value
            processor.metadata_generator = MagicMock()
            processor.audio_manager = MagicMock()
            processor.digest_repo = MagicMock()

            result = processor.process_digest_to_audio(digest)

        self.assertTrue(result['success'])
        self.assertTrue(result.get('skipped'))
        # Audio generator must NOT be called
        MockGen.return_value.generate_audio_for_script.assert_not_called()


# ── Test 4: run_tts.py phase success when all digests skip ──────────────────

class TestTTSRunnerPhaseSuccess(unittest.TestCase):
    """TTSRunner.generate_audio() must return success=True when all digests are
    skipped (no qualifying voice config) and zero are hard-failed."""

    def test_all_skipped_yields_phase_success(self):
        from scripts.run_tts import TTSRunner

        with patch.object(TTSRunner, '__init__', lambda self, **kw: None):
            runner = TTSRunner.__new__(TTSRunner)
            runner.logger = MagicMock()
            runner.pipeline_logger = MagicMock()
            runner.digest_repo = MagicMock()
            runner.complete_audio_processor = MagicMock()
            runner.dry_run = False
            runner.limit = None
            runner.no_parallel = True

            # Provide two digests to process
            d1 = _make_digest(664, "General Summary")
            d2 = _make_digest(670, "AI and Technology")
            runner.digest_repo.get_digests_pending_tts.return_value = [d1, d2]

            # Both skip (no voice config)
            def fake_process(digest):
                return {'success': True, 'skipped': True,
                        'skip_reason': 'No voice configuration found'}
            runner.complete_audio_processor.process_digest_to_audio.side_effect = fake_process

            result = runner.generate_audio()

        self.assertTrue(result['success'], "Phase must succeed when all digests skip")
        self.assertEqual(result['audio_generated'], 0)
        self.assertEqual(result['audio_failed'], 0)
        self.assertEqual(result.get('audio_skipped', 0), 2)

    def test_one_skip_one_success_yields_phase_success(self):
        """One skip + one real audio generation → phase still succeeds."""
        from src.audio.audio_generator import AudioMetadata
        from scripts.run_tts import TTSRunner

        with patch.object(TTSRunner, '__init__', lambda self, **kw: None):
            runner = TTSRunner.__new__(TTSRunner)
            runner.logger = MagicMock()
            runner.pipeline_logger = MagicMock()
            runner.digest_repo = MagicMock()
            runner.complete_audio_processor = MagicMock()
            runner.dry_run = False
            runner.limit = None
            runner.no_parallel = True

            d1 = _make_digest(664, "General Summary")
            d2 = _make_digest(670, "AI and Technology")
            runner.digest_repo.get_digests_pending_tts.return_value = [d1, d2]

            fake_meta = AudioMetadata(
                file_path="/tmp/fake.mp3",
                duration_seconds=1200.0,
                file_size_bytes=12345678,
                voice_name="Test Voice",
                voice_id="test-id",
            )

            def fake_process(digest):
                if digest.topic == "General Summary":
                    return {'success': True, 'skipped': True,
                            'skip_reason': 'No voice config'}
                return {'success': True, 'skipped': False, 'audio_metadata': fake_meta}
            runner.complete_audio_processor.process_digest_to_audio.side_effect = fake_process

            result = runner.generate_audio()

        self.assertTrue(result['success'])
        self.assertEqual(result['audio_generated'], 1)
        self.assertEqual(result['audio_failed'], 0)
        self.assertEqual(result.get('audio_skipped', 0), 1)


# ── Test 5: Orchestrator error-key mismatch fix ──────────────────────────────

class TestOrchestratorErrorKey(unittest.TestCase):
    """Orchestrator must surface nested audio_results[i]['errors'] when the
    top-level 'error' key is absent from a failed TTS result."""

    def _extract_tts_error_detail(self, tts_result: dict) -> str:
        """Replicate the fixed logic from run_full_pipeline_orchestrator.py."""
        return tts_result.get('error') or "; ".join(
            msg
            for r in tts_result.get('audio_results', [])
            if not r.get('success')
            for msg in (r.get('errors') or ([r.get('error')] if r.get('error') else []))
            if msg
        ) or 'no detail available'

    def test_surfaces_nested_errors_when_no_top_level_error(self):
        """The key scenario from the bug: no top-level 'error', only per-digest 'errors'."""
        tts_result = {
            'success': False,
            'audio_generated': 1,
            'audio_failed': 1,
            'audio_results': [
                {
                    'digest_id': 664,
                    'topic': 'General Summary',
                    'success': False,
                    'errors': ["TTS audio generation failed: Failed to get voice ID for topic 'General Summary': No voice configuration found for topic: General Summary"]
                },
                {
                    'digest_id': 670,
                    'topic': 'AI and Technology',
                    'success': True,
                    'skipped': False,
                }
            ]
        }

        detail = self._extract_tts_error_detail(tts_result)

        self.assertNotEqual(detail, 'None')
        self.assertNotEqual(detail, 'no detail available')
        self.assertIn('General Summary', detail)
        self.assertIn('No voice configuration found', detail)

    def test_uses_top_level_error_when_present(self):
        """Runner-level exception → top-level 'error' key → use it directly."""
        tts_result = {
            'success': False,
            'error': 'ElevenLabs API key not configured',
            'audio_generated': 0,
            'audio_results': []
        }

        detail = self._extract_tts_error_detail(tts_result)

        self.assertEqual(detail, 'ElevenLabs API key not configured')

    def test_fallback_message_when_no_errors_at_all(self):
        """Defensive: returns fallback string if no error detail exists anywhere."""
        tts_result = {
            'success': False,
            'audio_results': []
        }

        detail = self._extract_tts_error_detail(tts_result)

        self.assertEqual(detail, 'no detail available')

    def test_multiple_failed_digests_joined(self):
        """Multiple per-digest errors are joined with '; '."""
        tts_result = {
            'success': False,
            'audio_results': [
                {'success': False, 'errors': ['error A']},
                {'success': False, 'errors': ['error B']},
                {'success': True},
            ]
        }

        detail = self._extract_tts_error_detail(tts_result)

        self.assertIn('error A', detail)
        self.assertIn('error B', detail)


if __name__ == '__main__':
    unittest.main(verbosity=2)
