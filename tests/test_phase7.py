#!/usr/bin/env python3
"""
Phase 7 Test Suite: Publishing Pipeline
Tests GitHub publishing, RSS generation, retention management, and Vercel deployment
"""

import os
import sys
import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, date, timedelta
from unittest.mock import Mock, patch, MagicMock

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.publishing.github_publisher import GitHubPublisher, create_github_publisher, GitHubRelease
from src.publishing.rss_generator import RSSGenerator, create_rss_generator, create_podcast_metadata, PodcastEpisode
from src.publishing.retention_manager import RetentionManager, create_retention_manager, RetentionPolicy
from src.publishing.vercel_deployer import VercelDeployer, create_vercel_deployer, DeploymentResult

class TestGitHubPublisher(unittest.TestCase):
    """Test GitHub publisher functionality"""
    
    def setUp(self):
        """Set up test environment"""
        # Mock GitHub API responses
        self.mock_response = Mock()
        self.mock_response.status_code = 200
        self.mock_response.json.return_value = {
            'id': 123456,
            'tag_name': 'daily-2024-12-10',
            'name': 'Daily Digest - December 10, 2024',
            'body': 'Test release',
            'created_at': '2024-12-10T12:00:00Z',
            'published_at': '2024-12-10T12:00:00Z',
            'assets': [],
            'upload_url': 'https://uploads.github.com/repos/test/test/releases/123456/assets{?name,label}'
        }
    
    @patch.dict(os.environ, {'GITHUB_TOKEN': 'test_token', 'GITHUB_REPOSITORY': 'test/test'})
    def test_github_publisher_initialization(self):
        """Test GitHub publisher initialization"""
        publisher = create_github_publisher()
        
        self.assertIsNotNone(publisher)
        self.assertEqual(publisher.github_token, 'test_token')
        self.assertEqual(publisher.repository, 'test/test')
        self.assertIn('Authorization', publisher.headers)
    
    def test_github_publisher_missing_token(self):
        """Test GitHub publisher fails without token"""
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(Exception):
                create_github_publisher()
    
    @patch('src.publishing.github_publisher.requests.request')
    @patch.dict(os.environ, {'GITHUB_TOKEN': 'test_token', 'GITHUB_REPOSITORY': 'test/test'})
    def test_create_release(self, mock_request):
        """Test creating a GitHub release"""
        mock_request.return_value = self.mock_response
        
        publisher = create_github_publisher()
        
        # Create temporary MP3 files for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            mp3_files = []
            for i in range(2):
                mp3_file = Path(temp_dir) / f"test_{i}.mp3"
                mp3_file.write_bytes(b"fake mp3 content")
                mp3_files.append(str(mp3_file))
            
            # Mock the upload response
            upload_response = Mock()
            upload_response.status_code = 201
            upload_response.raise_for_status.return_value = None
            
            with patch('src.publishing.github_publisher.requests.post', return_value=upload_response):
                result = publisher.create_daily_release(date(2024, 12, 10), mp3_files)
                
                self.assertIsInstance(result, GitHubRelease)
                self.assertEqual(result.tag_name, 'daily-2024-12-10')
                self.assertEqual(result.name, 'Daily Digest - December 10, 2024')
    
    @patch('src.publishing.github_publisher.requests.request')
    @patch.dict(os.environ, {'GITHUB_TOKEN': 'test_token', 'GITHUB_REPOSITORY': 'test/test'})
    def test_list_releases(self, mock_request):
        """Test listing GitHub releases"""
        mock_request.return_value.json.return_value = [self.mock_response.json()]
        mock_request.return_value.status_code = 200
        
        publisher = create_github_publisher()
        releases = publisher.list_releases()
        
        self.assertEqual(len(releases), 1)
        self.assertIsInstance(releases[0], GitHubRelease)


