"""
Test script to regenerate audio for a specific digest.
"""
import sys
from datetime import date, datetime
from pathlib import Path
from src.database.models import get_digest_repo
from src.audio.audio_generator import AudioGenerator

def regenerate_audio_for_digest(digest_id: int):
    """Regenerate audio for a specific digest ID"""
    repo = get_digest_repo()
    digest = repo.get_by_id(digest_id)

    if not digest:
        print(f"Error: Digest {digest_id} not found")
        return False

    print(f"Found digest: {digest.topic} @ {digest.digest_timestamp}")
    print(f"Current MP3: {digest.mp3_path}")
    print(f"Script content: {len(digest.script_content) if digest.script_content else 0} chars")

    # Delete old MP3 if exists
    if digest.mp3_path:
        old_mp3 = Path(digest.mp3_path)
        if old_mp3.exists():
            old_mp3.unlink()
            print(f"Deleted old MP3: {digest.mp3_path}")

    # Clear MP3 path in database
    repo.update_audio(digest.id, None, 0, "", "")
    print("Cleared MP3 path in database")

    # Regenerate audio
    print("\nRegenerating audio...")
    generator = AudioGenerator()

    try:
        audio_metadata = generator.generate_audio_for_digest(digest)
        print(f"\n✅ Success!")
        print(f"Generated: {audio_metadata.file_path}")
        print(f"Duration: ~{audio_metadata.duration_seconds:.1f}s")
        print(f"Size: {audio_metadata.file_size_bytes:,} bytes")
        return True
    except Exception as e:
        print(f"\n❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def find_digest_by_timestamp(topic: str, timestamp_str: str):
    """Find digest by topic and timestamp substring"""
    repo = get_digest_repo()
    # Search last 3 days
    for days_back in range(3):
        check_date = date.today() - __import__('datetime').timedelta(days=days_back)
        digests = repo.get_by_date(check_date)
        for digest in digests:
            if digest.topic == topic and timestamp_str in str(digest.digest_timestamp):
                return digest.id
    return None

if __name__ == "__main__":
    # Test with the 03:35:41 Social Movements digest
    digest_id = find_digest_by_timestamp("Social Movements and Community Organizing", "03:35:41")

    if not digest_id:
        print("Could not find digest with timestamp 03:35:41")
        sys.exit(1)

    print(f"Found digest ID: {digest_id}")
    print()

    success = regenerate_audio_for_digest(digest_id)
    sys.exit(0 if success else 1)
