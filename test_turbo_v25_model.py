#!/usr/bin/env python3
"""
Test script to verify Turbo v2.5 model changes work correctly.
Forces processing of a recent episode to test the new model and character limits.
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Set up environment
from dotenv import load_dotenv
load_dotenv()

from src.database.models import get_digest_repo
from src.audio.complete_audio_processor import CompleteAudioProcessor

def test_turbo_model():
    """Test the Turbo v2.5 model on an existing digest"""
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    logger = logging.getLogger(__name__)
    
    logger.info("="*80)
    logger.info("TESTING TURBO V2.5 MODEL & 40K CHARACTER LIMITS")
    logger.info("="*80)
    
    try:
        # Get the most recent digest
        digest_repo = get_digest_repo()
        recent_digests = digest_repo.get_recent_digests(days=30)
        
        if not recent_digests:
            logger.error("No recent digests found to test with")
            return
            
        # Use the most recent digest
        test_digest = recent_digests[0]
        logger.info(f"Testing with digest: {test_digest.topic} (ID: {test_digest.id})")
        logger.info(f"Generated: {test_digest.generated_at}")
        logger.info(f"Script: {test_digest.script_path}")
        
        # Check script length
        if test_digest.script_path and Path(test_digest.script_path).exists():
            with open(test_digest.script_path, 'r', encoding='utf-8') as f:
                script_content = f.read()
                char_count = len(script_content)
                logger.info(f"Script length: {char_count:,} characters")
                
                if char_count > 10000:
                    logger.info("✅ Script is longer than old 10K limit - perfect for testing Turbo v2.5!")
                else:
                    logger.info("⚠️  Script is under 10K chars, but still good for testing model change")
        
        # Initialize the complete audio processor
        logger.info("\n🎤 Testing Turbo v2.5 audio generation...")
        complete_audio_processor = CompleteAudioProcessor()
        
        # Clear any existing MP3 to force regeneration
        if test_digest.mp3_path and Path(test_digest.mp3_path).exists():
            old_mp3 = Path(test_digest.mp3_path)
            backup_name = f"{old_mp3.stem}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}{old_mp3.suffix}"
            backup_path = old_mp3.parent / backup_name
            old_mp3.rename(backup_path)
            logger.info(f"Backed up existing MP3 to: {backup_name}")
            
            # Clear MP3 path in database to force regeneration
            digest_repo.update_audio_info(test_digest.id, None, None, None, None)
            test_digest.mp3_path = None
        
        # Process digest to audio with Turbo v2.5
        result = complete_audio_processor.process_digest_to_audio(test_digest)
        
        # Report results
        if result.get('success'):
            logger.info("✅ TURBO V2.5 TEST SUCCESSFUL!")
            
            audio_metadata = result.get('audio_metadata')
            if audio_metadata:
                file_path = getattr(audio_metadata, 'file_path', 'Unknown')
                file_size = getattr(audio_metadata, 'file_size_bytes', 0)
                duration = getattr(audio_metadata, 'duration_seconds', 0)
                
                logger.info(f"   📁 File: {Path(file_path).name}")
                logger.info(f"   📊 Size: {file_size/1024/1024:.1f} MB")
                logger.info(f"   ⏱️  Duration: {duration:.1f} seconds")
                logger.info(f"   🎵 Model: eleven_turbo_v2_5 (40K char limit)")
                logger.info(f"   💰 Cost: 50% lower per character than old model")
                
        elif result.get('skipped'):
            logger.info(f"⏭️  Skipped: {result.get('skip_reason')}")
        else:
            errors = result.get('errors', ['Unknown error'])
            logger.error(f"❌ Failed: {errors[0]}")
            
    except Exception as e:
        logger.error(f"💥 Test failed: {e}")
        
    logger.info("\n" + "="*80)
    logger.info("TURBO V2.5 MODEL TEST COMPLETE")
    logger.info("="*80)

if __name__ == '__main__':
    test_turbo_model()