class TestRSSGenerator(unittest.TestCase):
    """Test RSS generator functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.metadata = create_podcast_metadata(
            title="Test Podcast",
            description="Test podcast description",
            author="Test Author",
            email="test@example.com",
            website_url="https://example.com",
            image_url="https://example.com/image.jpg"
        )
        
        self.test_episodes = [
            PodcastEpisode(
                title="Test Episode 1",
                description="First test episode",
                audio_url="https://example.com/episode1.mp3",
                pub_date=datetime(2024, 12, 10, 12, 0, 0),
                duration_seconds=1200,
                file_size=9600000,
                guid="episode-1"
            ),
            PodcastEpisode(
                title="Test Episode 2",
                description="Second test episode",
                audio_url="https://example.com/episode2.mp3",
                pub_date=datetime(2024, 12, 9, 12, 0, 0),
                duration_seconds=900,
                file_size=7200000,
                guid="episode-2"
            )
        ]
    
    def test_rss_generator_initialization(self):
        """Test RSS generator initialization"""
        generator = create_rss_generator(self.metadata)
        
        self.assertIsNotNone(generator)
        self.assertEqual(generator.metadata.title, "Test Podcast")
        self.assertEqual(generator.metadata.author, "Test Author")
    
    def test_generate_rss_feed(self):
        """Test RSS feed generation"""
        generator = create_rss_generator(self.metadata)
        rss_xml = generator.generate_rss_feed(self.test_episodes)
        
        # Check basic RSS structure
        self.assertIn('<?xml', rss_xml)
        self.assertIn('<rss', rss_xml)
        self.assertIn('<channel>', rss_xml)
        self.assertIn('<item>', rss_xml)
        
        # Check podcast metadata
        self.assertIn('Test Podcast', rss_xml)
        self.assertIn('Test Author', rss_xml)
        self.assertIn('test@example.com', rss_xml)
        
        # Check episodes
        self.assertIn('Test Episode 1', rss_xml)
        self.assertIn('Test Episode 2', rss_xml)
        self.assertIn('episode1.mp3', rss_xml)
        
        # Check iTunes extensions
        self.assertIn('itunes:', rss_xml)
        self.assertIn('itunes:duration', rss_xml)
    
    def test_rss_validation(self):
        """Test RSS feed validation"""
        generator = create_rss_generator(self.metadata)
        rss_xml = generator.generate_rss_feed(self.test_episodes)
        
        # Validate the generated RSS
        is_valid = generator.validate_rss_feed(rss_xml)
        self.assertTrue(is_valid)
    
    def test_invalid_rss_validation(self):
        """Test validation of invalid RSS"""
        generator = create_rss_generator(self.metadata)
        
        invalid_rss = "<html><body>Not RSS</body></html>"
        is_valid = generator.validate_rss_feed(invalid_rss)
        self.assertFalse(is_valid)
    
    def test_duration_formatting(self):
        """Test duration formatting"""
        generator = create_rss_generator(self.metadata)
        
        # Test various durations
        self.assertEqual(generator._format_duration(90), "01:30")
        self.assertEqual(generator._format_duration(3661), "01:01:01")
        self.assertEqual(generator._format_duration(45), "00:45")
    
    def test_rss_feed_save(self):
        """Test saving RSS feed to file"""
        generator = create_rss_generator(self.metadata)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test_feed.xml"
            rss_xml = generator.generate_rss_feed(self.test_episodes, str(output_path))
            
            # Check file was created
            self.assertTrue(output_path.exists())
            
            # Check file content
            with open(output_path, 'r', encoding='utf-8') as f:
                saved_content = f.read()
            
            self.assertEqual(rss_xml, saved_content)
            self.assertIn('Test Podcast', saved_content)


class TestRetentionManager(unittest.TestCase):
    """Test retention manager functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = Path(tempfile.mkdtemp())
        
        # Create test retention policies
        self.test_policies = [
            RetentionPolicy(
                name="Test MP3s",
                path_pattern=str(self.temp_dir / "mp3s"),
                retention_days=7,
                file_pattern="*.mp3"
            ),
            RetentionPolicy(
                name="Test Logs",
                path_pattern=str(self.temp_dir / "logs"),
                retention_days=3,
                file_pattern="*.log"
            )
        ]
    
    def tearDown(self):
        """Clean up test environment"""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_retention_manager_initialization(self):
        """Test retention manager initialization"""
        with patch.dict(os.environ, {'GITHUB_TOKEN': 'test', 'GITHUB_REPOSITORY': 'test/test'}):
            manager = create_retention_manager(self.test_policies, None)
            
            self.assertIsNotNone(manager)
            self.assertEqual(len(manager.retention_policies), 2)
            self.assertEqual(manager.retention_policies[0].name, "Test MP3s")
    
    def _create_test_files(self):
        """Helper method to create test files with different ages"""
        # Create directories
        (self.temp_dir / "mp3s").mkdir(parents=True, exist_ok=True)
        (self.temp_dir / "logs").mkdir(parents=True, exist_ok=True)
        
        # Create old files (should be deleted)
        old_mp3 = self.temp_dir / "mp3s" / "old.mp3"
        old_mp3.write_text("old mp3")
        old_time = datetime.now() - timedelta(days=10)
        os.utime(old_mp3, (old_time.timestamp(), old_time.timestamp()))
        
        old_log = self.temp_dir / "logs" / "old.log"
        old_log.write_text("old log")
        os.utime(old_log, (old_time.timestamp(), old_time.timestamp()))
        
        # Create recent files (should be kept)
        recent_mp3 = self.temp_dir / "mp3s" / "recent.mp3"
        recent_mp3.write_text("recent mp3")
        
        recent_log = self.temp_dir / "logs" / "recent.log"
        recent_log.write_text("recent log")
        
        return [old_mp3, old_log, recent_mp3, recent_log]
    
    def test_cleanup_dry_run(self):
        """Test cleanup in dry run mode"""
        files = self._create_test_files()
        with patch.dict(os.environ, {'GITHUB_TOKEN': 'test', 'GITHUB_REPOSITORY': 'test/test'}):
            manager = create_retention_manager(self.test_policies, None)
            
            stats = manager.run_cleanup(dry_run=True)
            
            # Check that no files were actually deleted
            self.assertTrue(all(f.exists() for f in files))
            
            # Check stats
            self.assertEqual(stats.files_deleted, 2)  # 2 old files would be deleted
            self.assertTrue(stats.bytes_freed > 0)
    
    def test_cleanup_real(self):
        """Test actual cleanup"""
        files = self._create_test_files()
        old_mp3, old_log, recent_mp3, recent_log = files
        
        with patch.dict(os.environ, {'GITHUB_TOKEN': 'test', 'GITHUB_REPOSITORY': 'test/test'}):
            manager = create_retention_manager(self.test_policies, None)
            
            stats = manager.run_cleanup(dry_run=False)
            
            # Check that old files were deleted
            self.assertFalse(old_mp3.exists())
            self.assertFalse(old_log.exists())
            
            # Check that recent files were kept
            self.assertTrue(recent_mp3.exists())
            self.assertTrue(recent_log.exists())
            
            # Check stats
            self.assertEqual(stats.files_deleted, 2)
            self.assertTrue(stats.bytes_freed > 0)
    
    def test_disk_usage_stats(self):
        """Test disk usage statistics"""
        self._create_test_files()
        with patch.dict(os.environ, {'GITHUB_TOKEN': 'test', 'GITHUB_REPOSITORY': 'test/test'}):
            manager = create_retention_manager(self.test_policies, None)
            
            stats = manager.get_disk_usage_stats()
            
            self.assertIn("Test MP3s", stats)
            self.assertIn("Test Logs", stats)
            
            mp3_stats = stats["Test MP3s"]
            self.assertEqual(mp3_stats['file_count'], 2)
            self.assertTrue(mp3_stats['total_size'] > 0)
    
    def test_cleanup_specific_date(self):
        """Test cleanup for specific date"""
        # Create files with date in name
        (self.temp_dir / "mp3s").mkdir(parents=True, exist_ok=True)
        
        test_date = date(2024, 12, 10)
        date_str = test_date.strftime('%Y%m%d')
        
        dated_file = self.temp_dir / "mp3s" / f"episode_{date_str}.mp3"
        dated_file.write_text("dated content")
        
        other_file = self.temp_dir / "mp3s" / "other_episode.mp3"
        other_file.write_text("other content")
        
        with patch.dict(os.environ, {'GITHUB_TOKEN': 'test', 'GITHUB_REPOSITORY': 'test/test'}):
            manager = create_retention_manager(self.test_policies, None)
            
            stats = manager.cleanup_specific_date(test_date, dry_run=False)
            
            # Check that dated file was deleted
            self.assertFalse(dated_file.exists())
            
            # Check that other file was kept
            self.assertTrue(other_file.exists())
            
            # Check stats
            self.assertEqual(stats.files_deleted, 1)


