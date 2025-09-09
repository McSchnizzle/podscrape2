#!/usr/bin/env python3
"""
Phase 5 Test Suite: Script Generation
Tests the complete script generation pipeline with real scored episodes.
"""

import os
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
import tempfile
import shutil

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.generation.script_generator import ScriptGenerator, ScriptGenerationError, TopicInstruction
from src.database.models import get_episode_repo, get_digest_repo, get_database_manager
from src.config.config_manager import ConfigManager

class TestPhase5ScriptGeneration(unittest.TestCase):
    """Test script generation functionality"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        print("="*60)
        print("Phase 5 Test Suite: Script Generation")
        print("="*60)
        
        # Verify required directories exist
        required_dirs = ['digest_instructions', 'data/database', 'data/scripts']
        for dir_path in required_dirs:
            if not Path(dir_path).exists():
                print(f"ERROR: Required directory missing: {dir_path}")
                sys.exit(1)
        
        # Initialize components
        cls.generator = ScriptGenerator()
        cls.episode_repo = get_episode_repo()
        cls.digest_repo = get_digest_repo()
        
    def test_01_load_topic_instructions(self):
        """Test loading topic instructions from digest_instructions/"""
        print("\n1. Testing topic instruction loading...")
        
        # Check that instructions were loaded
        self.assertGreater(len(self.generator.topic_instructions), 0, 
                          "No topic instructions loaded")
        
        # Verify expected topics
        expected_topics = ['AI News', 'Tech News and Tech Culture', 
                          'Community Organizing', 'Societal Culture Change']
        
        for topic in expected_topics:
            self.assertIn(topic, self.generator.topic_instructions,
                         f"Topic instruction missing: {topic}")
            
            instruction = self.generator.topic_instructions[topic]
            self.assertIsInstance(instruction, TopicInstruction)
            self.assertTrue(len(instruction.content) > 100,
                           f"Instruction content too short for {topic}")
            print(f"   ✓ Loaded {topic}: {len(instruction.content)} chars")
        
        print(f"   ✓ Loaded {len(self.generator.topic_instructions)} topic instructions")
    
    def test_02_episode_filtering(self):
        """Test filtering episodes by score threshold"""
        print("\n2. Testing episode filtering by score threshold...")
        
        # Test filtering for each topic
        total_qualifying = 0
        
        for topic in self.generator.topic_instructions:
            episodes = self.generator.get_qualifying_episodes(topic)
            
            print(f"   {topic}: {len(episodes)} qualifying episodes")
            
            # Verify all episodes meet threshold
            for episode in episodes:
                self.assertIsNotNone(episode.scores, f"Episode {episode.title} missing scores")
                score = episode.scores.get(topic, 0.0)
                self.assertGreaterEqual(score, self.generator.score_threshold,
                                      f"Episode {episode.title} below threshold: {score}")
            
            total_qualifying += len(episodes)
        
        print(f"   ✓ Total qualifying episodes across all topics: {total_qualifying}")
        
        # With corrected scoring, we should have exactly 1 qualifying episode
        # (Societal Culture Change = 0.80 for "10 Things Worth More Than a Pound of Gold")
        self.assertEqual(total_qualifying, 1, 
                        "Expected exactly 1 qualifying episode after scoring fix")
    
    def test_03_script_generation_with_content(self):
        """Test script generation with qualifying episodes"""
        print("\n3. Testing script generation with content...")
        
        # Find topic with qualifying episodes
        topic_with_content = None
        qualifying_episodes = None
        
        for topic in self.generator.topic_instructions:
            episodes = self.generator.get_qualifying_episodes(topic)
            if episodes:
                topic_with_content = topic
                qualifying_episodes = episodes
                break
        
        self.assertIsNotNone(topic_with_content, "No topics have qualifying episodes")
        print(f"   Testing with topic: {topic_with_content}")
        print(f"   Qualifying episodes: {len(qualifying_episodes)}")
        
        # Generate script
        test_date = date.today()
        script_content, word_count = self.generator.generate_script(
            topic_with_content, qualifying_episodes, test_date
        )
        
        # Validate script
        self.assertTrue(len(script_content) > 200, "Generated script too short")
        self.assertLessEqual(word_count, self.generator.max_words,
                           f"Script exceeds word limit: {word_count} > {self.generator.max_words}")
        
        # Check script contains topic-relevant content
        self.assertIn(topic_with_content.lower().split()[0], script_content.lower(),
                     "Script doesn't mention topic")
        
        print(f"   ✓ Generated script: {word_count} words")
        print(f"   ✓ Preview: {script_content[:100]}...")
    
    def test_04_script_generation_no_content(self):
        """Test script generation when no episodes qualify"""
        print("\n4. Testing no-content script generation...")
        
        # Find topic with no qualifying episodes
        topic_no_content = None
        for topic in self.generator.topic_instructions:
            episodes = self.generator.get_qualifying_episodes(topic)
            if not episodes:
                topic_no_content = topic
                break
        
        self.assertIsNotNone(topic_no_content, "All topics have qualifying episodes")
        print(f"   Testing with topic: {topic_no_content}")
        
        # Generate no-content script
        test_date = date.today()
        script_content, word_count = self.generator.generate_script(
            topic_no_content, [], test_date
        )
        
        # Validate no-content script
        self.assertTrue(len(script_content) > 100, "No-content script too short")
        self.assertIn("don't have any new episodes", script_content,
                     "No-content script missing expected message")
        self.assertIn(str(self.generator.score_threshold).replace('0.', '').rstrip('0') + '%', 
                     script_content, "No-content script missing threshold reference")
        
        print(f"   ✓ Generated no-content script: {word_count} words")
        print(f"   ✓ Preview: {script_content[:100]}...")
    
    def test_05_script_saving(self):
        """Test script file saving"""
        print("\n5. Testing script file saving...")
        
        # Create test script
        test_topic = list(self.generator.topic_instructions.keys())[0]
        test_date = date.today()
        test_content = f"# Test Script for {test_topic}\n\nThis is a test script for {test_date}."
        test_word_count = len(test_content.split())
        
        # Save script
        script_path = self.generator.save_script(test_topic, test_date, test_content, test_word_count)
        
        # Validate file was created
        self.assertTrue(Path(script_path).exists(), f"Script file not created: {script_path}")
        
        # Validate file contents
        with open(script_path, 'r', encoding='utf-8') as f:
            saved_content = f.read()
        
        self.assertEqual(saved_content, test_content, "Saved content doesn't match original")
        
        # Validate filename format
        expected_filename = f"{test_topic.replace(' ', '_')}_{test_date.strftime('%Y%m%d')}.md"
        self.assertTrue(script_path.endswith(expected_filename),
                       f"Unexpected filename format: {script_path}")
        
        print(f"   ✓ Script saved to: {script_path}")
        print(f"   ✓ File size: {Path(script_path).stat().st_size} bytes")
        
        # Cleanup test file
        Path(script_path).unlink()
    
    def test_06_complete_digest_creation(self):
        """Test complete digest creation workflow"""
        print("\n6. Testing complete digest creation...")
        
        # Find topic with content
        topic_with_content = None
        for topic in self.generator.topic_instructions:
            episodes = self.generator.get_qualifying_episodes(topic)
            if episodes:
                topic_with_content = topic
                break
        
        self.assertIsNotNone(topic_with_content, "No topics have qualifying episodes")
        
        # Create digest
        test_date = date.today()
        digest = self.generator.create_digest(topic_with_content, test_date)
        
        # Validate digest
        self.assertIsNotNone(digest, "Digest creation failed")
        self.assertEqual(digest.topic, topic_with_content)
        self.assertEqual(digest.digest_date, test_date)
        self.assertIsNotNone(digest.script_path, "Script path not set")
        self.assertGreater(digest.script_word_count, 0, "Word count not set")
        self.assertGreater(digest.episode_count, 0, "Episode count not set")
        self.assertIsNotNone(digest.average_score, "Average score not calculated")
        
        # Validate script file exists
        self.assertTrue(Path(digest.script_path).exists(),
                       f"Script file doesn't exist: {digest.script_path}")
        
        print(f"   ✓ Created digest ID: {digest.id}")
        print(f"   ✓ Topic: {digest.topic}")
        print(f"   ✓ Episodes: {digest.episode_count}")
        print(f"   ✓ Word count: {digest.script_word_count}")
        print(f"   ✓ Average score: {digest.average_score:.2f}")
        print(f"   ✓ Script saved: {digest.script_path}")
        
        # Cleanup
        if digest.script_path and Path(digest.script_path).exists():
            Path(digest.script_path).unlink()
    
    def test_07_daily_digest_creation(self):
        """Test creating digests for all topics"""
        print("\n7. Testing daily digest creation for all topics...")
        
        test_date = date.today()
        digests = self.generator.create_daily_digests(test_date)
        
        # Should create one digest per active topic
        expected_count = len(self.generator.topic_instructions)
        self.assertEqual(len(digests), expected_count,
                        f"Expected {expected_count} digests, got {len(digests)}")
        
        # Check each digest
        topics_created = set()
        for digest in digests:
            self.assertIsNotNone(digest.id, "Digest ID not set")
            self.assertEqual(digest.digest_date, test_date, "Wrong digest date")
            self.assertIsNotNone(digest.script_path, "Script path not set")
            self.assertGreater(digest.script_word_count, 0, "Word count not set")
            
            topics_created.add(digest.topic)
            print(f"   ✓ {digest.topic}: {digest.episode_count} episodes, {digest.script_word_count} words")
            
            # Cleanup script files
            if digest.script_path and Path(digest.script_path).exists():
                Path(digest.script_path).unlink()
        
        # Verify all topics were processed
        expected_topics = set(self.generator.topic_instructions.keys())
        self.assertEqual(topics_created, expected_topics, "Not all topics were processed")
        
        print(f"   ✓ Created {len(digests)} daily digests successfully")
    
    def test_08_error_handling(self):
        """Test error handling scenarios"""
        print("\n8. Testing error handling...")
        
        # Test with invalid topic
        with self.assertRaises(ScriptGenerationError):
            self.generator.generate_script("NonexistentTopic", [], date.today())
        print("   ✓ Invalid topic raises ScriptGenerationError")
        
        # Test with empty transcript episodes (should work with no-content script)
        try:
            valid_topic = list(self.generator.topic_instructions.keys())[0]
            script_content, word_count = self.generator.generate_script(valid_topic, [], date.today())
            self.assertIn("don't have any new episodes", script_content)
            print("   ✓ Empty episodes handled gracefully")
        except Exception as e:
            self.fail(f"Empty episodes should not raise exception: {e}")

def main():
    """Run Phase 5 tests"""
    # Set up test environment
    os.environ.setdefault('OPENAI_API_KEY', 'test-key')
    
    # Run tests
    unittest.main(verbosity=2, exit=False)
    
    print("\n" + "="*60)
    print("Phase 5 Testing Complete!")
    print("="*60)

if __name__ == '__main__':
    main()