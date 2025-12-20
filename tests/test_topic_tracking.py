#!/usr/bin/env python3
"""
Unit tests for topic tracking functionality
"""

import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock

# Add project paths
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

# Set up environment via centralized entry point
from src.config.env import load_env
load_env()


class TestTopicExtractor(unittest.TestCase):
    """Test TopicExtractor functionality"""

    @patch('src.topic_tracking.topic_extractor.OpenAI')
    @patch('src.topic_tracking.topic_extractor.get_topic_tracking_repo')
    @patch('src.topic_tracking.topic_extractor.get_episode_repo')
    @patch('src.topic_tracking.topic_extractor.WebConfigManager')
    def test_extract_topics_basic(self, mock_config, mock_episode_repo, mock_tracking_repo, mock_openai):
        """Test basic topic extraction"""
        from src.topic_tracking.topic_extractor import TopicExtractor

        # Mock configuration
        mock_config_instance = Mock()
        mock_config_instance.get_setting.return_value = 15
        mock_config.return_value = mock_config_instance

        # Mock episode repository
        mock_episode = Mock()
        mock_episode.id = 1
        mock_episode_repo_instance = Mock()
        mock_episode_repo_instance.get_by_episode_guid.return_value = mock_episode
        mock_episode_repo.return_value = mock_episode_repo_instance

        # Mock topic tracking repository
        mock_tracking_instance = Mock()
        mock_tracking_repo.return_value = mock_tracking_instance

        # Mock OpenAI response
        mock_openai_instance = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='{"topics": [{"name": "AI Safety", "key_points": ["Point 1", "Point 2"]}]}'))]
        mock_openai_instance.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_openai_instance

        # Create extractor
        extractor = TopicExtractor()

        # Test extraction
        result = extractor.extract_and_store_topics(
            episode_guid="test-guid",
            digest_topic="AI and Technology",
            transcript="Test transcript about AI safety",
            relevance_score=0.85
        )

        # Verify
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['name'], "AI Safety")

    def test_normalize_topic_name(self):
        """Test topic name normalization"""
        from src.database.topic_tracking_repo import TopicTrackingRepository

        repo = TopicTrackingRepository()

        # Test various inputs
        self.assertEqual(repo._normalize_topic_name("OpenAI Leadership Crisis"), "openai-leadership-crisis")
        self.assertEqual(repo._normalize_topic_name("GPT-5 Release"), "gpt-5-release")
        self.assertEqual(repo._normalize_topic_name("AI  Safety   "), "ai-safety")


class TestAdFilter(unittest.TestCase):
    """Test AdFilter functionality"""

    @patch('src.topic_tracking.ad_filter.get_common_ads_repo')
    @patch('src.topic_tracking.ad_filter.WebConfigManager')
    def test_filter_disabled(self, mock_config, mock_ad_repo):
        """Test that filtering is skipped when disabled"""
        from src.topic_tracking.ad_filter import AdFilter

        # Mock configuration with filtering disabled
        mock_config_instance = Mock()
        mock_config_instance.get_setting.side_effect = lambda section, key, default: False if key == "enabled" else 0.7
        mock_config.return_value = mock_config_instance

        # Mock ad repository
        mock_ad_repo_instance = Mock()
        mock_ad_repo_instance.get_active_patterns.return_value = []
        mock_ad_repo.return_value = mock_ad_repo_instance

        # Create filter
        ad_filter = AdFilter()

        # Test filtering
        transcript = "This is a test transcript with potential ad content."
        filtered, detected = ad_filter.filter_transcript(transcript)

        # Verify nothing was filtered
        self.assertEqual(filtered, transcript)
        self.assertEqual(len(detected), 0)

    @patch('src.topic_tracking.ad_filter.get_common_ads_repo')
    @patch('src.topic_tracking.ad_filter.WebConfigManager')
    def test_filter_detects_ads(self, mock_config, mock_ad_repo):
        """Test that ads are detected and filtered"""
        from src.topic_tracking.ad_filter import AdFilter

        # Mock configuration with filtering enabled
        mock_config_instance = Mock()
        mock_config_instance.get_setting.side_effect = lambda section, key, default: True if key == "enabled" else 0.5
        mock_config.return_value = mock_config_instance

        # Mock ad repository with test pattern
        mock_ad_repo_instance = Mock()
        mock_ad_repo_instance.get_active_patterns.return_value = [
            {
                "advertiser_name": "TestBrand",
                "pattern_keywords": ["test", "brand", "sponsor"],
                "confidence_threshold": 0.5
            }
        ]
        mock_ad_repo.return_value = mock_ad_repo_instance

        # Create filter
        ad_filter = AdFilter()

        # Test filtering
        transcript = "Welcome to the show.\nThis episode is brought to you by TestBrand, our sponsor.\nNow back to the content."
        filtered, detected = ad_filter.filter_transcript(transcript)

        # Verify ad was detected and line removed
        self.assertNotIn("TestBrand", filtered)
        self.assertIn("TestBrand", detected)
        self.assertIn("Welcome to the show", filtered)
        self.assertIn("Now back to the content", filtered)


