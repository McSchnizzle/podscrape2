#!/usr/bin/env python3
"""
Phase 1 Testing Suite: Foundation & Data Layer
Tests database schema, configuration management, and logging infrastructure.
"""

import sys
import os
import json
import tempfile
import logging
from pathlib import Path
from datetime import datetime, date
from typing import List, Dict

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from database.models import (
    get_database_manager, get_channel_repo, get_episode_repo, get_digest_repo,
    Channel, Episode, Digest, DatabaseManager
)
from utils.config import get_config_manager, TopicConfig, ChannelConfig, validate_environment
from utils.logging_config import setup_logging, get_logger
from utils.error_handling import (
    DigestSystemError, DatabaseError, ConfigurationError,
    system_health_check, error_tracker
)

class Phase1TestSuite:
    """Comprehensive test suite for Phase 1 components"""
    
    def __init__(self):
        self.test_results = []
        self.temp_dir = None
        self.logger = None
        
    def setup(self):
        """Set up test environment"""
        print("🔧 Setting up Phase 1 test environment...")
        
        # Create temporary directory for test files
        self.temp_dir = Path(tempfile.mkdtemp())
        print(f"Test directory: {self.temp_dir}")
        
        # Set up logging
        log_dir = self.temp_dir / 'logs'
        logging_manager = setup_logging(str(log_dir), 'DEBUG')
        self.logger = get_logger('test_phase1')
        
        self.logger.info("Phase 1 test suite initialized")
        
    def teardown(self):
        """Clean up test environment"""
        if self.temp_dir and self.temp_dir.exists():
            import shutil
            shutil.rmtree(self.temp_dir)
        print("🧹 Test environment cleaned up")
    
    def run_test(self, test_name: str, test_func):
        """Run a single test with error handling"""
        print(f"\n🧪 Running test: {test_name}")
        self.logger.info(f"Starting test: {test_name}")
        
        try:
            test_func()
            self.test_results.append({'name': test_name, 'status': 'PASS', 'error': None})
            print(f"  ✅ {test_name} - PASSED")
            self.logger.info(f"Test passed: {test_name}")
            
        except Exception as e:
            self.test_results.append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
            print(f"  ❌ {test_name} - FAILED: {e}")
            self.logger.error(f"Test failed: {test_name} - {e}", exc_info=True)
    
    def test_database_schema_creation(self):
        """Test database schema creation and table structure"""
        db_path = self.temp_dir / 'test_schema.db'
        db_manager = DatabaseManager(str(db_path))
        
        # Test database file creation
        assert db_path.exists(), "Database file not created"
        
        # Test table existence
        with db_manager.get_connection() as conn:
            tables_query = "SELECT name FROM sqlite_master WHERE type='table'"
            tables = [row[0] for row in conn.execute(tables_query).fetchall()]
            
            required_tables = ['channels', 'episodes', 'digests', 'system_metadata']
            for table in required_tables:
                assert table in tables, f"Required table {table} not found"
            
            # Test indexes
            indexes_query = "SELECT name FROM sqlite_master WHERE type='index'"
            indexes = [row[0] for row in conn.execute(indexes_query).fetchall()]
            assert len(indexes) > 0, "No indexes found"
            
            # Test views
            views_query = "SELECT name FROM sqlite_master WHERE type='view'"
            views = [row[0] for row in conn.execute(views_query).fetchall()]
            expected_views = ['active_channels', 'recent_episodes', 'scored_episodes', 'digest_stats']
            for view in expected_views:
                assert view in views, f"Required view {view} not found"
            
            # Test schema version
            metadata_query = "SELECT value FROM system_metadata WHERE key = 'schema_version'"
            version = conn.execute(metadata_query).fetchone()[0]
            assert version == '1.0', f"Unexpected schema version: {version}"
    
    def test_database_crud_operations(self):
        """Test database CRUD operations for all models"""
        db_path = self.temp_dir / 'test_crud.db'
        db_manager = DatabaseManager(str(db_path))
        
        channel_repo = get_channel_repo(db_manager)
        episode_repo = get_episode_repo(db_manager)
        digest_repo = get_digest_repo(db_manager)
        
        # Test Channel CRUD
        test_channel = Channel(
            channel_id="UC12345TEST",
            channel_name="Test Channel",
            channel_url="https://youtube.com/@testchannel"
        )
        
        # Create
        channel_id = channel_repo.create(test_channel)
        assert channel_id > 0, "Channel creation failed"
        
        # Read
        retrieved_channel = channel_repo.get_by_id("UC12345TEST")
        assert retrieved_channel is not None, "Channel retrieval failed"
        assert retrieved_channel.channel_name == "Test Channel", "Channel data mismatch"
        
        # Update
        channel_repo.update_last_checked("UC12345TEST")
        updated_channel = channel_repo.get_by_id("UC12345TEST")
        assert updated_channel.last_checked is not None, "Channel update failed"
        
        # Test Episode CRUD
        test_episode = Episode(
            video_id="VIDEO123TEST",
            channel_id="UC12345TEST",
            title="Test Video",
            published_date=datetime.now(),
            duration_seconds=300
        )
        
        # Create
        episode_id = episode_repo.create(test_episode)
        assert episode_id > 0, "Episode creation failed"
        
        # Read
        retrieved_episode = episode_repo.get_by_video_id("VIDEO123TEST")
        assert retrieved_episode is not None, "Episode retrieval failed"
        assert retrieved_episode.title == "Test Video", "Episode data mismatch"
        
        # Update
        episode_repo.update_status("VIDEO123TEST", "transcribed")
        updated_episode = episode_repo.get_by_video_id("VIDEO123TEST")
        assert updated_episode.status == "transcribed", "Episode status update failed"
        
        # Test scores update
        test_scores = {"AI News": 0.85, "Tech News": 0.45}
        episode_repo.update_scores("VIDEO123TEST", test_scores)
        scored_episode = episode_repo.get_by_video_id("VIDEO123TEST")
        assert scored_episode.scores == test_scores, "Episode scores update failed"
        
        # Test Digest CRUD
        test_digest = Digest(
            topic="AI News",
            digest_date=date.today(),
            episode_ids=[episode_id],
            episode_count=1
        )
        
        # Create
        digest_id = digest_repo.create(test_digest)
        assert digest_id > 0, "Digest creation failed"
        
        # Read
        retrieved_digest = digest_repo.get_by_topic_date("AI News", date.today())
        assert retrieved_digest is not None, "Digest retrieval failed"
        assert retrieved_digest.episode_count == 1, "Digest data mismatch"
    
    def test_configuration_management(self):
        """Test configuration loading, validation, and saving"""
        config_dir = self.temp_dir / 'config'
        config_manager = get_config_manager(str(config_dir))
        
        # Test default config creation
        assert (config_dir / 'topics.json').exists(), "Default topics.json not created"
        assert (config_dir / 'channels.json').exists(), "Default channels.json not created"
        
        # Test topic loading
        topics = config_manager.load_topics()
        assert len(topics) > 0, "No topics loaded"
        assert all(isinstance(t, TopicConfig) for t in topics), "Invalid topic objects"
        
        # Test topic validation
        for topic in topics:
            assert topic.name, "Topic name is empty"
            assert topic.instruction_file, "Topic instruction_file is empty"
            assert topic.voice_id, "Topic voice_id is empty"
        
        # Test channel operations
        initial_channels = config_manager.load_channels()
        initial_count = len(initial_channels)
        
        # Add channel
        success = config_manager.add_channel(
            "Test Channel",
            "UC123456789TEST",
            "https://youtube.com/@testchannel",
            "Test description"
        )
        assert success, "Channel addition failed"
        
        # Verify addition
        updated_channels = config_manager.load_channels()
        assert len(updated_channels) == initial_count + 1, "Channel count mismatch after addition"
        
        # Test channel retrieval
        test_channel = config_manager.get_channel_config("UC123456789TEST")
        assert test_channel is not None, "Added channel not found"
        assert test_channel.name == "Test Channel", "Channel data mismatch"
        
        # Remove channel
        success = config_manager.remove_channel("UC123456789TEST")
        assert success, "Channel removal failed"
        
        # Verify removal
        final_channels = config_manager.load_channels()
        assert len(final_channels) == initial_count, "Channel count mismatch after removal"
        
        # Test settings loading
        topic_settings = config_manager.get_settings('topics')
        assert 'score_threshold' in topic_settings, "Topic settings not loaded"
        
        channel_settings = config_manager.get_settings('channels')
        assert 'min_video_duration_seconds' in channel_settings, "Channel settings not loaded"
    
    def test_logging_functionality(self):
        """Test logging infrastructure and handlers"""
        # Test basic logging
        test_logger = get_logger('test_logger')
        test_logger.info("Test info message")
        test_logger.warning("Test warning message")
        test_logger.error("Test error message")
        
        # Test log file creation
        log_dir = self.temp_dir / 'logs'
        log_files = list(log_dir.glob('*.log'))
        assert len(log_files) > 0, "No log files created"
        
        # Test structured logging
        structured_logs = list(log_dir.glob('*structured*.log'))
        assert len(structured_logs) > 0, "Structured log file not created"
        
        # Test error logging
        error_logs = list(log_dir.glob('*error*.log'))
        assert len(error_logs) > 0, "Error log file not created"
        
        # Test log content
        main_log = log_dir / 'digest.log'
        if main_log.exists():
            with open(main_log, 'r') as f:
                content = f.read()
                assert "Test info message" in content, "Log message not found in file"
        
        # Test performance logging
        from utils.logging_config import PerformanceLogger
        perf_logger = PerformanceLogger("test_operation", test_logger)
        
        with perf_logger:
            # Simulate some work
            import time
            time.sleep(0.1)
        
        # Performance log should be recorded
        assert True  # If we get here without exception, performance logging works
    
    def test_error_handling(self):
        """Test error handling utilities and custom exceptions"""
        from utils.error_handling import (
            retry_with_backoff, safe_operation, 
            handle_graceful_degradation, validate_required_fields
        )
        
        # Test custom exceptions
        try:
            raise DatabaseError("Test database error")
        except DigestSystemError as e:
            assert isinstance(e, DatabaseError), "Custom exception inheritance failed"
        
        # Test retry decorator
        call_count = 0
        
        @retry_with_backoff(max_attempts=3, base_delay=0.01)
        def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Simulated failure")
            return "success"
        
        result = failing_function()
        assert result == "success", "Retry decorator failed"
        assert call_count == 3, f"Unexpected retry count: {call_count}"
        
        # Test safe operation context manager
        with safe_operation("test_operation", self.logger, reraise=False) as op:
            # This should not raise
            pass
        
        # Test validation utilities
        try:
            validate_required_fields({}, ["required_field"], "test context")
            assert False, "Validation should have failed"
        except ConfigurationError:
            pass  # Expected
        
        # Test error tracker
        error_tracker.record_error("TestError", "test_context")
        assert error_tracker.error_counts.get("TestError:test_context", 0) > 0, "Error tracking failed"
    
    def test_health_check(self):
        """Test system health check functionality"""
        # Set temporary environment variables for test
        os.environ['OPENAI_API_KEY'] = 'test_key_123456789'
        os.environ['ELEVENLABS_API_KEY'] = 'test_key_123456789'  
        os.environ['GITHUB_TOKEN'] = 'test_token_123456789'
        
        try:
            health_status = system_health_check()
            
            assert 'timestamp' in health_status, "Health check missing timestamp"
            assert 'status' in health_status, "Health check missing status"
            assert 'checks' in health_status, "Health check missing checks"
            
            # Database check should pass (we have a test database)
            assert 'database' in health_status['checks'], "Database check missing"
            
            # Configuration check should pass
            assert 'configuration' in health_status['checks'], "Configuration check missing"
            
            # Logging check should pass
            assert 'logging' in health_status['checks'], "Logging check missing"
            
        finally:
            # Clean up environment variables
            for key in ['OPENAI_API_KEY', 'ELEVENLABS_API_KEY', 'GITHUB_TOKEN']:
                if key in os.environ:
                    del os.environ[key]
    
    def test_integration_flow(self):
        """Test integration between database, config, and logging"""
        # This test validates that all components work together
        
        # Set up database
        db_path = self.temp_dir / 'integration_test.db'
        db_manager = DatabaseManager(str(db_path))
        
        # Set up config
        config_dir = self.temp_dir / 'integration_config'
        config_manager = get_config_manager(str(config_dir))
        
        # Add test channel via config
        config_manager.add_channel(
            "Integration Test Channel",
            "UC_INTEGRATION_TEST",
            "https://youtube.com/@integration"
        )
        
        # Verify channel in config
        channels = config_manager.load_channels()
        test_channel_config = next(
            (c for c in channels if c.channel_id == "UC_INTEGRATION_TEST"), None
        )
        assert test_channel_config is not None, "Channel not found in config"
        
        # Add channel to database
        channel_repo = get_channel_repo(db_manager)
        db_channel = Channel(
            channel_id=test_channel_config.channel_id,
            channel_name=test_channel_config.name,
            channel_url=test_channel_config.url
        )
        channel_repo.create(db_channel)
        
        # Verify channel in database
        retrieved_channel = channel_repo.get_by_id("UC_INTEGRATION_TEST")
        assert retrieved_channel is not None, "Channel not found in database"
        
        # Test logging throughout
        integration_logger = get_logger('integration_test')
        integration_logger.info("Integration test completed successfully")
        
        # Verify log was written
        log_dir = self.temp_dir / 'logs'
        log_files = list(log_dir.glob('*.log'))
        assert len(log_files) > 0, "Integration test logs not created"
    
    def run_all_tests(self):
        """Run all Phase 1 tests"""
        print("\n🚀 Starting Phase 1 Test Suite: Foundation & Data Layer")
        print("=" * 60)
        
        self.setup()
        
        try:
            # Core functionality tests
            self.run_test("Database Schema Creation", self.test_database_schema_creation)
            self.run_test("Database CRUD Operations", self.test_database_crud_operations)
            self.run_test("Configuration Management", self.test_configuration_management)
            self.run_test("Logging Functionality", self.test_logging_functionality)
            self.run_test("Error Handling", self.test_error_handling)
            self.run_test("Health Check", self.test_health_check)
            self.run_test("Integration Flow", self.test_integration_flow)
            
            # Generate test report
            self.generate_report()
            
        finally:
            self.teardown()
    
    def generate_report(self):
        """Generate and display test report"""
        print("\n📊 Phase 1 Test Results")
        print("=" * 40)
        
        passed = sum(1 for result in self.test_results if result['status'] == 'PASS')
        failed = sum(1 for result in self.test_results if result['status'] == 'FAIL')
        total = len(self.test_results)
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Success Rate: {(passed/total)*100:.1f}%")
        
        if failed > 0:
            print(f"\n❌ Failed Tests:")
            for result in self.test_results:
                if result['status'] == 'FAIL':
                    print(f"  - {result['name']}: {result['error']}")
        
        # Overall status
        if failed == 0:
            print(f"\n✅ Phase 1: Foundation & Data Layer - ALL TESTS PASSED")
            print("Ready to proceed to Phase 2: Channel Management & Discovery")
            return True
        else:
            print(f"\n❌ Phase 1: Foundation & Data Layer - {failed} TESTS FAILED")
            print("Please fix failing tests before proceeding to Phase 2")
            return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Phase 1 Test Suite")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Configure logging level based on verbose flag
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    
    # Run test suite
    test_suite = Phase1TestSuite()
    success = test_suite.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)