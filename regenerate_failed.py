"""
Regenerate the failed Social Movements digest (05:34:47).
"""
from src.database.models import get_digest_repo
from src.audio.audio_generator import AudioGenerator
from datetime import date
from pathlib import Path

repo = get_digest_repo()
digests = repo.get_by_date(date(2025, 11, 10))

# Find the 05:34:47 digest
for digest in digests:
    if 'Community' in digest.topic and '05:34:47' in str(digest.digest_timestamp):
        print(f"Regenerating: {digest.topic}")
        print(f"  Timestamp: {digest.digest_timestamp}")
        print(f"  Script: {len(digest.script_content)} chars")

        # Delete old MP3 if exists
        if digest.mp3_path:
            old_mp3 = Path(digest.mp3_path)
            if old_mp3.exists():
                old_mp3.unlink()
            repo.update_audio(digest.id, None, 0, "", "")

        print("  Generating audio...")
        generator = AudioGenerator()
        try:
            metadata = generator.generate_audio_for_digest(digest)
            print(f"  ✅ SUCCESS: {Path(metadata.file_path).name}")
            print(f"     Size: {metadata.file_size_bytes:,} bytes")
        except Exception as e:
            print(f"  ❌ FAILED: {e}")
            import traceback
            traceback.print_exc()
        break
