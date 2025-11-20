#!/usr/bin/env python3
"""Test script to regenerate AI & Tech digest with correct voice and v3 model"""

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

    # Get digest 374 (AI & Tech)
    digest_374 = digest_repo.get_by_id(374)

    if not digest_374:
        print("ERROR: Digest 374 not found!")
        return 1

    print(f"Digest ID: {digest_374.id}")
    print(f"Topic: {digest_374.topic}")
    print(f"Date: {digest_374.digest_date}")
    print(f"Script length: {len(digest_374.script_content)} chars")
    print(f"\nFirst 200 chars of script:")
    print(digest_374.script_content[:200])
    print("\n" + "="*80)
    print("Generating audio with correct voice (21m00Tcm4TlvDq8ikWAM) and v3 model...")
    print("="*80 + "\n")

    # Initialize audio generator
    generator = AudioGenerator()

    # Generate audio
    try:
        # Temporarily modify the script to add the test episode ID
        # We'll manually rename the file after generation
        audio_metadata = generator.generate_audio_for_script(
            script_content=digest_374.script_content,
            topic=digest_374.topic,
            timestamp="20251113_161700",  # Match original timestamp
            episode_id="374a"  # Add "a" suffix
        )

        print(f"\n✅ SUCCESS!")
        print(f"Audio file: {audio_metadata.file_path}")
        print(f"File size: {audio_metadata.file_size_bytes:,} bytes")
        print(f"Duration: ~{audio_metadata.duration_seconds:.1f}s")
        print(f"Voice: {audio_metadata.voice_name}")
        print(f"Voice ID: {audio_metadata.voice_id}")
        print(f"\n🎧 Test the audio file to verify correct voice and v3 model!")

        return 0

    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
