#!/usr/bin/env python3
"""
Test Suite for Phase 3: Transcript Processing
Tests transcript fetching, storage, validation, and CLI functionality.
"""

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.database.models import get_database_manager, get_episode_repo, Episode
from src.youtube.transcript_processor import (
    TranscriptProcessor, 
    TranscriptPipeline, 
    TranscriptData,
    TranscriptSegment,
    create_transcript_pipeline
)
from src.utils.logging_config import setup_logging

# Test configuration
TEST_VIDEO_ID = "exWEkRHmhKU"  # Matt Wolfe video
FALLBACK_VIDEO_ID = "dQw4w9WgXcQ"  # Rick Roll as fallback (well-known video with transcript)

def setup_test_environment():
    """Set up test environment with logging and test database"""
    setup_logging()
    
    # Use test database
    test_db_path = Path("data/database/test_digest.db")
    test_db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Clean up any existing test database
    if test_db_path.exists():
        test_db_path.unlink()
    
    return str(test_db_path)

def create_test_episode(video_id: str = TEST_VIDEO_ID) -> Episode:
    """Create a test episode for transcript processing"""
    return Episode(
        video_id=video_id,
        channel_id="UChpleBmo18P08aKCIgti38g",
        title="Test Video for Transcript Processing",
        published_date=datetime.now(),
        duration_seconds=1620,
        description="Test video description",
        status='pending'
    )

