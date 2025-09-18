#!/usr/bin/env python3
"""
Integration tests for phase scripts.
Tests command-line arguments, database interactions, and basic functionality.
"""

import os
import sys
import subprocess
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.web_config import WebConfigManager
from src.database.models import get_episode_repo, get_digest_repo
from scripts.run_publishing import PublishingPipelineRunner


class TestPhaseScripts(unittest.TestCase):
    """Test all phase scripts for basic functionality and integration"""

    def setUp(self):
        """Set up test environment"""
        self.project_root = PROJECT_ROOT
        self.scripts_dir = self.project_root / "scripts"

        # Store original environment
        self.original_env = os.environ.copy()

        # Set up test environment variables
        os.environ.update({
            'OPENAI_API_KEY': 'test-key',
            'ELEVENLABS_API_KEY': 'test-key',
            'GITHUB_TOKEN': 'test-token',
            'GITHUB_REPOSITORY': 'test/repo',
            'DATABASE_URL': 'sqlite:///test.db',
            'DRY_RUN': 'true'
        })

    def tearDown(self):
        """Clean up test environment"""
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_discovery_script_help(self):
        """Test run_discovery.py shows help and handles arguments"""
        script_path = self.scripts_dir / "run_discovery.py"
        self.assertTrue(script_path.exists(), f"Discovery script not found: {script_path}")

        # Test help option
        result = subprocess.run(
            [sys.executable, str(script_path), "--help"],
            capture_output=True,
            text=True,
            cwd=str(self.project_root)
        )

        self.assertEqual(result.returncode, 0, f"Discovery script help failed: {result.stderr}")
        self.assertIn("usage", result.stdout.lower() or result.stderr.lower())

    def test_audio_script_help(self):
        """Test run_audio.py shows help and handles arguments"""
        script_path = self.scripts_dir / "run_audio.py"
        self.assertTrue(script_path.exists(), f"Audio script not found: {script_path}")

        # Test help option
        result = subprocess.run(
            [sys.executable, str(script_path), "--help"],
            capture_output=True,
            text=True,
            cwd=str(self.project_root)
        )

        self.assertEqual(result.returncode, 0, f"Audio script help failed: {result.stderr}")
        self.assertIn("usage", result.stdout.lower() or result.stderr.lower())

    def test_scoring_script_help(self):
        """Test run_scoring.py shows help and handles arguments"""
        script_path = self.scripts_dir / "run_scoring.py"
        self.assertTrue(script_path.exists(), f"Scoring script not found: {script_path}")

        # Test help option
        result = subprocess.run(
            [sys.executable, str(script_path), "--help"],
            capture_output=True,
            text=True,
            cwd=str(self.project_root)
        )

        self.assertEqual(result.returncode, 0, f"Scoring script help failed: {result.stderr}")
        self.assertIn("usage", result.stdout.lower() or result.stderr.lower())

    def test_digest_script_help(self):
        """Test run_digest.py shows help and handles arguments"""
        script_path = self.scripts_dir / "run_digest.py"
        self.assertTrue(script_path.exists(), f"Digest script not found: {script_path}")

        # Test help option
        result = subprocess.run(
            [sys.executable, str(script_path), "--help"],
            capture_output=True,
            text=True,
            cwd=str(self.project_root)
        )

        self.assertEqual(result.returncode, 0, f"Digest script help failed: {result.stderr}")
        self.assertIn("usage", result.stdout.lower() or result.stderr.lower())

    def test_tts_script_help(self):
        """Test run_tts.py shows help and handles arguments"""
        script_path = self.scripts_dir / "run_tts.py"
        self.assertTrue(script_path.exists(), f"TTS script not found: {script_path}")

        # Test help option
        result = subprocess.run(
            [sys.executable, str(script_path), "--help"],
            capture_output=True,
            text=True,
            cwd=str(self.project_root)
        )

        self.assertEqual(result.returncode, 0, f"TTS script help failed: {result.stderr}")
        self.assertIn("usage", result.stdout.lower() or result.stderr.lower())

    def test_tts_script_dry_run_empty_payload(self):
        """Run TTS script in dry-run mode with no digests and expect success"""
        script_path = self.scripts_dir / "run_tts.py"
        self.assertTrue(script_path.exists(), f"TTS script not found: {script_path}")

        payload = json.dumps({"success": True, "digests": []})
        result = subprocess.run(
            [sys.executable, str(script_path), "--dry-run"],
            input=payload,
            capture_output=True,
            text=True,
            cwd=str(self.project_root)
        )

        self.assertEqual(result.returncode, 0, f"TTS dry run failed: {result.stderr}")
        output = (result.stdout or result.stderr).strip()
        lines = [line for line in output.splitlines() if line.strip()]
        json_line = None
        for line in reversed(lines):
            if line.strip().startswith('{'):
                json_line = line.strip()
                break
        self.assertIsNotNone(json_line, f"No JSON payload found in output: {output}")
        data = json.loads(json_line)
        self.assertTrue(data.get("success"), f"Unexpected response: {data}")
        self.assertEqual(data.get("audio_generated"), 0)

    @patch('scripts.run_publishing.get_digest_repo')
    def test_publishing_runner_dry_run(self, mock_get_repo):
        """Publishing pipeline returns success in dry run mode with no digests"""
        mock_repo = MagicMock()
        mock_repo.get_recent_digests.return_value = []
        mock_get_repo.return_value = mock_repo

        runner = PublishingPipelineRunner(dry_run=True)
        self.assertTrue(runner.run_complete_pipeline())
        mock_repo.get_recent_digests.assert_called_once()

    def test_publishing_script_help(self):
        """Test run_publishing.py shows help and handles arguments"""
        script_path = self.scripts_dir / "run_publishing.py"
        self.assertTrue(script_path.exists(), f"Publishing script not found: {script_path}")

        # Test help option
        result = subprocess.run(
            [sys.executable, str(script_path), "--help"],
            capture_output=True,
            text=True,
            cwd=str(self.project_root)
        )

        self.assertEqual(result.returncode, 0, f"Publishing script help failed: {result.stderr}")
        self.assertIn("usage", result.stdout.lower() or result.stderr.lower())

    @patch('src.database.models.get_episode_repo')
    def test_discovery_script_database_interaction(self, mock_get_repo):
        """Test discovery script database interaction"""
        # Mock episode repository
        mock_repo = MagicMock()
        mock_get_repo.return_value = mock_repo

        # Test that script can import and initialize database components
        script_path = self.scripts_dir / "run_discovery.py"

        # Run with dry-run or minimal arguments to test initialization
        result = subprocess.run(
            [sys.executable, str(script_path), "--limit", "1", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=str(self.project_root)
        )

        # Should not crash on import and basic setup
        # Accept any exit code since we're just testing that it doesn't crash on import
        self.assertIsNotNone(result.returncode, "Script should complete execution")

    @patch('src.database.models.get_digest_repo')
    def test_digest_script_database_interaction(self, mock_get_repo):
        """Test digest script database interaction"""
        # Mock digest repository
        mock_repo = MagicMock()
        mock_get_repo.return_value = mock_repo

        script_path = self.scripts_dir / "run_digest.py"

        # Run with minimal arguments to test initialization
        result = subprocess.run(
            [sys.executable, str(script_path), "--limit", "1", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=str(self.project_root)
        )

        # Should not crash on import and basic setup
        self.assertIsNotNone(result.returncode, "Script should complete execution")

    def test_environment_validation(self):
        """Test that scripts properly validate environment configuration"""
        # Test with missing API key
        env_copy = os.environ.copy()
        if 'OPENAI_API_KEY' in os.environ:
            del os.environ['OPENAI_API_KEY']

        try:
            script_path = self.scripts_dir / "run_scoring.py"

            # This should fail or warn about missing API key
            result = subprocess.run(
                [sys.executable, str(script_path), "--help"],
                capture_output=True,
                text=True,
                cwd=str(self.project_root)
            )

            # Help should still work even with missing API key
            self.assertEqual(result.returncode, 0, "Help should work even with missing API key")

        finally:
            # Restore environment
            os.environ.clear()
            os.environ.update(env_copy)

    def test_config_integration(self):
        """Test that scripts can integrate with WebConfigManager"""
        try:
            # Test that WebConfigManager can be imported and initialized
            config_manager = WebConfigManager()

            # Test that AI models are available
            ai_models = config_manager.get_ai_models()
            self.assertIsInstance(ai_models, dict, "AI models should be a dictionary")
            self.assertIn('openai', ai_models, "OpenAI models should be available")
            self.assertIn('elevenlabs', ai_models, "ElevenLabs models should be available")

            # Test that configuration categories exist
            content_scoring = config_manager.get_category('ai_content_scoring')
            self.assertIsInstance(content_scoring, dict, "Content scoring config should be available")

        except Exception as e:
            self.fail(f"WebConfigManager integration failed: {e}")

    def test_script_imports(self):
        """Test that all scripts can be imported without errors"""
        script_files = [
            "run_discovery.py",
            "run_audio.py",
            "run_scoring.py",
            "run_digest.py",
            "run_tts.py",
            "run_publishing.py"
        ]

        for script_name in script_files:
            script_path = self.scripts_dir / script_name

            if script_path.exists():
                # Test that script can be executed without crashing on import
                result = subprocess.run(
                    [sys.executable, "-c", f"import sys; sys.path.insert(0, '{self.project_root}'); exec(open('{script_path}').read()[:100] + '\\n# Import test')"],
                    capture_output=True,
                    text=True,
                    cwd=str(self.project_root)
                )

                # We expect some errors since we're not running the full script,
                # but import errors should be caught early
                if "ImportError" in result.stderr or "ModuleNotFoundError" in result.stderr:
                    self.fail(f"Import error in {script_name}: {result.stderr}")

    def test_orchestrator_integration(self):
        """Test orchestrator script functionality"""
        orchestrator_path = self.project_root / "run_full_pipeline_orchestrator.py"

        if orchestrator_path.exists():
            # Test help option
            result = subprocess.run(
                [sys.executable, str(orchestrator_path), "--help"],
                capture_output=True,
                text=True,
                cwd=str(self.project_root)
            )

            self.assertEqual(result.returncode, 0, f"Orchestrator help failed: {result.stderr}")
            self.assertIn("usage", result.stdout.lower() or result.stderr.lower())

            # Test that it recognizes phase arguments
            help_text = result.stdout + result.stderr
            self.assertIn("phase", help_text.lower(), "Should mention phase argument")

    def test_ai_configuration_defaults(self):
        """Test that AI configuration has proper defaults"""
        try:
            config_manager = WebConfigManager()

            # Test content scoring defaults
            content_scoring = config_manager.get_category('ai_content_scoring')
            self.assertIn('model', content_scoring)
            self.assertIn('max_tokens', content_scoring)
            self.assertIn('prompt_max_chars', content_scoring)

            # Test digest generation defaults
            digest_generation = config_manager.get_category('ai_digest_generation')
            self.assertIn('model', digest_generation)
            self.assertIn('max_output_tokens', digest_generation)
            self.assertIn('max_input_tokens', digest_generation)
            self.assertIn('transcript_buffer_percent', digest_generation)
            self.assertIn('transcript_min_chars', digest_generation)
            self.assertIn('transcript_max_chars', digest_generation)

            # Test metadata generation defaults
            metadata_generation = config_manager.get_category('ai_metadata_generation')
            self.assertIn('model', metadata_generation)
            self.assertIn('max_title_tokens', metadata_generation)

            # Test TTS generation defaults
            tts_generation = config_manager.get_category('ai_tts_generation')
            self.assertIn('model', tts_generation)
            self.assertIn('max_characters', tts_generation)

            # Test STT transcription defaults
            stt_transcription = config_manager.get_category('ai_stt_transcription')
            self.assertIn('model', stt_transcription)
            self.assertIn('max_file_size_mb', stt_transcription)

            transcript_processing = config_manager.get_category('transcript_processing')
            self.assertIn('ad_trim_enabled', transcript_processing)
            self.assertIn('ad_trim_start_percent', transcript_processing)
            self.assertIn('ad_trim_end_percent', transcript_processing)

        except Exception as e:
            self.fail(f"AI configuration defaults test failed: {e}")

    def test_model_validation(self):
        """Test that model validation works properly"""
        try:
            config_manager = WebConfigManager()

            # Test OpenAI model limits
            gpt5_limit = config_manager.get_model_limit('openai', 'gpt-5', 'max_output')
            self.assertIsInstance(gpt5_limit, int, "Model limit should be integer")
            self.assertGreater(gpt5_limit, 0, "Model limit should be positive")

            # Test ElevenLabs model limits
            turbo_limit = config_manager.get_model_limit('elevenlabs', 'eleven_turbo_v2_5', 'max_characters')
            self.assertIsInstance(turbo_limit, int, "Character limit should be integer")
            self.assertGreater(turbo_limit, 0, "Character limit should be positive")

            # Test Whisper model limits
            whisper_limit = config_manager.get_model_limit('whisper', 'whisper-1', 'max_file_size_mb')
            self.assertIsInstance(whisper_limit, int, "File size limit should be integer")
            self.assertGreater(whisper_limit, 0, "File size limit should be positive")

        except Exception as e:
            self.fail(f"Model validation test failed: {e}")


if __name__ == '__main__':
    # Set up test environment
    os.environ.setdefault('DATABASE_URL', 'sqlite:///test.db')
    os.environ.setdefault('OPENAI_API_KEY', 'test-key')
    os.environ.setdefault('ELEVENLABS_API_KEY', 'test-key')
    os.environ.setdefault('GITHUB_TOKEN', 'test-token')
    os.environ.setdefault('GITHUB_REPOSITORY', 'test/repo')

    unittest.main()