class TestVercelDeployer(unittest.TestCase):
    """Test Vercel deployer functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Test Podcast</title>
<description>Test Description</description>
<link>https://example.com</link>
</channel>
</rss>"""
    
    @patch('subprocess.run')
    def test_vercel_cli_verification(self, mock_run):
        """Test Vercel CLI verification"""
        # Mock successful verification
        mock_run.side_effect = [
            Mock(returncode=0, stdout="/usr/local/bin/vercel"),  # which vercel
            Mock(returncode=0, stdout="testuser\n")  # vercel whoami
        ]
        
        deployer = create_vercel_deployer("test-project")
        self.assertIsNotNone(deployer)
        self.assertEqual(deployer.project_name, "test-project")
    
    @patch('subprocess.run')
    def test_vercel_cli_not_found(self, mock_run):
        """Test error when Vercel CLI not found"""
        mock_run.return_value = Mock(returncode=1, stdout="")
        
        with self.assertRaises(Exception) as context:
            create_vercel_deployer()
        
        self.assertIn("Vercel CLI not found", str(context.exception))
    
    @patch('subprocess.run')
    def test_deployment_structure_creation(self, mock_run):
        """Test deployment structure creation"""
        # Mock CLI verification
        mock_run.side_effect = [
            Mock(returncode=0, stdout="/usr/local/bin/vercel"),  # which vercel
            Mock(returncode=0, stdout="testuser\n")  # vercel whoami
        ]
        
        deployer = create_vercel_deployer()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            deployer._create_deployment_structure(temp_path, self.test_rss)
            
            # Check files were created
            self.assertTrue((temp_path / "public" / "daily-digest2.xml").exists())
            self.assertTrue((temp_path / "public" / "index.html").exists())
            self.assertTrue((temp_path / "vercel.json").exists())
            
            # Check RSS content
            rss_content = (temp_path / "public" / "daily-digest2.xml").read_text()
            self.assertEqual(rss_content, self.test_rss)
            
            # Check vercel.json
            vercel_config = json.loads((temp_path / "vercel.json").read_text())
            self.assertIn("routes", vercel_config)
            self.assertIn("headers", vercel_config)
    
    @patch('subprocess.run')
    @patch('requests.get')
    def test_deployment_validation(self, mock_get, mock_run):
        """Test deployment validation"""
        # Mock CLI verification
        mock_run.side_effect = [
            Mock(returncode=0, stdout="/usr/local/bin/vercel"),
            Mock(returncode=0, stdout="testuser\n")
        ]
        
        # Mock successful HTTP request
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'application/rss+xml'}
        mock_response.text = self.test_rss
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        deployer = create_vercel_deployer()
        
        is_valid = deployer.validate_deployment("https://test.example.com/daily-digest2.xml")
        self.assertTrue(is_valid)
    
    @patch('subprocess.run')
    def test_deploy_rss_feed_success(self, mock_run):
        """Test successful RSS feed deployment"""
        # Mock CLI verification and deployment
        mock_run.side_effect = [
            Mock(returncode=0, stdout="/usr/local/bin/vercel"),
            Mock(returncode=0, stdout="testuser\n"),
            Mock(returncode=0, stdout="https://test-deployment.vercel.app\n")  # deploy command
        ]
        
        deployer = create_vercel_deployer()
        
        result = deployer.deploy_rss_feed(self.test_rss, production=False)
        
        self.assertTrue(result.success)
        self.assertIn("vercel.app", result.url)
        self.assertIsNotNone(result.duration_seconds)
    
    @patch('subprocess.run')
    def test_deploy_rss_feed_failure(self, mock_run):
        """Test failed RSS feed deployment"""
        # Mock CLI verification and failed deployment
        mock_run.side_effect = [
            Mock(returncode=0, stdout="/usr/local/bin/vercel"),
            Mock(returncode=0, stdout="testuser\n"),
            Mock(returncode=1, stderr="Deployment failed", stdout="")  # deploy command fails
        ]
        
        deployer = create_vercel_deployer()
        
        result = deployer.deploy_rss_feed(self.test_rss, production=False)
        
        self.assertFalse(result.success)
        self.assertIn("failed", result.error.lower())


