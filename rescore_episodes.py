#!/usr/bin/env python3
"""
Re-score all transcribed episodes with the new simplified topic structure.
Updated to use 2 combined topics instead of 4 separate ones.
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime

# Add src to Python path
sys.path.append(str(Path(__file__).parent / 'src'))

from database.models import get_episode_repo
from scoring.content_scorer import ContentScorer
from config.config_manager import ConfigManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rescore_episodes.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def rescore_all_episodes():
    """Re-score all transcribed episodes with new topic structure"""

    # Initialize components
    episode_repo = get_episode_repo()

    # Initialize content scorer with new configuration
    config_manager = ConfigManager()
    content_scorer = ContentScorer(config_path="config/topics.json")

    logger.info("Starting episode re-scoring with new topic structure")
    logger.info(f"Active topics: {[t['name'] for t in config_manager.get_topics()]}")

    # Get all episodes that have been transcribed
    episodes_to_rescore = episode_repo.get_by_status_list(['transcribed', 'scored', 'digested'])
    
    logger.info(f"Found {len(episodes_to_rescore)} episodes to re-score")
    
    successful_rescores = 0
    failed_rescores = 0

    for episode in episodes_to_rescore:
        episode_id = episode.id
        episode_guid = episode.episode_guid
        title = episode.title
        transcript_path = episode.transcript_path
        current_status = episode.status

        logger.info(f"\\nRe-scoring episode {episode_id}: {title[:50]}...")
        
        try:
            # Read transcript content (prefer database content over file)
            transcript_content = None
            if episode.transcript_content and episode.transcript_content.strip():
                transcript_content = episode.transcript_content
                logger.debug(f"Using transcript from database for episode: {title}")
            elif transcript_path and Path(transcript_path).exists():
                logger.debug(f"Reading transcript from file (fallback) for episode: {title}")
                with open(transcript_path, 'r', encoding='utf-8') as f:
                    transcript_content = f.read()
            else:
                logger.warning(f"No transcript content available (database or file) for episode: {title}")
                failed_rescores += 1
                continue
            
            if not transcript_content.strip():
                logger.warning(f"Empty transcript content for episode: {title}")
                failed_rescores += 1
                continue
            
            # Score the episode with new topics
            logger.info(f"Scoring with content scorer...")
            scoring_result = content_scorer.score_transcript(transcript_content)
            
            if not scoring_result.success:
                logger.error(f"Scoring failed: {scoring_result.error_message}")
                failed_rescores += 1
                continue
            
            scores = scoring_result.scores
            
            # Update episode with new scores
            episode_repo.update_scores(episode_guid, scores)
            
            # Log the new scores
            logger.info("📊 NEW TOPIC SCORES:")
            for topic, score in scores.items():
                qualifier = "✅ QUALIFIES" if score >= config_manager.get_score_threshold() else ""
                logger.info(f"    {qualifier} {topic:<35} {score:.2f}")
            
            successful_rescores += 1
            logger.info(f"✅ Re-scored successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to re-score episode {episode_id}: {e}")
            failed_rescores += 1
            continue
    
    # Summary
    logger.info(f"\\n" + "="*50)
    logger.info(f"RE-SCORING COMPLETE:")
    logger.info(f"  ✅ Successfully re-scored: {successful_rescores} episodes")
    logger.info(f"  ❌ Failed to re-score: {failed_rescores} episodes")
    logger.info(f"  📊 Total processed: {len(episodes_to_rescore)} episodes")
    
    return successful_rescores > 0

if __name__ == "__main__":
    try:
        success = rescore_all_episodes()
        if success:
            logger.info("✅ Re-scoring completed successfully")
            sys.exit(0)
        else:
            logger.error("❌ Re-scoring failed")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\\n⏹️  Re-scoring interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"💥 Re-scoring failed with error: {e}")
        sys.exit(1)