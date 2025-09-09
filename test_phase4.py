#!/usr/bin/env python3
"""
Phase 4 Test Script - GPT-5-mini Content Scoring System

This script provides comprehensive testing for the content scoring system including:
- GPT-5-mini API integration validation
- Database integration testing
- Batch processing validation
- Score accuracy verification
- End-to-end workflow testing

Since GPT-5 API calls may timeout in automated environments, this script is designed
to be run manually with clear output for verification.
"""

import json
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from scoring.content_scorer import ContentScorer, create_content_scorer
from database.models import get_database_manager, get_episode_repo
from utils.logging_config import setup_logging

def test_api_connection():
    """Test GPT-5-mini API connection and basic functionality"""
    print("\n" + "="*60)
    print("TEST 1: GPT-5-mini API Connection")
    print("="*60)
    
    try:
        scorer = create_content_scorer()
        print(f"✅ ContentScorer initialized with {len(scorer.topics)} topics")
        
        # Test with sample text
        sample_text = """
        This is a test podcast transcript about artificial intelligence and machine learning.
        We discuss the latest developments in AI technology, including new language models
        and their impact on the tech industry. The conversation covers community organizing
        around AI ethics and societal changes brought by technological advancement.
        """
        
        print("\n📝 Testing with sample transcript...")
        result = scorer.score_transcript(sample_text, "test-episode")
        
        if result.success:
            print("✅ API call successful!")
            print(f"⏱️  Processing time: {result.processing_time:.2f}s")
            print("📊 Scores received:")
            for topic, score in result.scores.items():
                print(f"   {topic}: {score:.3f}")
            return True
        else:
            print(f"❌ API call failed: {result.error_message}")
            return False
            
    except Exception as e:
        print(f"❌ API connection test failed: {e}")
        return False

def test_database_integration():
    """Test database operations for scoring system"""
    print("\n" + "="*60)
    print("TEST 2: Database Integration")
    print("="*60)
    
    try:
        # Get database connections
        db_manager = get_database_manager()
        episode_repo = get_episode_repo(db_manager)
        
        print("✅ Database connection established")
        
        # Check for existing transcribed episodes
        transcribed_episodes = episode_repo.get_by_status('transcribed')
        print(f"📊 Found {len(transcribed_episodes)} transcribed episodes")
        
        if transcribed_episodes:
            # Test score update for first episode
            test_episode = transcribed_episodes[0]
            print(f"🧪 Testing score update for episode: {test_episode.episode_guid}")
            
            # Create test scores
            test_scores = {
                "AI News": 0.75,
                "Tech News and Tech Culture": 0.85,
                "Community Organizing": 0.45,
                "Societal Culture Change": 0.60
            }
            
            # Update scores in database
            episode_repo.update_scores(test_episode.episode_guid, test_scores)
            print("✅ Test scores updated in database")
            
            # Verify scores were stored correctly
            updated_episode = episode_repo.get_by_episode_guid(test_episode.episode_guid)
            if updated_episode and updated_episode.scores:
                print("✅ Scores retrieved from database:")
                for topic, score in updated_episode.scores.items():
                    print(f"   {topic}: {score}")
                
                # Test topic-based episode retrieval
                qualifying_episodes = episode_repo.get_scored_episodes_for_topic(
                    "Tech News and Tech Culture", min_score=0.65
                )
                print(f"✅ Found {len(qualifying_episodes)} episodes qualifying for 'Tech News and Tech Culture'")
                
                return True
            else:
                print("❌ Failed to retrieve updated scores")
                return False
        else:
            print("⚠️  No transcribed episodes found for testing")
            return True
            
    except Exception as e:
        print(f"❌ Database integration test failed: {e}")
        return False