class TestPhase7Integration(unittest.TestCase):
    """Integration tests for Phase 7 components"""
    
    def test_end_to_end_publishing_workflow(self):
        """Test the complete publishing workflow"""
        # This would test the integration of all components
        # For now, just verify all components can be imported and created
        
        # Test metadata creation
        metadata = create_podcast_metadata(
            title="Integration Test Podcast",
            description="Test description",
            author="Test Author",
            email="test@example.com"
        )
        
        # Test RSS generator
        generator = create_rss_generator(metadata)
        self.assertIsNotNone(generator)
        
        # Test GitHub publisher (with mocked env vars)
        with patch.dict(os.environ, {'GITHUB_TOKEN': 'test', 'GITHUB_REPOSITORY': 'test/test'}):
            github_publisher = create_github_publisher()
            self.assertIsNotNone(github_publisher)
        
        # Test retention manager
        with patch.dict(os.environ, {'GITHUB_TOKEN': 'test', 'GITHUB_REPOSITORY': 'test/test'}):
            retention_manager = create_retention_manager()
            self.assertIsNotNone(retention_manager)
        
        # Test Vercel deployer
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0, stdout="/usr/local/bin/vercel"),
                Mock(returncode=0, stdout="testuser\n")
            ]
            vercel_deployer = create_vercel_deployer()
            self.assertIsNotNone(vercel_deployer)