class TestScriptGeneratorIntegration(unittest.TestCase):
    """Test script generator integration with topic tracking"""

    @patch('src.generation.script_generator.get_topic_tracking_repo')
    @patch('src.generation.script_generator.AdFilter')
    def test_topic_history_retrieval(self, mock_ad_filter, mock_tracking_repo):
        """Test that topic history is retrieved for deduplication"""
        # Mock topic tracking repository
        mock_tracking_instance = Mock()
        mock_tracking_instance.get_topics_last_n_days.return_value = [
            {
                'topic_name': 'OpenAI Leadership',
                'topic_slug': 'openai-leadership',
                'key_points': ['Sam Altman returns', 'Board restructuring']
            }
        ]
        mock_tracking_repo.return_value = mock_tracking_instance

        # Mock ad filter
        mock_ad_filter_instance = Mock()
        mock_ad_filter_instance.filter_transcript.return_value = ("Test transcript", [])
        mock_ad_filter.return_value = mock_ad_filter_instance

        # Test that history can be retrieved
        from src.generation.script_generator import ScriptGenerator

        # Create generator with mocked dependencies
        with patch('src.generation.script_generator.get_episode_repo'):
            with patch('src.generation.script_generator.get_digest_repo'):
                with patch('src.generation.script_generator.get_digest_episode_link_repo'):
                    with patch('src.generation.script_generator.WebConfigManager'):
                        with patch('src.generation.script_generator.ConfigManager'):
                            generator = ScriptGenerator()
                            generator.topic_tracking_repo = mock_tracking_instance

                            # Test history retrieval
                            history = generator._get_recent_topic_history("AI and Technology", days_back=7)

                            # Verify
                            self.assertIn("RECENT TOPICS COVERED", history)
                            self.assertIn("OpenAI Leadership", history)

    @patch('src.generation.script_generator.get_topic_tracking_repo')
    def test_repetition_check(self, mock_tracking_repo):
        """Test topic repetition checking"""
        # Mock topic tracking repository
        mock_tracking_instance = Mock()

        # Current episodes have these topics
        mock_tracking_instance.get_topics_for_episode.return_value = [
            {'topic_slug': 'openai-leadership'},
            {'topic_slug': 'gpt-5-release'},
        ]

        # Recent topics (80% overlap)
        mock_tracking_instance.get_topics_last_n_days.return_value = [
            {'topic_slug': 'openai-leadership'},
            {'topic_slug': 'gpt-5-release'},
        ]

        mock_tracking_repo.return_value = mock_tracking_instance

        # Test repetition check
        from src.generation.script_generator import ScriptGenerator

        with patch('src.generation.script_generator.get_episode_repo'):
            with patch('src.generation.script_generator.get_digest_repo'):
                with patch('src.generation.script_generator.get_digest_episode_link_repo'):
                    with patch('src.generation.script_generator.WebConfigManager'):
                        with patch('src.generation.script_generator.ConfigManager'):
                            with patch('src.generation.script_generator.AdFilter'):
                                generator = ScriptGenerator()
                                generator.topic_tracking_repo = mock_tracking_instance
                                generator.web_config = Mock()
                                generator.web_config.get_setting.return_value = 14

                                # Test with mock episodes
                                mock_episode = Mock()
                                mock_episode.id = 1
                                episodes = [mock_episode]

                                is_repetitive, msg = generator._check_topic_repetition(
                                    episodes, "AI and Technology", repetition_threshold=0.8
                                )

                                # Verify - should be repetitive (100% overlap)
                                self.assertTrue(is_repetitive)


if __name__ == '__main__':
    unittest.main()
