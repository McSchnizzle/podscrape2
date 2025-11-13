"""
Regenerate AI and Technology digests from Nov 9 onwards with eleven_v3 model.
"""
from src.database.models import get_digest_repo
from src.audio.audio_generator import AudioGenerator
from datetime import date
from pathlib import Path

print("Finding AI and Technology digests from Nov 9 onwards...")
repo = get_digest_repo()

# Get AI and Tech digests from Nov 9-11
dates = [date(2025, 11, 9), date(2025, 11, 10), date(2025, 11, 11)]

all_digests = []
for d in dates:
    digests = repo.get_by_date(d)
    all_digests.extend([dig for dig in digests if 'AI and Technology' in dig.topic])

# Filter to only digests with substantial script content (>3000 chars)
targets = [d for d in all_digests if d.script_content and len(d.script_content) > 3000]

print(f"Found {len(targets)} AI and Technology digests to regenerate\n")

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

print("\n✅ AI and Technology regeneration complete")
