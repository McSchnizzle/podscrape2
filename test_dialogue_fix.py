#!/usr/bin/env python3
"""Test script to regenerate Community Organizing digest with dialogue fix"""

import sys
import logging
from pathlib import Path

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Add src to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from dotenv import load_dotenv
load_dotenv()

from src.database.models import get_digest_repo
from src.audio.audio_generator import AudioGenerator

def main():
    digest_repo = get_digest_repo()

    # Get digest 375 (Community Organizing)
    digest_375 = digest_repo.get_by_id(375)

    if not digest_375:
        print("ERROR: Digest 375 not found!")
        return 1

    print(f"Digest ID: {digest_375.id}")
    print(f"Topic: {digest_375.topic}")
    print(f"Date: {digest_375.digest_date}")
    print(f"Script length: {len(digest_375.script_content)} chars")
    print(f"\nFirst 200 chars of script:")
    print(digest_375.script_content[:200])
    print("\n" + "="*80)
    print("Generating audio with dialogue fix...")
    print("="*80 + "\n")

    # Initialize audio generator
    generator = AudioGenerator()

    # Generate audio
    try:
        audio_metadata = generator.generate_audio_for_script(
            script_content=digest_375.script_content,
            topic=digest_375.topic,
            timestamp=None,  # Will use current time
            episode_id=digest_375.id
        )

        print(f"\n✅ SUCCESS!")
        print(f"Audio file: {audio_metadata.file_path}")
        print(f"File size: {audio_metadata.file_size_bytes:,} bytes")
        print(f"Duration: ~{audio_metadata.duration_seconds:.1f}s")
        print(f"Voice: {audio_metadata.voice_name}")
        print(f"\n🎧 Test the audio file to verify multi-voice dialogue!")

        return 0

    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
