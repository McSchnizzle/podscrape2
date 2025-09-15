#!/usr/bin/env python3
"""
Test digest generation with new 2-topic structure
"""

import os
import sys
import logging
from pathlib import Path
from datetime import date

# Add src to Python path  
sys.path.append(str(Path(__file__).parent / 'src'))

from database.models import get_episode_repo, get_digest_repo
from config.config_manager import ConfigManager

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_new_digests():
    """Test digest generation with new topic structure"""
    
    print("🎯 Testing New Digest Generation")
    print("="*50)
    
    # Initialize components
    episode_repo = get_episode_repo()
    digest_repo = get_digest_repo()
    config_manager = ConfigManager()
    
    # Get current topics
    topics = config_manager.get_topics()
    print(f"📋 Active Topics: {[t['name'] for t in topics]}")
    
    # Check for qualifying episodes
    print(f"\n🔍 Checking Episode Qualification:")
    for topic in topics:
        topic_name = topic['name']
        qualifying_episodes = episode_repo.get_scored_episodes_for_topic(
            topic_name, 
            min_score=config_manager.get_score_threshold(),
            start_date=date(2025, 9, 8),  # Last 2 days
            end_date=date(2025, 9, 9)
        )
        
        print(f"  {topic_name}: {len(qualifying_episodes)} qualifying episodes")
        if len(qualifying_episodes) > 0:
            print(f"    Scores: {[f'{ep.scores.get(topic_name, 0):.2f}' for ep in qualifying_episodes[:3]]}")
    
    # Get sample scored episodes to see actual scores
    print(f"\n📊 Sample Scored Episodes for New Topics:")
    episodes_with_scores = episode_repo.get_scored_episodes_sample(limit=5)

    for episode in episodes_with_scores:
        scores = episode.scores or {}
        print(f"  Episode: {episode.title[:40]}...")
        for topic_name in [t['name'] for t in topics]:
            score = scores.get(topic_name, 0.0)
            qualifier = "✅" if score >= 0.65 else ""
            print(f"    {qualifier} {topic_name}: {score:.2f}")
        print()

if __name__ == "__main__":
    test_new_digests()