#!/usr/bin/env python3
"""
Test ElevenLabs TTS integration with existing real scripts
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.audio.audio_generator import AudioGenerator, AudioGenerationError

def test_tts_integration():
    """Test TTS integration with existing scripts"""
    print("🎙️ Testing ElevenLabs TTS Integration")
    print("=" * 50)
    
    try:
        # Initialize audio generator
        print("1. Initializing Audio Generator...")
        audio_gen = AudioGenerator()
        print("   ✅ AudioGenerator initialized successfully")
        
        # List available scripts
        scripts_dir = Path("data/scripts")
        print(f"\n2. Finding available scripts in {scripts_dir}...")
        
        script_files = list(scripts_dir.glob("*.md"))
        print(f"   Found {len(script_files)} script files:")
        
        for script_file in script_files:
            file_size = script_file.stat().st_size
            print(f"   • {script_file.name} ({file_size:,} bytes)")
        
        if not script_files:
            print("   ❌ No script files found!")
            return False
        
        # Test with smallest script first for safety
        smallest_script = min(script_files, key=lambda f: f.stat().st_size)
        print(f"\n3. Testing TTS with smallest script: {smallest_script.name}")
        
        # Extract topic from filename (e.g., "AI_News_20250909.md" -> "AI News")
        topic_name = smallest_script.stem.replace('_', ' ')
        for part in ['20250909', '20250908', '20250907']:  # Remove dates
            topic_name = topic_name.replace(part, '').strip()
        
        # Map common variations
        topic_mapping = {
            'AI News': 'AI News',
            'Tech News and Tech Culture': 'Tech News and Tech Culture',
            'Community Organizing': 'Community Organizing',
            'Societal Culture Change': 'Societal Culture Change'
        }
        
        # Find matching topic
        matched_topic = None
        for key, value in topic_mapping.items():
            if key.lower() in topic_name.lower() or topic_name.lower() in key.lower():
                matched_topic = value
                break
        
        if not matched_topic:
            print(f"   ⚠️  Could not match topic for '{topic_name}', using first available")
            matched_topic = list(topic_mapping.values())[0]
        
        print(f"   Script: {smallest_script.name}")
        print(f"   Extracted topic: '{matched_topic}'")
        print(f"   File size: {smallest_script.stat().st_size:,} bytes")
        
        # Read script preview
        with open(smallest_script, 'r', encoding='utf-8') as f:
            content = f.read()
            preview = content[:200] + "..." if len(content) > 200 else content
            print(f"   Content preview: {preview}")
        
        print("\n4. Generating TTS audio...")
        print("   ⚠️  This will make a real API call to ElevenLabs")
        
        # Generate audio
        audio_metadata = audio_gen.generate_audio_for_script(
            str(smallest_script),
            matched_topic
        )
        
        print("   ✅ TTS generation completed successfully!")
        print(f"   Audio file: {audio_metadata.file_path}")
        print(f"   File size: {audio_metadata.file_size_bytes:,} bytes")
        print(f"   Estimated duration: {audio_metadata.duration_seconds:.1f} seconds")
        print(f"   Voice: {audio_metadata.voice_name} ({audio_metadata.voice_id[:8]}...)")
        
        # Verify file exists
        audio_file = Path(audio_metadata.file_path)
        if audio_file.exists():
            actual_size = audio_file.stat().st_size
            print(f"   Verified file exists: {actual_size:,} bytes")
        else:
            print(f"   ❌ Audio file not found at {audio_metadata.file_path}")
            return False
        
        print(f"\n5. Listing generated audio files...")
        audio_files = audio_gen.list_generated_audio()
        print(f"   Found {len(audio_files)} audio files:")
        
        for audio_file in audio_files[:5]:  # Show first 5
            print(f"   • {audio_file['filename']} ({audio_file['size_bytes']:,} bytes)")
        
        print(f"\n✅ TTS integration testing completed successfully!")
        print(f"📋 Task 6.2: ElevenLabs TTS integration working with real scripts")
        
        return True
        
    except AudioGenerationError as e:
        print(f"❌ Audio generation error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing TTS integration: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_tts_integration()
    sys.exit(0 if success else 1)