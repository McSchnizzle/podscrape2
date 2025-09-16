#!/usr/bin/env python3
"""
Test FFmpeg chunking fix with 5-minute chunks (like orchestrator)
"""

import os
import sys
from pathlib import Path

# Add src directory to path
sys.path.append('src')

from src.podcast.audio_processor import AudioProcessor
from src.utils.logging_config import setup_logging

def test_ffmpeg_chunking_5min():
    """Test FFmpeg chunking with 5-minute chunks like the orchestrator"""
    print("Testing FFmpeg chunking with 5-minute chunks...")

    # Setup basic logging
    setup_logging()

    # Initialize audio processor with 5-minute chunks
    processor = AudioProcessor(chunk_duration_minutes=5)

    # Check if we have any existing audio files to test with
    audio_cache = Path("audio_cache")
    if audio_cache.exists():
        audio_files = list(audio_cache.glob("*.mp3"))
        if audio_files:
            test_file = audio_files[0]
            print(f"Testing with existing file: {test_file}")

            # Create a fake episode GUID for testing
            test_guid = "test-5min-episode-guid-12345"

            try:
                chunks = processor.chunk_audio(str(test_file), test_guid)
                print(f"✅ SUCCESS: Created {len(chunks)} chunks with 5-minute duration")
                for i, chunk in enumerate(chunks, 1):
                    print(f"  Chunk {i}: {chunk}")
                return True

            except Exception as e:
                print(f"❌ FAILED: {e}")
                return False
        else:
            print("No audio files found in audio_cache directory")
            return None
    else:
        print("No audio_cache directory found")
        return None

if __name__ == "__main__":
    result = test_ffmpeg_chunking_5min()
    if result is True:
        print("\n🎉 FFmpeg chunking fix verified with 5-minute chunks!")
    elif result is False:
        print("\n💥 FFmpeg chunking still failing with 5-minute chunks!")
        sys.exit(1)
    else:
        print("\n⚠️  No test files available")