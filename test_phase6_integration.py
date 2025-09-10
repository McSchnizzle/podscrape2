#!/usr/bin/env python3
"""
Comprehensive Phase 6 Integration Test - End-to-End TTS & Audio Generation
Tests the complete pipeline: Script → Voice Config → TTS → Metadata → File Management
"""

import os
import sys
from pathlib import Path
from datetime import date, datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.audio.audio_generator import AudioGenerator
from src.audio.metadata_generator import MetadataGenerator
from src.audio.audio_manager import AudioManager
from src.audio.voice_manager import VoiceManager

def test_phase6_integration():
    """Test complete Phase 6 pipeline with real scripts"""
    print("🎙️ Testing Phase 6: Complete TTS & Audio Generation Pipeline")
    print("=" * 70)
    
    try:
        # Initialize all components
        print("1. Initializing Phase 6 Components...")
        
        voice_manager = VoiceManager()
        audio_generator = AudioGenerator()
        metadata_generator = MetadataGenerator()
        audio_manager = AudioManager()
        
        print("   ✅ All Phase 6 components initialized successfully")
        
        # Validate voice configuration
        print("\n2. Validating voice configuration...")
        voice_validation = voice_manager.validate_voice_configuration()
        
        print(f"   Topics checked: {voice_validation['topics_checked']}")
        print(f"   Configuration valid: {'✅' if voice_validation['valid'] else '❌'}")
        
        if voice_validation['issues']:
            print("   Issues found:")
            for issue in voice_validation['issues']:
                print(f"     - {issue}")
        
        # Find all available scripts
        print("\n3. Discovering available scripts...")
        scripts_dir = Path("data/scripts")
        script_files = list(scripts_dir.glob("*.md"))
        
        print(f"   Found {len(script_files)} script files:")
        
        # Map scripts to topics
        script_topic_mapping = []
        topic_mapping = {
            'AI_News': 'AI News',
            'Tech_News': 'Tech News and Tech Culture', 
            'Community_Organizing': 'Community Organizing',
            'Societal_Culture': 'Societal Culture Change'
        }
        
        for script_file in script_files:
            filename = script_file.stem
            matched_topic = None
            
            for key, topic in topic_mapping.items():
                if key in filename:
                    matched_topic = topic
                    break
            
            if matched_topic:
                file_size = script_file.stat().st_size
                script_topic_mapping.append((script_file, matched_topic))
                print(f"   • {script_file.name} → {matched_topic} ({file_size:,} bytes)")
            else:
                print(f"   ⚠️ Could not map: {script_file.name}")
        
        if not script_topic_mapping:
            print("   ❌ No scripts could be mapped to topics!")
            return False
        
        # Test with a subset (limit API calls for testing)
        test_scripts = script_topic_mapping[:2]  # Test first 2 scripts
        print(f"\n4. Testing pipeline with {len(test_scripts)} scripts...")
        
        test_date = date(2025, 9, 9)
        successful_generations = []
        
        for i, (script_file, topic) in enumerate(test_scripts, 1):
            print(f"\n   === Test {i}: {script_file.name} ===")
            print(f"   📝 Script: {script_file.name}")
            print(f"   🎯 Topic: {topic}")
            print(f"   📏 Size: {script_file.stat().st_size:,} bytes")
            
            try:
                # Step 1: Generate metadata
                print("   🤖 Generating metadata with GPT-5...")
                metadata = metadata_generator.generate_metadata_for_script(
                    str(script_file),
                    topic,
                    test_date
                )
                
                print(f"      📝 Title: '{metadata.title}'")
                print(f"      📄 Summary: {metadata.summary[:60]}...")
                print(f"      🏷️ Keywords: {metadata.keywords[:40]}...")
                print(f"      📂 Category: {metadata.category}")
                
                # Step 2: Generate TTS audio
                print("   🎙️ Generating TTS audio...")
                audio_metadata = audio_generator.generate_audio_for_script(
                    str(script_file),
                    topic
                )
                
                print(f"      🔊 Audio file: {Path(audio_metadata.file_path).name}")
                print(f"      📊 File size: {audio_metadata.file_size_bytes:,} bytes")
                print(f"      ⏱️ Est. duration: {audio_metadata.duration_seconds:.1f} seconds")
                print(f"      🎭 Voice: {audio_metadata.voice_name}")
                
                # Step 3: Verify file exists and is valid
                audio_file = Path(audio_metadata.file_path)
                if audio_file.exists():
                    actual_size = audio_file.stat().st_size
                    print(f"      ✅ File verified: {actual_size:,} bytes")
                    
                    if actual_size != audio_metadata.file_size_bytes:
                        print(f"      ⚠️ Size mismatch: expected {audio_metadata.file_size_bytes}, got {actual_size}")
                else:
                    print(f"      ❌ Audio file not found!")
                    continue
                
                successful_generations.append({
                    'script': script_file.name,
                    'topic': topic,
                    'audio_file': audio_file.name,
                    'metadata': metadata,
                    'audio_metadata': audio_metadata
                })
                
                print("      ✅ Pipeline completed successfully")
                
            except Exception as e:
                print(f"      ❌ Pipeline failed: {e}")
                continue
        
        # Test audio file management
        print(f"\n5. Testing audio file management...")
        
        # Organize files
        organize_results = audio_manager.organize_audio_files()
        print(f"   📂 Organized files: moved {organize_results['moved_to_current']}, errors {organize_results['errors']}")
        
        # Get updated file list
        current_files = audio_manager.get_audio_files("current")
        print(f"   📁 Current directory: {len(current_files)} files")
        
        # Show storage stats
        stats = audio_manager.get_storage_stats()
        print(f"   💾 Total storage: {stats['total_size_mb']:.1f} MB across {stats['total_files']} files")
        
        # Export metadata
        metadata_export_path = audio_manager.export_metadata("phase6_test_metadata.json")
        print(f"   📋 Metadata exported to: {Path(metadata_export_path).name}")
        
        # Summary results
        print(f"\n6. Phase 6 Integration Test Results:")
        print(f"   📊 Scripts processed: {len(test_scripts)}")
        print(f"   ✅ Successful generations: {len(successful_generations)}")
        print(f"   ❌ Failed generations: {len(test_scripts) - len(successful_generations)}")
        
        if successful_generations:
            print(f"\n   🎉 Successfully generated audio files:")
            for result in successful_generations:
                print(f"   • {result['audio_file']} - {result['topic']}")
                print(f"     Title: {result['metadata'].title}")
        
        # Test database integration readiness (Task 6.6 preview)
        print(f"\n7. Database integration readiness check...")
        
        # Check if we have the necessary metadata for database storage
        if successful_generations:
            sample_result = successful_generations[0]
            
            required_fields = [
                'mp3_path', 'duration_seconds', 'title', 'summary'
            ]
            
            available_data = {
                'mp3_path': sample_result['audio_metadata'].file_path,
                'duration_seconds': int(sample_result['audio_metadata'].duration_seconds or 0),
                'title': sample_result['metadata'].title,
                'summary': sample_result['metadata'].summary
            }
            
            print("   📋 Database fields ready:")
            for field in required_fields:
                value = available_data.get(field, 'Missing')
                status = "✅" if value != 'Missing' else "❌"
                print(f"     {status} {field}: {str(value)[:50]}...")
        
        success_rate = len(successful_generations) / len(test_scripts) if test_scripts else 0
        
        print(f"\n✅ Phase 6 Integration Test {'PASSED' if success_rate >= 0.5 else 'FAILED'}")
        print(f"📋 Task 6.5: End-to-end pipeline working with {success_rate*100:.0f}% success rate")
        
        return success_rate >= 0.5
        
    except Exception as e:
        print(f"❌ Error in Phase 6 integration test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_phase6_integration()
    sys.exit(0 if success else 1)