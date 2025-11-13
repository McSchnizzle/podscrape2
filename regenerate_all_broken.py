"""
Regenerate all broken Social Movements MP3s from Nov 10-11.
"""
from src.database.models import get_digest_repo
from src.audio.audio_generator import AudioGenerator
from datetime import date
from pathlib import Path

print("Finding broken Social Movements digests...")
repo = get_digest_repo()
digests = repo.get_by_date(date(2025, 11, 10))

# Find the ones with dialogue scripts that need regeneration
targets = []
for d in digests:
    if 'Community' in d.topic and d.script_content and 'SPEAKER_1' in d.script_content:
        targets.append(d)

print(f"Found {len(targets)} Social Movements digests with dialogue scripts\n")

generator = AudioGenerator()
success_count = 0
fail_count = 0

for idx, digest in enumerate(targets, 1):
    timestamp_str = str(digest.digest_timestamp)
    print(f"\n[{idx}/{len(targets)}] {digest.topic}")
    print(f"  Timestamp: {timestamp_str}")
    print(f"  Digest ID: {digest.id}")
    print(f"  Script: {len(digest.script_content)} chars")

    # Delete old MP3 if exists
    if digest.mp3_path:
        old_mp3 = Path(digest.mp3_path)
        if old_mp3.exists():
            old_mp3.unlink()
            print(f"  Deleted old MP3")
        # Clear in database
        repo.update_audio(digest.id, None, 0, "", "")

    print(f"  Generating audio...")
    try:
        metadata = generator.generate_audio_for_digest(digest)
        print(f"  ✅ SUCCESS: {Path(metadata.file_path).name}")
        print(f"     Size: {metadata.file_size_bytes:,} bytes")
        success_count += 1
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        fail_count += 1

print(f"\n{'='*60}")
print(f"Results: {success_count} succeeded, {fail_count} failed")
print(f"{'='*60}")