def run_phase7_tests():
    """Run all Phase 7 tests"""
    print("🧪 Running Phase 7 Publishing Pipeline Tests")
    print("=" * 60)
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestGitHubPublisher,
        TestRSSGenerator,
        TestRetentionManager,
        TestVercelDeployer,
        TestPhase7Integration
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "=" * 60)
    if result.wasSuccessful():
        print("✅ All Phase 7 tests passed!")
        return True
    else:
        print(f"❌ {len(result.failures)} test(s) failed, {len(result.errors)} error(s)")
        
        # Print failures
        for test, traceback in result.failures:
            print(f"\n❌ FAILED: {test}")
            print(traceback)
        
        # Print errors
        for test, traceback in result.errors:
            print(f"\n💥 ERROR: {test}")
            print(traceback)
        
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Phase 7 Publishing Pipeline Tests")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--test", help="Run specific test class")
    
    args = parser.parse_args()
    
    if args.test:
        # Run specific test class
        suite = unittest.TestSuite()
        test_class = globals().get(args.test)
        if test_class:
            tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
            suite.addTests(tests)
            runner = unittest.TextTestRunner(verbosity=2 if args.verbose else 1)
            result = runner.run(suite)
            sys.exit(0 if result.wasSuccessful() else 1)
        else:
            print(f"Test class '{args.test}' not found")
            sys.exit(1)
    else:
        # Run all tests
        success = run_phase7_tests()
        sys.exit(0 if success else 1)