def test_transcript_file_processing():
    """Test processing of actual transcript files"""
    print("\n" + "="*60)
    print("TEST 3: Transcript File Processing")
    print("="*60)
    
    try:
        # Find transcript files
        transcript_dir = Path("data/transcripts")
        if not transcript_dir.exists():
            print("⚠️  Transcript directory not found, skipping file processing test")
            return True
        
        transcript_files = list(transcript_dir.glob("*.txt"))
        print(f"📁 Found {len(transcript_files)} transcript files")
        
        if not transcript_files:
            print("⚠️  No transcript files found for testing")
            return True
        
        # Test with first transcript file
        test_file = transcript_files[0]
        print(f"📄 Testing with file: {test_file.name}")
        
        # Check file size
        file_size = test_file.stat().st_size
        print(f"📏 File size: {file_size:,} bytes")
        
        # Read and display sample content
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()
            word_count = len(content.split())
            print(f"📝 Word count: {word_count:,} words")
            print(f"📝 First 200 characters: {content[:200]}...")
        
        # Test scoring
        scorer = create_content_scorer()
        print("\n🤖 Scoring transcript with GPT-5-mini...")
        
        result = scorer.score_transcript_file(test_file, test_file.stem)
        
        if result.success:
            print("✅ File processing successful!")
            print(f"⏱️  Processing time: {result.processing_time:.2f}s")
            print("📊 Content scores:")
            for topic, score in result.scores.items():
                emoji = "🎯" if score >= 0.65 else "📉"
                print(f"   {emoji} {topic}: {score:.3f}")
            
            # Check which topics qualify
            qualifying_topics = [topic for topic, score in result.scores.items() if score >= 0.65]
            print(f"\n✅ Qualifies for {len(qualifying_topics)} topics: {', '.join(qualifying_topics)}")
            
            return True
        else:
            print(f"❌ File processing failed: {result.error_message}")
            return False
            
    except Exception as e:
        print(f"❌ Transcript file processing test failed: {e}")
        return False

def test_batch_processing():
    """Test batch processing of multiple episodes"""
    print("\n" + "="*60)
    print("TEST 4: Batch Processing")
    print("="*60)
    
    try:
        # Get database connections
        db_manager = get_database_manager()
        episode_repo = get_episode_repo(db_manager)
        
        # Find episodes with transcripts
        transcribed_episodes = episode_repo.get_by_status('transcribed')
        
        if len(transcribed_episodes) < 2:
            print("⚠️  Need at least 2 transcribed episodes for batch testing")
            return True
        
        # Prepare batch data (limit to 3 episodes for testing)
        test_episodes = transcribed_episodes[:3]
        batch_data = []
        
        for episode in test_episodes:
            if episode.transcript_path and Path(episode.transcript_path).exists():
                batch_data.append((episode.episode_guid, episode.transcript_path))
        
        if not batch_data:
            print("⚠️  No episodes with valid transcript files found")
            return True
        
        print(f"📦 Preparing batch of {len(batch_data)} episodes")
        for episode_id, transcript_path in batch_data:
            print(f"   📄 {episode_id}: {Path(transcript_path).name}")
        
        # Test batch scoring
        scorer = create_content_scorer()
        print(f"\n🤖 Processing batch with GPT-5-mini...")
        
        start_time = time.time()
        results = scorer.batch_score_episodes(batch_data, max_batch_size=2)
        total_time = time.time() - start_time
        
        print(f"⏱️  Total batch processing time: {total_time:.2f}s")
        print(f"📊 Batch results: {len(results)} episodes processed")
        
        # Analyze results
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        print(f"✅ Successful: {len(successful)}")
        print(f"❌ Failed: {len(failed)}")
        
        if successful:
            avg_time = sum(r.processing_time for r in successful) / len(successful)
            print(f"⚡ Average processing time per episode: {avg_time:.2f}s")
            
            # Display top scores for each topic
            print("\n📊 Top scores by topic:")
            all_topics = set()
            for result in successful:
                all_topics.update(result.scores.keys())
            
            for topic in sorted(all_topics):
                scores = [(r.episode_id, r.scores.get(topic, 0.0)) for r in successful]
                scores.sort(key=lambda x: x[1], reverse=True)
                best_episode, best_score = scores[0]
                emoji = "🎯" if best_score >= 0.65 else "📉"
                print(f"   {emoji} {topic}: {best_score:.3f} ({best_episode})")
        
        if failed:
            print("\n❌ Failed episodes:")
            for result in failed:
                print(f"   {result.episode_id}: {result.error_message}")
        
        return len(successful) > 0
        
    except Exception as e:
        print(f"❌ Batch processing test failed: {e}")
        return False

