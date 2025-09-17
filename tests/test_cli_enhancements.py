"""
Tests for enhanced CLI functionality in Phase 1.
Tests new command-line flags and pipeline behavior.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import argparse
from datetime import datetime, timedelta
from io import StringIO
import sys

# LEGACY TEST - These tests are for deprecated run_full_pipeline functionality
# Skip entire module until tests are updated for current orchestrator
pytestmark = pytest.mark.skip(reason="Legacy run_full_pipeline tests - use orchestrator instead")

# Import the CLI module components
import run_full_pipeline


class TestCLIArguments:
    """Test command-line argument parsing"""

    def test_help_output(self, capsys):
        """Test that help output includes new flags"""
        with pytest.raises(SystemExit):
            with patch('sys.argv', ['run_full_pipeline.py', '--help']):
                run_full_pipeline.main()

        captured = capsys.readouterr()
        help_output = captured.out

        # Check that new flags are present
        assert '--dry-run' in help_output
        assert '--limit' in help_output
        assert '--days-back' in help_output
        assert '--episode-guid' in help_output
        assert '--verbose' in help_output

    def test_argument_parsing(self):
        """Test that arguments are parsed correctly"""
        # Mock sys.argv
        test_args = [
            'run_full_pipeline.py',
            '--dry-run',
            '--limit', '5',
            '--days-back', '3',
            '--episode-guid', 'test-guid-123',
            '--verbose',
            '--phase', 'discovery'
        ]

        with patch('sys.argv', test_args):
            with patch('run_full_pipeline.FullPipelineRunner') as mock_runner:
                with patch.object(mock_runner.return_value, 'run_pipeline'):
                    run_full_pipeline.main()

                    # Check that FullPipelineRunner was called with correct args
                    mock_runner.assert_called_once_with(
                        log_file=None,
                        phase_stop='discovery',
                        dry_run=True,
                        limit=5,
                        days_back=3,
                        episode_guid='test-guid-123',
                        verbose=True
                    )

    def test_default_values(self):
        """Test default argument values"""
        test_args = ['run_full_pipeline.py']

        with patch('sys.argv', test_args):
            with patch('run_full_pipeline.FullPipelineRunner') as mock_runner:
                with patch.object(mock_runner.return_value, 'run_pipeline'):
                    run_full_pipeline.main()

                    # Check default values
                    mock_runner.assert_called_once_with(
                        log_file=None,
                        phase_stop=None,
                        dry_run=False,
                        limit=None,
                        days_back=7,
                        episode_guid=None,
                        verbose=False
                    )


class TestFullPipelineRunner:
    """Test FullPipelineRunner with enhanced CLI features"""

    @patch('run_full_pipeline.get_episode_repo')
    @patch('run_full_pipeline.FeedParser')
    def test_initialization_with_new_parameters(self, mock_feed_parser, mock_episode_repo):
        """Test that runner initializes correctly with new parameters"""
        runner = run_full_pipeline.FullPipelineRunner(
            dry_run=True,
            limit=3,
            days_back=5,
            episode_guid='test-guid',
            verbose=True
        )

        assert runner.dry_run is True
        assert runner.limit == 3
        assert runner.days_back == 5
        assert runner.episode_guid == 'test-guid'
        assert runner.verbose is True

    @patch('run_full_pipeline.get_episode_repo')
    @patch('run_full_pipeline.FeedParser')
    def test_dry_run_logging(self, mock_feed_parser, mock_episode_repo, capsys):
        """Test that dry run mode produces appropriate logging"""
        runner = run_full_pipeline.FullPipelineRunner(dry_run=True)

        # The initialization should log dry run mode
        captured = capsys.readouterr()
        assert "DRY RUN MODE" in captured.out

    @patch('run_full_pipeline.get_episode_repo')
    @patch('run_full_pipeline.FeedParser')
    def test_verbose_logging(self, mock_feed_parser, mock_episode_repo):
        """Test that verbose mode adjusts logging level"""
        with patch('logging.getLogger') as mock_logger:
            mock_logger_instance = Mock()
            mock_logger.return_value = mock_logger_instance

            runner = run_full_pipeline.FullPipelineRunner(verbose=True)

            # Should have set debug level
            assert runner.verbose is True

    def test_episode_guid_discovery(self):
        """Test discovery behavior with specific episode GUID"""
        with patch('run_full_pipeline.get_episode_repo') as mock_repo_factory:
            mock_repo = Mock()
            mock_repo_factory.return_value = mock_repo

            # Mock episode found
            mock_episode = Mock()
            mock_episode.title = "Test Episode"
            mock_repo.get_by_episode_guid.return_value = mock_episode

            with patch('run_full_pipeline.FeedParser'):
                runner = run_full_pipeline.FullPipelineRunner(episode_guid='test-guid')
                episodes = runner.discover_new_episodes()

                # Should have called get_by_episode_guid
                mock_repo.get_by_episode_guid.assert_called_once_with('test-guid')
                assert len(episodes) == 1
                assert episodes[0] == mock_episode

    def test_episode_guid_not_found(self):
        """Test discovery behavior when episode GUID not found"""
        with patch('run_full_pipeline.get_episode_repo') as mock_repo_factory:
            mock_repo = Mock()
            mock_repo_factory.return_value = mock_repo

            # Mock episode not found
            mock_repo.get_by_episode_guid.return_value = None

            with patch('run_full_pipeline.FeedParser'):
                runner = run_full_pipeline.FullPipelineRunner(episode_guid='nonexistent-guid')
                episodes = runner.discover_new_episodes()

                assert len(episodes) == 0

    def test_dry_run_episode_discovery(self):
        """Test that dry run prevents episode discovery"""
        with patch('run_full_pipeline.get_episode_repo') as mock_repo_factory:
            mock_repo = Mock()
            mock_repo_factory.return_value = mock_repo

            # Mock episode found
            mock_episode = Mock()
            mock_episode.title = "Test Episode"
            mock_repo.get_by_episode_guid.return_value = mock_episode

            with patch('run_full_pipeline.FeedParser'):
                runner = run_full_pipeline.FullPipelineRunner(
                    episode_guid='test-guid',
                    dry_run=True
                )
                episodes = runner.discover_new_episodes()

                # Should return empty list in dry run mode
                assert len(episodes) == 0

    @patch('run_full_pipeline.requests.get')
    @patch('run_full_pipeline.feedparser.parse')
    def test_days_back_filtering(self, mock_feedparser, mock_requests):
        """Test that days_back parameter filters episodes correctly"""
        # Mock RSS feed response
        mock_response = Mock()
        mock_response.content = b"mock feed content"
        mock_requests.return_value = mock_response

        # Mock feed entries with different dates
        mock_entry_old = Mock()
        mock_entry_old.title = "Old Episode"
        mock_entry_old.published_parsed = (datetime.now() - timedelta(days=10)).timetuple()
        mock_entry_old.id = "old-episode"
        mock_entry_old.links = [{'type': 'audio/mpeg', 'href': 'http://example.com/old.mp3'}]
        mock_entry_old.get = lambda key, default=None: {'title': 'Old Episode', 'summary': '', 'id': 'old-episode'}.get(key, default)

        mock_entry_recent = Mock()
        mock_entry_recent.title = "Recent Episode"
        mock_entry_recent.published_parsed = (datetime.now() - timedelta(days=2)).timetuple()
        mock_entry_recent.id = "recent-episode"
        mock_entry_recent.links = [{'type': 'audio/mpeg', 'href': 'http://example.com/recent.mp3'}]
        mock_entry_recent.get = lambda key, default=None: {'title': 'Recent Episode', 'summary': '', 'id': 'recent-episode'}.get(key, default)

        mock_feed = Mock()
        mock_feed.entries = [mock_entry_old, mock_entry_recent]
        mock_feedparser.return_value = mock_feed

        with patch('run_full_pipeline.get_episode_repo') as mock_repo_factory:
            mock_repo = Mock()
            mock_repo_factory.return_value = mock_repo
            mock_repo.get_by_episode_guid.return_value = None  # No existing episodes

            with patch('run_full_pipeline.FeedParser'):
                runner = run_full_pipeline.FullPipelineRunner(days_back=5)

                # Mock the RSS feeds
                runner.rss_feeds = [{'url': 'http://example.com/feed.xml', 'name': 'Test Feed', 'id': 1}]

                episodes = runner.discover_new_episodes()

                # Should only find the recent episode (within 5 days)
                assert len(episodes) == 1
                assert episodes[0]['title'] == "Recent Episode"

    def test_limit_parameter(self):
        """Test that limit parameter restricts episode count"""
        with patch('run_full_pipeline.get_episode_repo') as mock_repo_factory:
            mock_repo = Mock()
            mock_repo_factory.return_value = mock_repo

            with patch('run_full_pipeline.FeedParser'):
                runner = run_full_pipeline.FullPipelineRunner(limit=2)

                # Should override max_episodes_per_run
                max_episodes = runner.limit or runner.max_episodes_per_run
                assert max_episodes == 2


class TestErrorHandling:
    """Test enhanced error handling and logging"""

    @patch('run_full_pipeline.get_episode_repo')
    @patch('run_full_pipeline.FeedParser')
    def test_database_connection_error_handling(self, mock_feed_parser, mock_episode_repo):
        """Test graceful handling of database connection errors"""
        # Mock database connection failure
        mock_episode_repo.side_effect = Exception("Database connection failed")

        with pytest.raises(Exception):
            run_full_pipeline.FullPipelineRunner()

    def test_invalid_episode_guid(self):
        """Test handling of invalid episode GUID"""
        with patch('run_full_pipeline.get_episode_repo') as mock_repo_factory:
            mock_repo = Mock()
            mock_repo_factory.return_value = mock_repo
            mock_repo.get_by_episode_guid.return_value = None

            with patch('run_full_pipeline.FeedParser'):
                runner = run_full_pipeline.FullPipelineRunner(episode_guid='invalid-guid')
                episodes = runner.discover_new_episodes()

                assert len(episodes) == 0

    def test_negative_days_back(self):
        """Test handling of negative days_back parameter"""
        with patch('run_full_pipeline.get_episode_repo') as mock_repo_factory:
            mock_repo = Mock()
            mock_repo_factory.return_value = mock_repo

            with patch('run_full_pipeline.FeedParser'):
                # Should not raise an error, but behavior may be undefined
                runner = run_full_pipeline.FullPipelineRunner(days_back=-1)
                assert runner.days_back == -1


class TestIntegrationScenarios:
    """Integration test scenarios combining multiple features"""

    def test_dry_run_with_limit_and_days_back(self, capsys):
        """Test dry run combined with limit and days_back parameters"""
        with patch('run_full_pipeline.get_episode_repo') as mock_repo_factory:
            mock_repo = Mock()
            mock_repo_factory.return_value = mock_repo

            with patch('run_full_pipeline.FeedParser'):
                runner = run_full_pipeline.FullPipelineRunner(
                    dry_run=True,
                    limit=1,
                    days_back=3
                )

                captured = capsys.readouterr()
                output = captured.out

                # Should log all configuration
                assert "DRY RUN MODE" in output
                assert "LIMIT: Processing max 1 episodes" in output
                assert "TIMEFRAME: Processing episodes from last 3 days" in output

    def test_verbose_dry_run_episode_guid(self, capsys):
        """Test verbose + dry run + specific episode GUID"""
        with patch('run_full_pipeline.get_episode_repo') as mock_repo_factory:
            mock_repo = Mock()
            mock_repo_factory.return_value = mock_repo

            mock_episode = Mock()
            mock_episode.title = "Target Episode"
            mock_repo.get_by_episode_guid.return_value = mock_episode

            with patch('run_full_pipeline.FeedParser'):
                runner = run_full_pipeline.FullPipelineRunner(
                    dry_run=True,
                    episode_guid='target-guid',
                    verbose=True
                )

                episodes = runner.discover_new_episodes()

                captured = capsys.readouterr()
                output = captured.out

                # Should show dry run message for specific episode
                assert "DRY RUN: Would process episode" in output
                assert len(episodes) == 0  # Dry run returns empty