class TestTranscriptProcessor:
    """Test the TranscriptProcessor class"""
    
    def __init__(self):
        self.temp_dir = None
        self.processor = None
    
    def setup(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.processor = TranscriptProcessor(self.temp_dir)
        print(f"📁 Using temporary transcript directory: {self.temp_dir}")
    
    def teardown(self):
        """Clean up test environment"""
        if self.temp_dir and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
    
    def test_transcript_fetching(self):
        """Test 3.1: Transcript API integration successfully extracts transcripts"""
        print("🧪 Test 3.1: Testing transcript fetching...")
        
        # Try primary video first
        transcript_data = self.processor.fetch_transcript(TEST_VIDEO_ID)
        
        if not transcript_data:
            print(f"⚠️ Primary video {TEST_VIDEO_ID} failed, trying fallback...")
            transcript_data = self.processor.fetch_transcript(FALLBACK_VIDEO_ID)
        
        assert transcript_data is not None, "Failed to fetch transcript from any test video"
        assert transcript_data.video_id in [TEST_VIDEO_ID, FALLBACK_VIDEO_ID], "Wrong video ID in transcript"
        assert transcript_data.word_count > 0, "Transcript has no words"
        assert len(transcript_data.segments) > 0, "Transcript has no segments"
        assert transcript_data.language is not None, "No language detected"
        
        print(f"✅ Successfully fetched transcript: {transcript_data.word_count} words, {len(transcript_data.segments)} segments")
        return transcript_data
    
    def test_transcript_storage(self):
        """Test 3.2: Transcript storage with unique filenames and database references"""
        print("🧪 Test 3.2: Testing transcript storage...")
        
        # Fetch a transcript first
        transcript_data = self.test_transcript_fetching()
        
        # Save transcript
        file_path = self.processor.save_transcript(transcript_data)
        
        assert Path(file_path).exists(), f"Transcript file was not created: {file_path}"
        assert transcript_data.video_id in file_path, "Video ID not in filename"
        
        # Check file contents
        with open(file_path, 'r', encoding='utf-8') as f:
            saved_data = json.load(f)
        
        assert saved_data['video_id'] == transcript_data.video_id, "Video ID mismatch in saved file"
        assert saved_data['word_count'] == transcript_data.word_count, "Word count mismatch in saved file"
        assert len(saved_data['segments']) == len(transcript_data.segments), "Segment count mismatch in saved file"
        
        print(f"✅ Successfully saved transcript to: {Path(file_path).name}")
        return file_path
    
    def test_transcript_loading(self):
        """Test 3.3: Transcript loading from storage"""
        print("🧪 Test 3.3: Testing transcript loading...")
        
        # Save a transcript first
        file_path = self.test_transcript_storage()
        
        # Load it back
        loaded_transcript = self.processor.load_transcript(file_path)
        
        assert loaded_transcript is not None, "Failed to load transcript from file"
        assert loaded_transcript.video_id in [TEST_VIDEO_ID, FALLBACK_VIDEO_ID], "Video ID mismatch in loaded transcript"
        assert loaded_transcript.word_count > 0, "Loaded transcript has no words"
        assert len(loaded_transcript.segments) > 0, "Loaded transcript has no segments"
        
        print(f"✅ Successfully loaded transcript: {loaded_transcript.word_count} words")
        return loaded_transcript
    
    def test_quality_validation(self):
        """Test 3.4: Transcript quality validation identifies good vs poor quality"""
        print("🧪 Test 3.4: Testing quality validation...")
        
        # Test with real transcript
        transcript_data = self.test_transcript_fetching()
        is_valid, reason = self.processor.validate_transcript_quality(transcript_data)
        
        # Real transcripts should generally pass basic validation
        print(f"📊 Real transcript validation: {is_valid} - {reason}")
        
        # Test with synthetic poor quality transcript
        poor_transcript = TranscriptData(
            video_id="test_poor",
            language="en",
            segments=[
                TranscriptSegment("short", 0.0, 1.0),
                TranscriptSegment("text", 1.0, 1.0)
            ],
            total_duration=2.0,
            word_count=2,
            is_auto_generated=True,
            fetch_timestamp=datetime.now()
        )
        
        is_poor_valid, poor_reason = self.processor.validate_transcript_quality(poor_transcript)
        assert not is_poor_valid, "Poor quality transcript should fail validation"
        assert "Word count too low" in poor_reason, f"Expected word count error, got: {poor_reason}"
        
        print(f"✅ Quality validation working: Good transcript assessed, poor transcript rejected")

class TestTranscriptPipeline:
    """Test the complete TranscriptPipeline"""
    
    def __init__(self):
        self.db_path = None
        self.temp_dir = None
        self.pipeline = None
    
    def setup(self):
        """Set up test environment"""
        self.db_path = setup_test_environment()
        self.temp_dir = tempfile.mkdtemp()
        
        # Create database manager and repositories
        db_manager = get_database_manager(self.db_path)
        episode_repo = get_episode_repo(db_manager)
        
        # Create transcript processor and pipeline
        transcript_processor = TranscriptProcessor(self.temp_dir)
        self.pipeline = TranscriptPipeline(episode_repo, transcript_processor)
        
        print(f"📁 Using test database: {self.db_path}")
        print(f"📁 Using temporary transcript directory: {self.temp_dir}")
    
    def teardown(self):
        """Clean up test environment"""
        if self.temp_dir and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
        if self.db_path and Path(self.db_path).exists():
            Path(self.db_path).unlink()
    
    def test_end_to_end_processing(self):
        """Test 3.5: End-to-end pipeline processes videos from discovery to storage"""
        print("🧪 Test 3.5: Testing end-to-end transcript processing...")
        
        # First create a test channel (required for foreign key constraint)
        from src.database.models import Channel, get_channel_repo
        
        channel_repo = get_channel_repo(self.pipeline.episode_repo.db)
        test_channel = Channel(
            channel_id="UChpleBmo18P08aKCIgti38g",
            channel_name="Test Channel",
            channel_url="https://www.youtube.com/channel/UChpleBmo18P08aKCIgti38g",
            active=True
        )
        
        try:
            channel_repo.create(test_channel)
        except Exception:
            # Channel might already exist, that's fine
            pass
        
        # Create test episode
        episode = create_test_episode()
        episode_id = self.pipeline.episode_repo.create(episode)
        
        # Verify episode was created
        created_episode = self.pipeline.episode_repo.get_by_video_id(episode.video_id)
        assert created_episode is not None, "Failed to create test episode"
        assert created_episode.status == 'pending', "Episode should start as pending"
        
        # Process the episode
        success = self.pipeline.process_episode(created_episode)
        
        if not success:
            # Try with fallback video
            print(f"⚠️ Primary video failed, trying fallback video...")
            fallback_episode = create_test_episode(FALLBACK_VIDEO_ID)
            fallback_episode.channel_id = "UChpleBmo18P08aKCIgti38g"  # Use same test channel
            fallback_id = self.pipeline.episode_repo.create(fallback_episode)
            created_fallback = self.pipeline.episode_repo.get_by_video_id(FALLBACK_VIDEO_ID)
            success = self.pipeline.process_episode(created_fallback)
            created_episode = created_fallback
        
        assert success, "Failed to process episode transcript"
        
        # Verify database was updated
        processed_episode = self.pipeline.episode_repo.get_by_video_id(created_episode.video_id)
        assert processed_episode.status == 'transcribed', f"Episode status should be 'transcribed', got: {processed_episode.status}"
        assert processed_episode.transcript_path is not None, "Transcript path should be set"
        assert processed_episode.transcript_word_count > 0, "Word count should be set"
        assert processed_episode.transcript_fetched_at is not None, "Fetch timestamp should be set"
        
        # Verify transcript file exists
        assert Path(processed_episode.transcript_path).exists(), f"Transcript file should exist: {processed_episode.transcript_path}"
        
        print(f"✅ End-to-end processing successful: {processed_episode.transcript_word_count} words saved")
        return processed_episode
    
    def test_retry_logic(self):
        """Test 3.6: Retry logic handles failures and marks episodes appropriately"""
        print("🧪 Test 3.6: Testing retry logic...")
        
        # Create episode with invalid video ID
        invalid_episode = Episode(
            video_id="invalid_video_id_123",
            channel_id="UChpleBmo18P08aKCIgti38g",  # Use existing test channel
            title="Invalid Video for Testing",
            published_date=datetime.now(),
            duration_seconds=300,
            description="Test video with invalid ID",
            status='pending'
        )
        
        episode_id = self.pipeline.episode_repo.create(invalid_episode)
        created_episode = self.pipeline.episode_repo.get_by_video_id(invalid_episode.video_id)
        
        # Process the invalid episode (should fail)
        success = self.pipeline.process_episode(created_episode)
        assert not success, "Processing invalid video should fail"
        
        # Verify failure was recorded
        failed_episode = self.pipeline.episode_repo.get_by_video_id(invalid_episode.video_id)
        assert failed_episode.failure_count > 0, "Failure count should be incremented"
        assert failed_episode.failure_reason is not None, "Failure reason should be recorded"
        
        print(f"✅ Retry logic working: failure recorded with reason: {failed_episode.failure_reason}")
    
    def test_batch_processing(self):
        """Test 3.7: Batch processing handles multiple episodes"""
        print("🧪 Test 3.7: Testing batch processing...")
        
        # Create multiple test episodes
        episodes = []
        for i, video_id in enumerate([TEST_VIDEO_ID, FALLBACK_VIDEO_ID]):
            episode = Episode(
                video_id=f"{video_id}_batch_{i}",
                channel_id="UChpleBmo18P08aKCIgti38g",  # Use existing test channel
                title=f"Batch Test Video {i}",
                published_date=datetime.now(),
                duration_seconds=300 + i * 60,
                description=f"Test video {i} for batch processing",
                status='pending'
            )
            
            # For testing, we'll use valid video IDs but modify them slightly
            # This will cause them to fail, which is fine for testing batch processing
            episode_id = self.pipeline.episode_repo.create(episode)
            episodes.append(episode)
        
        # Process batch
        stats = self.pipeline.process_pending_episodes(limit=len(episodes))
        
        assert stats['total'] == len(episodes), f"Expected {len(episodes)} episodes, got {stats['total']}"
        assert stats['successful'] + stats['failed'] == stats['total'], "Success + Failed should equal total"
        
        print(f"✅ Batch processing completed: {stats['successful']} successful, {stats['failed']} failed")

def run_test_suite():
    """Run the complete Phase 3 test suite"""
    print("🧪 Starting Phase 3 Test Suite: Transcript Processing\n")
    
    test_results = []
    
    # Test TranscriptProcessor
    print("=" * 60)
    print("Testing TranscriptProcessor Class")
    print("=" * 60)
    
    processor_tests = TestTranscriptProcessor()
    processor_tests.setup()
    
    try:
        # Run processor tests
        processor_tests.test_transcript_fetching()
        test_results.append("✅ Test 3.1: Transcript API integration")
        
        processor_tests.test_transcript_storage()
        test_results.append("✅ Test 3.2: Transcript storage system")
        
        processor_tests.test_transcript_loading()
        test_results.append("✅ Test 3.3: Transcript loading system")
        
        processor_tests.test_quality_validation()
        test_results.append("✅ Test 3.4: Quality validation system")
        
    except Exception as e:
        test_results.append(f"❌ TranscriptProcessor test failed: {e}")
        print(f"❌ TranscriptProcessor test failed: {e}")
    finally:
        processor_tests.teardown()
    
    # Test TranscriptPipeline
    print("\n" + "=" * 60)
    print("Testing TranscriptPipeline Integration")
    print("=" * 60)
    
    pipeline_tests = TestTranscriptPipeline()
    pipeline_tests.setup()
    
    try:
        # Run pipeline tests
        pipeline_tests.test_end_to_end_processing()
        test_results.append("✅ Test 3.5: End-to-end processing pipeline")
        
        pipeline_tests.test_retry_logic()
        test_results.append("✅ Test 3.6: Retry logic and error handling")
        
        pipeline_tests.test_batch_processing()
        test_results.append("✅ Test 3.7: Batch processing system")
        
    except Exception as e:
        test_results.append(f"❌ TranscriptPipeline test failed: {e}")
        print(f"❌ TranscriptPipeline test failed: {e}")
    finally:
        pipeline_tests.teardown()
    
    # Summary
    print("\n" + "=" * 60)
    print("Phase 3 Test Results Summary")
    print("=" * 60)
    
    passed_tests = [t for t in test_results if t.startswith("✅")]
    failed_tests = [t for t in test_results if t.startswith("❌")]
    
    for result in test_results:
        print(result)
    
    print(f"\n📊 Test Summary: {len(passed_tests)}/{len(test_results)} tests passed")
    
    if failed_tests:
        print("❌ Some tests failed. Please review the issues above.")
        return False
    else:
        print("🎉 All Phase 3 tests passed! Transcript processing system is ready.")
        return True

if __name__ == "__main__":
    success = run_test_suite()
    sys.exit(0 if success else 1)