def test_end_to_end_workflow():
    """Test complete workflow from transcript to database storage"""
    print("\n" + "="*60)
    print("TEST 5: End-to-End Workflow")
    print("="*60)
    
    try:
        # Get database connections
        db_manager = get_database_manager()
        episode_repo = get_episode_repo(db_manager)
        
        # Find a transcribed episode
        transcribed_episodes = episode_repo.get_by_status('transcribed')
        
        if not transcribed_episodes:
            print("⚠️  No transcribed episodes found for end-to-end test")
            return True
        
        test_episode = transcribed_episodes[0]
        print(f"🧪 Testing end-to-end workflow with episode: {test_episode.episode_guid}")
        print(f"📄 Transcript: {test_episode.transcript_path}")
        print(f"📝 Word count: {test_episode.transcript_word_count}")
        
        # Step 1: Score the transcript
        scorer = create_content_scorer()
        print("\n🤖 Step 1: Scoring transcript...")
        
        if test_episode.transcript_path and Path(test_episode.transcript_path).exists():
            result = scorer.score_transcript_file(
                Path(test_episode.transcript_path), 
                test_episode.episode_guid
            )
            
            if not result.success:
                print(f"❌ Scoring failed: {result.error_message}")
                return False
            
            print("✅ Transcript scored successfully")
            print(f"⏱️  Processing time: {result.processing_time:.2f}s")
            
            # Step 2: Store scores in database
            print("\n💾 Step 2: Storing scores in database...")
            episode_repo.update_scores(test_episode.episode_guid, result.scores)
            print("✅ Scores stored in database")
            
            # Step 3: Verify storage and retrieval
            print("\n🔍 Step 3: Verifying storage and retrieval...")
            updated_episode = episode_repo.get_by_episode_guid(test_episode.episode_guid)
            
            if updated_episode.scores:
                print("✅ Scores retrieved successfully:")
                for topic, score in updated_episode.scores.items():
                    emoji = "🎯" if score >= scorer.score_threshold else "📉"
                    print(f"   {emoji} {topic}: {score:.3f}")
                
                # Step 4: Test topic-based queries
                print(f"\n🔍 Step 4: Testing topic-based queries (threshold: {scorer.score_threshold})...")
                
                for topic in scorer.topics:
                    topic_name = topic['name']
                    qualifying = episode_repo.get_scored_episodes_for_topic(
                        topic_name, min_score=scorer.score_threshold
                    )
                    episode_score = updated_episode.scores.get(topic_name, 0.0)
                    
                    if episode_score >= scorer.score_threshold:
                        found_episode = any(ep.episode_guid == test_episode.episode_guid for ep in qualifying)
                        status = "✅" if found_episode else "❌"
                        print(f"   {status} {topic_name}: {len(qualifying)} qualifying episodes "
                               f"(this episode: {episode_score:.3f})")
                    else:
                        print(f"   📉 {topic_name}: Episode below threshold ({episode_score:.3f})")
                
                print("\n🎉 End-to-end workflow completed successfully!")
                return True
            else:
                print("❌ Failed to retrieve scores from database")
                return False
        else:
            print(f"❌ Transcript file not found: {test_episode.transcript_path}")
            return False
            
    except Exception as e:
        print(f"❌ End-to-end workflow test failed: {e}")
        return False

def main():
    """Run all Phase 4 tests"""
    print("🚀 Phase 4 Content Scoring System Test Suite")
    print("=" * 80)
    
    # Setup logging
    setup_logging()
    
    # Test summary
    tests = [
        ("API Connection", test_api_connection),
        ("Database Integration", test_database_integration),
        ("Transcript File Processing", test_transcript_file_processing),
        ("Batch Processing", test_batch_processing),
        ("End-to-End Workflow", test_end_to_end_workflow),
    ]
    
    results = {}
    start_time = time.time()
    
    # Run all tests
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n❌ {test_name} crashed: {e}")
            results[test_name] = False
    
    total_time = time.time() - start_time
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\n📊 Results: {passed}/{total} tests passed")
    print(f"⏱️  Total execution time: {total_time:.2f}s")
    
    if passed == total:
        print("🎉 All tests passed! Phase 4 implementation is ready.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)