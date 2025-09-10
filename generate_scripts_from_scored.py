#!/usr/bin/env python3
"""
Generate scripts from all scored episodes using the existing pipeline structure.
"""

import os
import sys
import logging
from datetime import datetime, date

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import pipeline class
from run_full_pipeline import FullPipelineRunner

def main():
    """Generate scripts from all scored episodes"""
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    logger.info("🔄 Starting script generation from scored episodes...")
    
    # Initialize pipeline
    pipeline = FullPipelineRunner()
    
    # Get all scored episodes
    scored_episodes = pipeline.episode_repo.get_by_status('scored')
    logger.info(f"📁 Found {len(scored_episodes)} scored episodes")
    
    if not scored_episodes:
        logger.warning("No scored episodes found")
        return
    
    # Check for high-scoring episodes
    high_scoring = []
    for ep in scored_episodes:
        if ep.scores:
            max_score = max(ep.scores.values())
            if max_score >= 0.65:
                high_scoring.append(ep)
    
    logger.info(f"🎯 Found {len(high_scoring)} episodes scoring ≥0.65")
    
    if not high_scoring:
        logger.warning("No episodes meet the 0.65 threshold")
        return
    
    # Generate scripts using the pipeline's script generator
    logger.info(f"\n📚 Generating scripts for today's date...")
    
    try:
        # Use the pipeline's script generator directly to create digests for each topic
        script_generator = pipeline.script_generator
        digests = []
        
        # Get topic list from config
        topics = ["AI News", "Tech News and Tech Culture", "Community Organizing", "Societal Culture Change"]
        
        for topic in topics:
            logger.info(f"  📄 Generating script for: {topic}")
            try:
                digest = script_generator.create_digest(topic, date.today())
                digests.append(digest)
                logger.info(f"    ✅ Success: {digest.episode_count} episodes, {digest.script_word_count} words")
            except Exception as e:
                logger.error(f"    ❌ Failed: {e}")
        
        if digests:
            logger.info(f"✅ Generated {len(digests)} scripts")
            
            for digest in digests:
                logger.info(f"  📄 {digest.topic}: {digest.episode_count} episodes, {digest.script_word_count} words")
                if digest.script_path:
                    logger.info(f"      File: {digest.script_path}")
            
            # Now generate audio for the scripts
            logger.info(f"\n🎵 Generating audio for scripts...")
            audio_processor = pipeline.complete_audio_processor
            audio_results = []
            
            for digest in digests:
                logger.info(f"  🎵 Processing: {digest.topic}")
                try:
                    result = audio_processor.process_digest_to_audio(digest)
                    if result.get('skipped'):
                        logger.info(f"    ⏭️  Skipped: {result.get('skip_reason')}")
                    else:
                        audio_results.append(result)
                        logger.info(f"    ✅ Generated MP3: {result.get('audio_path', 'Unknown')}")
                except Exception as e:
                    logger.error(f"    ❌ Failed: {e}")
            
            logger.info(f"✅ Generated {len(audio_results)} audio files")
            
        else:
            logger.warning("No scripts were generated")
            
    except Exception as e:
        logger.error(f"❌ Error generating scripts: {e}")
        import traceback
        traceback.print_exc()
    
    logger.info("\n🎉 Script generation complete!")

if __name__ == "__main__":
    main()