#!/usr/bin/env python3
"""
Test and configure ElevenLabs voice mappings for topics
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.audio.voice_manager import VoiceManager

def test_voice_configuration():
    """Test ElevenLabs voice configuration and update topics.json"""
    print("🎙️ Testing ElevenLabs Voice Configuration")
    print("=" * 50)
    
    try:
        # Initialize voice manager
        print("1. Initializing Voice Manager...")
        voice_manager = VoiceManager()
        print("   ✅ VoiceManager initialized successfully")
        
        # Fetch available voices
        print("\n2. Fetching available ElevenLabs voices...")
        voices = voice_manager.get_available_voices()
        print(f"   Found {len(voices)} available voices:")
        
        for i, voice in enumerate(voices[:10], 1):  # Show first 10
            print(f"   {i:2}. {voice.name} ({voice.voice_id[:8]}...)")
        
        if len(voices) > 10:
            print(f"   ... and {len(voices) - 10} more voices")
        
        # Get recommended voice mappings
        print("\n3. Generating recommended voice mappings...")
        recommendations = voice_manager.get_recommended_voices_for_topics()
        
        for topic, voice_id in recommendations.items():
            voice = voice_manager.get_voice_by_id(voice_id)
            voice_name = voice.name if voice else "Unknown"
            print(f"   • {topic} → {voice_name} ({voice_id[:12]}...)")
        
        # Update configuration file
        print("\n4. Updating topics.json configuration...")
        success = voice_manager.update_topic_voice_configuration()
        
        if success:
            print("   ✅ Configuration updated successfully")
        else:
            print("   ❌ Failed to update configuration")
            return False
        
        # Validate updated configuration
        print("\n5. Validating updated configuration...")
        validation = voice_manager.validate_voice_configuration()
        
        print(f"   Topics checked: {validation['topics_checked']}")
        print(f"   Voices available: {validation['voices_available']}")
        print(f"   Configuration valid: {'✅' if validation['valid'] else '❌'}")
        
        if validation['issues']:
            print("   Issues found:")
            for issue in validation['issues']:
                print(f"     - {issue}")
        
        print(f"\n✅ Voice configuration testing completed!")
        print(f"📋 Task 6.1: Voice configuration system ready for TTS generation")
        
        return validation['valid']
        
    except Exception as e:
        print(f"❌ Error testing voice configuration: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_voice_configuration()
    sys.exit(0 if success else 1)