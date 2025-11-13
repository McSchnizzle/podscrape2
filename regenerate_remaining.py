"""
Regenerate the remaining 2 Social Movements MP3s.
"""
from src.database.models import get_digest_repo
from src.audio.audio_generator import AudioGenerator
from datetime import date
from pathlib import Path

print("Finding remaining Social Movements digests to regenerate...")
repo = get_digest_repo()
digests = repo.get_by_date(date(2025, 11, 10))

# Find the 2 we haven't regenerated yet (not 03:35:41)
targets = []
for d in digests:
    if 'Community' in d.topic and d.script_content and 'SPEAKER_1' in d.script_content:
        if '03:35:41' not in str(d.digest_timestamp):  # Skip the one we already did
            targets.append(d)

print(f"Found {len(targets)} digests to regenerate\n")

generator = AudioGenerator()

for idx, digest in enumerate(targets, 1):
    print(f"\n[{idx}/{len(targets)}] {digest.topic}")
    print(f"  Timestamp: {digest.digest_timestamp}")
    print(f"  Script: {len(digest.script_content)} chars")

    # Delete old MP3 if exists
    if digest.mp3_path:
        old_mp3 = Path(digest.mp3_path)
        if old_mp3.exists():
            old_mp3.unlink()
            print(f"  Deleted old MP3")
        # Clear in database to trigger republishing
        repo.update_audio(digest.id, None, 0, "", "")

    print(f"  Generating audio...")
    try:
        metadata = generator.generate_audio_for_digest(digest)
        print(f"  ✅ SUCCESS: {Path(metadata.file_path).name}")
        print(f"     Size: {metadata.file_size_bytes:,} bytes")
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        import traceback
        traceback.print_exc()

print("\n✅ Regeneration complete")
