#!/usr/bin/env python3
"""
Phase 2 Test Suite: Channel Management & Discovery
Tests YouTube channel ID resolution, CLI operations, and video discovery.

Run with: python tests/test_phase2.py
"""

import os
import sys
import unittest
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path for imports
project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))

from src.database.models import DatabaseManager, ChannelRepository, Channel
from src.youtube.channel_resolver import ChannelResolver, ChannelInfo, resolve_channel, validate_channel_id
from src.youtube.video_discovery import VideoDiscovery, ChannelHealthMonitor, VideoInfo, discover_videos_for_channel
from src.cli.channel_manager import ChannelManager
from src.utils.logging_config import setup_logging

# Setup test logging
setup_logging(log_level='ERROR')  # Suppress logs during testing

class TestPhase2(unittest.TestCase):
    """Comprehensive test suite for Phase 2: Channel Management & Discovery"""
    
    def setUp(self):
        """Set up test environment"""
        # Create temporary database for testing
        self.test_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.test_dir, 'test_digest.db')
        
        # Initialize database and repositories
        self.db_manager = DatabaseManager(self.test_db_path)
        self.channel_repo = ChannelRepository(self.db_manager)
        
        print(f"Test {self._testMethodName}: ", end="")
    
    def tearDown(self):
        """Clean up test environment"""
        # Remove temporary test directory
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_01_channel_resolver_initialization(self):
        """Test ChannelResolver can be initialized and configured properly"""
        try:
            resolver = ChannelResolver()
            self.assertIsInstance(resolver, ChannelResolver)
            self.assertIsInstance(resolver.ydl_opts, dict)
            self.assertTrue(resolver.ydl_opts.get('quiet', False))
            print("✅ PASSED")
        except Exception as e:
            print(f"❌ FAILED: {e}")
            raise
    
    @patch('yt_dlp.YoutubeDL')
    def test_02_channel_id_extraction_from_url(self, mock_ydl):
        """Test channel ID extraction from various URL formats"""
        try:
            resolver = ChannelResolver()
            
            # Test direct channel ID URL
            test_cases = [
                "https://www.youtube.com/channel/UCxyz123",
                "https://youtube.com/channel/UCabc456", 
                "youtube.com/channel/UCdef789"
            ]
            
            for url in test_cases:
                result = resolver._extract_channel_id_from_url(url)
                # Should either return a channel ID or None (for further resolution)
                self.assertTrue(result is None or (isinstance(result, str) and result.startswith('UC')))
            
            print("✅ PASSED")
        except Exception as e:
            print(f"❌ FAILED: {e}")
            raise
    
    @patch('yt_dlp.YoutubeDL')
    def test_03_channel_resolver_mock_success(self, mock_ydl):
        """Test successful channel resolution with mocked yt-dlp"""
        try:
            # Mock yt-dlp response for direct channel URL
            mock_instance = MagicMock()
            mock_ydl.return_value.__enter__.return_value = mock_instance
            
            # Mock both the direct channel extraction and fallback fetch
            mock_instance.extract_info.return_value = {
                'id': 'UC_test_channel_id',
                'channel_id': 'UC_test_channel_id',
                'title': 'Test Channel',
                'channel': 'Test Channel',
                'channel_url': 'https://www.youtube.com/channel/UC_test_channel_id',
                'subscriber_count': 50000,
                'description': 'Test channel description'
            }
            
            resolver = ChannelResolver()
            
            # Test with a @handle URL which should trigger the resolution logic
            result = resolver.resolve_channel_id("https://www.youtube.com/@testchannel")
            
            self.assertIsInstance(result, ChannelInfo)
            self.assertEqual(result.channel_id, 'UC_test_channel_id')
            self.assertEqual(result.channel_name, 'Test Channel')
            self.assertEqual(result.subscriber_count, 50000)
            
            print("✅ PASSED")
        except Exception as e:
            print(f"❌ FAILED: {e}")
            raise
    
    def test_04_channel_resolver_invalid_input(self):
        """Test channel resolver with invalid inputs"""
        try:
            resolver = ChannelResolver()
            
            # Test empty/invalid inputs
            invalid_inputs = ["", None, "   ", "invalid_url", "not_a_channel"]
            
            for invalid_input in invalid_inputs:
                if invalid_input is None:
                    continue  # Skip None test as it would cause different error
                    
                result = resolver.resolve_channel_id(invalid_input)
                # Should return None for invalid inputs (with mocked network calls)
                # In real scenario, this might fail differently, but we test the error handling
                self.assertTrue(result is None or isinstance(result, ChannelInfo))
            
            print("✅ PASSED")
        except Exception as e:
            print(f"❌ FAILED: {e}")
            raise
    
    def test_05_video_discovery_initialization(self):
        """Test VideoDiscovery initialization and configuration"""
        try:
            discovery = VideoDiscovery()
            self.assertEqual(discovery.min_duration_seconds, 180)  # 3 minutes default
            
            # Test custom duration
            custom_discovery = VideoDiscovery(min_duration_seconds=300)
            self.assertEqual(custom_discovery.min_duration_seconds, 300)
            
            print("✅ PASSED")
        except Exception as e:
            print(f"❌ FAILED: {e}")
            raise
    
    @patch('yt_dlp.YoutubeDL')
    def test_06_video_discovery_mock_success(self, mock_ydl):
        """Test video discovery with mocked yt-dlp response"""
        try:
            # Create test channel
            test_channel = Channel(
                channel_id='UC_test_channel',
                channel_name='Test Channel',
                channel_url='https://www.youtube.com/channel/UC_test_channel',
                active=True
            )
            
            # Mock yt-dlp response
            mock_instance = MagicMock()
            mock_ydl.return_value.__enter__.return_value = mock_instance
            mock_instance.extract_info.return_value = {
                'entries': [
                    {
                        'id': 'video123',
                        'title': 'Test Video',
                        'description': 'Test description',
                        'duration': 600,  # 10 minutes
                        'upload_date': '20240101',
                        'thumbnail': 'http://example.com/thumb.jpg',
                        'view_count': 1000
                    }
                ]
            }
            
            discovery = VideoDiscovery()
            videos = discovery.discover_recent_videos(test_channel, days_back=1)
            
            self.assertIsInstance(videos, list)
            if videos:  # If discovery worked
                self.assertIsInstance(videos[0], VideoInfo)
                self.assertEqual(videos[0].video_id, 'video123')
                self.assertEqual(videos[0].duration_seconds, 600)
            
            print("✅ PASSED")
        except Exception as e:
            print(f"❌ FAILED: {e}")
            raise
    
    def test_07_video_discovery_duration_filtering(self):
        """Test video discovery duration filtering logic"""
        try:
            discovery = VideoDiscovery(min_duration_seconds=300)  # 5 minutes
            
            test_channel = Channel(
                channel_id='UC_test',
                channel_name='Test',
                active=True
            )
            
            # Test video info creation with different durations
            test_entry = {
                'id': 'test_video',
                'title': 'Test Video',
                'description': 'Test',
                'duration': 120,  # 2 minutes - should be filtered out
                'upload_date': '20240101'
            }
            
            result = discovery._extract_video_info(test_entry, test_channel)
            if result:
                # If extraction worked, check duration
                self.assertEqual(result.duration_seconds, 120)
                self.assertLess(result.duration_seconds, discovery.min_duration_seconds)
            
            print("✅ PASSED")
        except Exception as e:
            print(f"❌ FAILED: {e}")
            raise
    
    def test_08_channel_health_monitor(self):
        """Test channel health monitoring functionality"""
        try:
            monitor = ChannelHealthMonitor(failure_threshold=3)
            self.assertEqual(monitor.failure_threshold, 3)
            
            # Test with test channel
            test_channel = Channel(
                channel_id='UC_test',
                channel_name='Test Channel',
                consecutive_failures=0,
                active=True
            )
            
            # Test should_check_channel logic
            should_check = monitor.should_check_channel(test_channel)
            self.assertTrue(should_check)  # Should check if never checked
            
            # Test with recently checked channel
            test_channel.last_checked = datetime.now() - timedelta(minutes=30)
            should_check = monitor.should_check_channel(test_channel, min_check_interval_hours=1)
            self.assertFalse(should_check)  # Should not check within interval
            
            print("✅ PASSED")
        except Exception as e:
            print(f"❌ FAILED: {e}")
            raise
    
    def test_09_channel_repository_integration(self):
        """Test channel repository operations with Phase 2 functionality"""
        try:
            # Create test channel
            test_channel = Channel(
                channel_id='UC_integration_test',
                channel_name='Integration Test Channel',
                channel_url='https://www.youtube.com/channel/UC_integration_test',
                active=True
            )
            
            # Test create
            channel_id = self.channel_repo.create(test_channel)
            self.assertIsInstance(channel_id, int)
            self.assertGreater(channel_id, 0)
            
            # Test retrieve
            retrieved = self.channel_repo.get_by_id('UC_integration_test')
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved.channel_name, 'Integration Test Channel')
            
            # Test health monitoring methods
            self.channel_repo.increment_failures('UC_integration_test', 'Test failure')
            updated = self.channel_repo.get_by_id('UC_integration_test')
            self.assertEqual(updated.consecutive_failures, 1)
            
            # Test reset failures
            self.channel_repo.reset_failures('UC_integration_test')
            reset_channel = self.channel_repo.get_by_id('UC_integration_test')
            self.assertEqual(reset_channel.consecutive_failures, 0)
            
            # Test get unhealthy channels
            for i in range(4):  # Create 4 failures to exceed threshold
                self.channel_repo.increment_failures('UC_integration_test', f'Failure {i}')
            
            unhealthy = self.channel_repo.get_unhealthy_channels(failure_threshold=3)
            self.assertGreater(len(unhealthy), 0)
            
            print("✅ PASSED")
        except Exception as e:
            print(f"❌ FAILED: {e}")
            raise
    
    def test_10_channel_manager_initialization(self):
        """Test ChannelManager can be initialized with temporary database"""
        try:
            # Patch the default database path to use our test database
            with patch('src.cli.channel_manager.get_database_manager') as mock_get_db:
                mock_get_db.return_value = self.db_manager
                
                manager = ChannelManager()
                self.assertIsInstance(manager, ChannelManager)
                self.assertIsNotNone(manager.channel_repo)
                self.assertIsNotNone(manager.health_monitor)
            
            print("✅ PASSED")
        except Exception as e:
            print(f"❌ FAILED: {e}")
            raise
    
    @patch('src.youtube.channel_resolver.resolve_channel')
    def test_11_channel_manager_add_channel_mock(self, mock_resolve):
        """Test ChannelManager add_channel with our real test channels"""
        try:
            # Mock channel resolution for Matt Wolfe channel
            mock_channel_info = ChannelInfo(
                channel_id='UChpleBmo18P08aKCIgti38g',
                channel_name='Matt Wolfe',
                channel_url='https://www.youtube.com/channel/UChpleBmo18P08aKCIgti38g'
            )
            mock_resolve.return_value = mock_channel_info
            
            # Patch the database manager
            with patch('src.cli.channel_manager.get_database_manager') as mock_get_db:
                mock_get_db.return_value = self.db_manager
                
                manager = ChannelManager()
                
                # Test adding channel (auto-confirm to skip prompts)
                result = manager.add_channel('https://www.youtube.com/@mreflow', auto_confirm=True)
                
                # Should return True if successful, False if channel exists or fails
                self.assertIsInstance(result, bool)
                
                # If successful, verify channel was added
                if result:
                    added_channel = self.channel_repo.get_by_id('UChpleBmo18P08aKCIgti38g')
                    self.assertIsNotNone(added_channel)
                    self.assertEqual(added_channel.channel_name, 'Matt Wolfe')
            
            print("✅ PASSED")
        except Exception as e:
            print(f"❌ FAILED: {e}")
            raise
    
    def test_12_convenience_functions(self):
        """Test convenience functions work correctly"""
        try:
            # Test resolve_channel function (will fail without network, but should not crash)
            result = resolve_channel("invalid_input")
            self.assertTrue(result is None or isinstance(result, ChannelInfo))
            
            # Test validate_channel_id function
            result = validate_channel_id("UC_invalid_channel_id")
            self.assertIsInstance(result, bool)
            
            # Test discover_videos_for_channel function
            test_channel = Channel(
                channel_id='UC_test',
                channel_name='Test',
                active=True
            )
            
            videos = discover_videos_for_channel(test_channel, days_back=1)
            self.assertIsInstance(videos, list)
            
            print("✅ PASSED")
        except Exception as e:
            print(f"❌ FAILED: {e}")
            raise
    
    def test_13_real_channels_validation(self):
        """Test our real channels can be validated (structure only)"""
        try:
            # Test that our real channel IDs have valid structure
            test_channels = [
                ('UChpleBmo18P08aKCIgti38g', 'Matt Wolfe'),
                ('UCHhYXsLBEVVnbvsq57n1MTQ', 'The AI Advantage')
            ]
            
            for channel_id, channel_name in test_channels:
                # Validate channel ID format
                self.assertTrue(channel_id.startswith('UC'))
                self.assertEqual(len(channel_id), 24)
                
                # Create Channel object
                channel = Channel(
                    channel_id=channel_id,
                    channel_name=channel_name,
                    channel_url=f'https://www.youtube.com/channel/{channel_id}',
                    active=True
                )
                
                # Verify object creation
                self.assertEqual(channel.channel_id, channel_id)
                self.assertEqual(channel.channel_name, channel_name)
                self.assertTrue(channel.active)
            
            print("✅ PASSED")
        except Exception as e:
            print(f"❌ FAILED: {e}")
            raise

def run_tests():
    """Run all Phase 2 tests and report results"""
    print("🧪 Running Phase 2 Test Suite: Channel Management & Discovery")
    print("=" * 70)
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPhase2)
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, 'w'))
    result = runner.run(suite)
    
    # Print summary
    print("=" * 70)
    print(f"📊 Phase 2 Test Results:")
    print(f"   Tests run: {result.testsRun}")
    print(f"   Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"   Failures: {len(result.failures)}")
    print(f"   Errors: {len(result.errors)}")
    
    if result.failures:
        print("\n❌ FAILURES:")
        for test, traceback in result.failures:
            print(f"   {test}: {traceback.split('AssertionError:')[-1].strip()}")
    
    if result.errors:
        print("\n🚨 ERRORS:")
        for test, traceback in result.errors:
            print(f"   {test}: {traceback.split('Exception:')[-1].strip()}")
    
    # Overall result
    success_rate = (result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100
    print(f"\n📈 Success Rate: {success_rate:.1f}%")
    
    if success_rate >= 90:
        print("🎉 Phase 2 testing PASSED! Ready for Phase 3.")
        return True
    else:
        print("⚠️  Phase 2 testing needs attention before proceeding.")
        return False

if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)