#!/usr/bin/env python3
"""
Score all existing transcripts and generate digests/audio.
This script processes transcripts that were created but never scored.
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from database.models import Episode, get_episode_repo
from scoring.content_scorer import ContentScorer
from generation.script_generator import ScriptGenerator
from audio.complete_audio_processor import CompleteAudioProcessor

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Score all existing transcripts and generate digests/audio"""
    
    logger.info("🔄 Starting transcript scoring for existing episodes...")
    
    # Initialize components
    episode_repo = get_episode_repo()
    scorer = ContentScorer()
    script_generator = ScriptGenerator()
    audio_processor = CompleteAudioProcessor()
    
    # Find all transcript files
    transcript_dir = Path("data/transcripts")
    transcript_files = list(transcript_dir.glob("*.txt"))
    
    if not transcript_files:
        logger.warning("No transcript files found in data/transcripts/")
        return
    
    logger.info(f"📁 Found {len(transcript_files)} transcript files")
    
    scored_episodes = []
    
    # Process each transcript
    for transcript_file in transcript_files:
        transcript_name = transcript_file.stem
        logger.info(f"\n📝 Processing: {transcript_name}")
        
        # Check if this episode exists in database
        # Try to find by partial GUID match
        episodes = episode_repo.get_all()
        matching_episode = None
        
        for episode in episodes:
            if transcript_name in episode.episode_guid or episode.episode_guid in transcript_name:
                matching_episode = episode
                break
        
        if not matching_episode:
            logger.warning(f"  ⚠️  No database record found for {transcript_name}")
            continue
            
        # Check if already scored
        if matching_episode.status == 'scored':
            logger.info(f"  ✅ Already scored: {matching_episode.title[:60]}...")
            scored_episodes.append(matching_episode)
            continue
        
        # Score the episode
        try:
            logger.info(f"  🧠 Scoring: {matching_episode.title[:60]}...")
            scores = scorer.score_episode(matching_episode.episode_guid)
            
            if scores:
                # Update episode status
                episode_repo.update_status(matching_episode.id, 'scored')
                matching_episode.status = 'scored'
                scored_episodes.append(matching_episode)
                
                # Log scores
                for topic, score in scores.items():
                    logger.info(f"    {topic}: {score:.2f}")
                    
                logger.info(f"  ✅ Scored successfully")
            else:
                logger.error(f"  ❌ Scoring failed")
                
        except Exception as e:
            logger.error(f"  ❌ Error scoring {transcript_name}: {e}")
            continue
    
    if not scored_episodes:
        logger.warning("No episodes were scored successfully")
        return
    
    # Generate scripts for today
    logger.info(f"\n📚 Generating scripts for {len(scored_episodes)} scored episodes...")
    
    try:
        digests = script_generator.generate_scripts_for_date(datetime.now().date())
        
        if digests:
            logger.info(f"✅ Generated {len(digests)} digests")
            
            # Generate audio for digests with qualifying episodes
            logger.info(f"\n🎵 Generating audio for digests...")
            qualifying_digests = [d for d in digests if d.episode_count > 0]
            
            if qualifying_digests:
                audio_results = audio_processor.generate_audio_for_date(datetime.now().date())
                logger.info(f"✅ Generated {len(audio_results)} audio files")
            else:
                logger.info("No digests qualified for audio generation (all episode_count = 0)")
        else:
            logger.warning("No digests were generated")
            
    except Exception as e:
        logger.error(f"❌ Error generating digests: {e}")
    
    logger.info("\n🎉 Transcript scoring complete!")

if __name__ == "__main__":
    main()