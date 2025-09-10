#!/usr/bin/env python3
"""
Generate digests and audio with new 2-topic structure
"""

import os
import sys
import logging
from pathlib import Path
from datetime import date, datetime

# Add src to Python path
sys.path.append(str(Path(__file__).parent / 'src'))

from generation.script_generator import ScriptGenerator  
from audio.complete_audio_processor import CompleteAudioProcessor
from database.models import get_database_manager, get_digest_repo
from config.config_manager import ConfigManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def generate_new_topic_digests():
    """Generate complete digests with new topic structure"""
    
    print("🎯 GENERATING NEW TOPIC DIGESTS")
    print("="*50)
    
    # Initialize components
    script_gen = ScriptGenerator()
    audio_processor = CompleteAudioProcessor()
    digest_repo = get_digest_repo()
    config_manager = ConfigManager()
    
    # Generate for current date
    target_date = date(2025, 9, 9)
    
    # Generate scripts
    print(f"📝 Step 1: Generating Scripts for {target_date}")
    results = script_gen.generate_all_digests(target_date)
    
    script_results = []
    for result in results:
        if result['generated']:
            print(f"  ✅ {result['topic']}: {result['word_count']} words, {result['episode_count']} episodes")
            script_results.append(result)
        else:
            print(f"  ⏭️  {result['topic']}: {result['reason']}")
    
    if not script_results:
        print("❌ No scripts generated, cannot proceed to audio generation")
        return False
    
    # Generate audio for successful scripts
    print(f"\n🎵 Step 2: Generating Audio Files")
    audio_results = []
    
    for script_result in script_results:
        topic = script_result['topic']
        print(f"  🎤 Processing: {topic}")
        
        # Get digest from database
        digest = digest_repo.get_by_topic_date(topic, target_date)
        if not digest:
            print(f"    ❌ No digest found in database for {topic}")
            continue
            
        try:
            # Generate audio
            audio_result = audio_processor.process_digest_to_audio(digest.id)
            
            if audio_result['success']:
                audio_results.append({
                    'topic': topic,
                    'audio_path': audio_result['audio_metadata'].file_path,
                    'success': True
                })
                print(f"    ✅ Audio generated: {Path(audio_result['audio_metadata'].file_path).name}")
            else:
                print(f"    ❌ Audio generation failed: {', '.join(audio_result['errors'])}")
                
        except Exception as e:
            print(f"    ❌ Audio generation error: {e}")
    
    # Summary
    print(f"\n📊 GENERATION SUMMARY:")
    print(f"  📝 Scripts generated: {len(script_results)}")
    print(f"  🎵 Audio files generated: {len(audio_results)}")
    
    if len(audio_results) > 0:
        print(f"\n🎉 SUCCESS: Generated {len(audio_results)} complete digest(s)")
        for result in audio_results:
            print(f"  ✅ {result['topic']}: {Path(result['audio_path']).name}")
        return True
    else:
        print(f"\n❌ No complete digests generated")
        return False

if __name__ == "__main__":
    try:
        success = generate_new_topic_digests()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Failed to generate digests: {e}")
        sys.exit(1)