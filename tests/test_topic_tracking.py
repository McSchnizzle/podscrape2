#!/usr/bin/env python3
"""
Unit tests for topic tracking functionality
"""

import json
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

    @patch('src.topic_tracking.topic_extractor.StoryArcExtractor._call_claude_p')
    @patch('src.database.topic_tracking_repo.get_topic_tracking_repo')
    @patch('src.database.models.get_episode_repo')
    @patch('src.topic_tracking.topic_extractor.WebConfigManager')
    def test_extract_topics_basic(self, mock_config, mock_episode_repo, mock_tracking_repo, mock_claude_p):
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

        # Mock claude -p response
        mock_claude_p.return_value = json.dumps({
            "continuing_arcs": [{
                "arc_name": "AI Safety",
                "arc_slug": "ai-safety",
                "event_summary": "New developments in AI safety",
                "key_points": ["Point 1", "Point 2"],
                "perspective": "neutral"
            }],
            "new_arcs": []
        })

        # Create extractor
        extractor = TopicExtractor()

        # Test extraction
        result = extractor.extract_and_store_topics(
            episode_guid="test-guid",
            digest_topic="AI and Technology",
            transcript="Test transcript about AI safety",
            relevance_score=0.85
        )

        # Verify (may return empty if episode not in DB)
        self.assertIsInstance(result, list)

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

    def test_topic_history_retrieval(self):
        """Test that recent story arc context is retrieved for deduplication"""
        # Mock story arc repository
        mock_arc_repo = Mock()
        mock_arc_repo.get_story_arcs_for_digest.return_value = [
            {
                'arc_name': 'OpenAI Leadership',
                'arc_slug': 'openai-leadership',
                'event_count': 3,
                'source_count': 2,
                'is_hot': False,
            }
        ]

        # Test that context can be retrieved
        from src.generation.script_generator import ScriptGenerator

        with patch('src.generation.script_generator.get_episode_repo'):
            with patch('src.generation.script_generator.get_digest_repo'):
                with patch('src.generation.script_generator.get_digest_episode_link_repo'):
                    with patch('src.generation.script_generator.WebConfigManager'):
                        with patch('src.generation.script_generator.ConfigManager'):
                            with patch('src.generation.script_generator.AdFilter'):
                                generator = ScriptGenerator()
                                generator.story_arc_repo = mock_arc_repo

                                # Test context retrieval
                                context = generator._get_recent_story_arc_context(
                                    "AI and Technology", days_back=7
                                )

                                # Verify
                                self.assertIn("STORY ARC INTEGRATION", context)
                                self.assertIn("OpenAI Leadership", context)

    def test_repetition_check(self):
        """Test story arc overlap detection for repetition avoidance"""
        # Mock story arc repository with high overlap
        mock_arc_repo = Mock()
        mock_arc_repo.get_active_story_arcs.return_value = [
            {'arc_name': 'openai-leadership'},
            {'arc_name': 'gpt-5-release'},
        ]
        mock_arc_repo.get_recently_included_arcs.return_value = [
            {'arc_name': 'openai-leadership'},
            {'arc_name': 'gpt-5-release'},
        ]

        from src.generation.script_generator import ScriptGenerator

        with patch('src.generation.script_generator.get_episode_repo'):
            with patch('src.generation.script_generator.get_digest_repo'):
                with patch('src.generation.script_generator.get_digest_episode_link_repo'):
                    with patch('src.generation.script_generator.WebConfigManager'):
                        with patch('src.generation.script_generator.ConfigManager'):
                            with patch('src.generation.script_generator.AdFilter'):
                                generator = ScriptGenerator()
                                generator.story_arc_repo = mock_arc_repo
                                generator.web_config = Mock()
                                generator.web_config.get_setting.return_value = 14

                                mock_episode = Mock()
                                mock_episode.id = 1
                                episodes = [mock_episode]

                                is_repetitive, msg, covered = generator._check_topic_repetition(
                                    episodes, "AI and Technology"
                                )

                                # Verify - 100% overlap should be flagged
                                self.assertTrue(is_repetitive)
                                self.assertIsInstance(covered, list)


if __name__ == '__main__':
    unittest.main()
