#!/usr/bin/env python3
"""
Phase 5 Validation Test - Real Script Generation
Tests script generation with the existing scored episode to validate Phase 5 is fully working.
Uses real API keys and the existing "10 Things Worth More Than a Pound of Gold" episode.
"""

import os
import sys
import logging
from datetime import date
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Set up environment
from dotenv import load_dotenv
load_dotenv()

from src.generation.script_generator import ScriptGenerator
from src.database.models import get_episode_repo, get_digest_repo

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_phase5_with_existing_episode():
    """
    Test Phase 5 script generation with the existing scored episode
    """
    logger.info("="*80)
    logger.info("PHASE 5 VALIDATION TEST - REAL SCRIPT GENERATION")
    logger.info("="*80)
    
    # Initialize components
    script_generator = ScriptGenerator()
    episode_repo = get_episode_repo()
    digest_repo = get_digest_repo()
    
    logger.info(f"✓ ScriptGenerator initialized")
    logger.info(f"✓ Score threshold: {script_generator.score_threshold}")
    logger.info(f"✓ Max words per script: {script_generator.max_words}")
    
    # Check existing episodes in database
    logger.info("\n" + "="*60)
    logger.info("CHECKING EXISTING EPISODES")
    logger.info("="*60)
    
    scored_episodes = episode_repo.get_by_status('scored')
    logger.info(f"Found {len(scored_episodes)} scored episodes in database:")
    
    qualifying_topics = {}
    
    for episode in scored_episodes:
        logger.info(f"\n  Episode: {episode.title}")
        logger.info(f"    GUID: {episode.episode_guid}")
        logger.info(f"    Status: {episode.status}")
        
        if episode.scores:
            logger.info("    Scores:")
            for topic, score in episode.scores.items():
                status = "✓ QUALIFIES" if score >= 0.65 else "  "
                logger.info(f"      {status} {topic}: {score:.2f}")
                
                if score >= 0.65:
                    if topic not in qualifying_topics:
                        qualifying_topics[topic] = []
                    qualifying_topics[topic].append(episode)
    
    if not qualifying_topics:
        logger.error("❌ No episodes qualify for any topics! Cannot test Phase 5.")
        return False
    
    logger.info(f"\n✓ Topics with qualifying episodes: {list(qualifying_topics.keys())}")
    
    # Test script generation for each qualifying topic
    logger.info("\n" + "="*60)
    logger.info("TESTING SCRIPT GENERATION")
    logger.info("="*60)
    
    success_count = 0
    
    for topic, topic_episodes in qualifying_topics.items():
        logger.info(f"\n📝 Generating script for '{topic}' with {len(topic_episodes)} episodes...")
        
        try:
            # Create digest using the script generator
            digest = script_generator.create_digest(topic, date.today())
            
            logger.info(f"✅ SUCCESS - Generated digest for {topic}")
            logger.info(f"   Digest ID: {digest.id}")
            logger.info(f"   Episodes: {digest.episode_count}")
            logger.info(f"   Word count: {digest.script_word_count}")
            logger.info(f"   Average score: {digest.average_score:.2f}")
            logger.info(f"   Script path: {digest.script_path}")
            
            # Verify script file exists and show preview
            if digest.script_path and Path(digest.script_path).exists():
                with open(digest.script_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    preview = content[:400] + "..." if len(content) > 400 else content
                    
                logger.info(f"   ✅ Script file created successfully")
                logger.info(f"   Preview:\n{preview}")
                
                success_count += 1
                
            else:
                logger.error(f"   ❌ Script file not found: {digest.script_path}")
            
        except Exception as e:
            logger.error(f"❌ FAILED to generate digest for {topic}: {e}")
            continue
    
    # Final results
    logger.info("\n" + "="*80)
    logger.info("PHASE 5 VALIDATION RESULTS")
    logger.info("="*80)
    
    if success_count > 0:
        logger.info(f"✅ SUCCESS: Generated {success_count} digest scripts")
        logger.info(f"✅ Phase 5 is fully implemented and working with real data!")
        logger.info(f"✅ Script generation pipeline: Episodes → Filtering → GPT-4 → Scripts")
        return True
    else:
        logger.error(f"❌ FAILED: No digest scripts generated successfully")
        logger.error(f"❌ Phase 5 implementation needs debugging")
        return False

def main():
    """Run Phase 5 validation test"""
    success = test_phase5_with_existing_episode()
    
    if success:
        print("\n🎉 PHASE 5 VALIDATION PASSED - Script generation working with real data!")
    else:
        print("\n❌ PHASE 5 VALIDATION FAILED - Script generation needs fixes")
        sys.exit(1)

if __name__ == '__main__':
    main()