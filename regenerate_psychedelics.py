"""
Regenerate all Psychedelics and Spirituality digests with eleven_v3 model and narrative chunking.
"""
from src.database.models import get_digest_repo
from src.audio.audio_generator import AudioGenerator
from datetime import date, timedelta
from pathlib import Path

print("Finding all Psychedelics and Spirituality digests to regenerate...")
repo = get_digest_repo()

# Get all Psychedelics digests from the last 14 days
end_date = date.today()
start_date = end_date - timedelta(days=14)

all_digests = []
current_date = start_date
while current_date <= end_date:
    digests = repo.get_by_date(current_date)
    all_digests.extend([d for d in digests if 'Psychedelics' in d.topic])
    current_date += timedelta(days=1)

# Filter to only digests with substantial script content (>3000 chars)
targets = [d for d in all_digests if d.script_content and len(d.script_content) > 3000]

print(f"Found {len(targets)} Psychedelics and Spirituality digests to regenerate\n")

if len(targets) == 0:
    print("No digests with substantial content found. Exiting.")
    exit(0)

generator = AudioGenerator()

for idx, digest in enumerate(targets, 1):
    print(f"\n[{idx}/{len(targets)}] {digest.topic}")
    print(f"  Date: {digest.digest_date}")
    print(f"  Digest ID: {digest.id}")
    print(f"  Script: {len(digest.script_content)} chars")

    # Delete old MP3 if exists
    if digest.mp3_path:
        old_mp3 = Path(digest.mp3_path)
        if old_mp3.exists():
            old_mp3.unlink()
            print(f"  Deleted old MP3")
        # Clear in database to trigger republishing
        repo.update_audio(digest.id, None, 0, "", "")

    print(f"  Generating audio with v3 + chunking...")
    try:
        metadata = generator.generate_audio_for_digest(digest)
        print(f"  ✅ SUCCESS: {Path(metadata.file_path).name}")
        print(f"     Size: {metadata.file_size_bytes:,} bytes")
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        import traceback
        traceback.print_exc()

print("\n✅ Psychedelics and Spirituality regeneration complete")
