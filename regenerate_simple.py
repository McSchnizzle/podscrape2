"""
Simple regeneration test with clear output.
"""
import sys
from src.database.models import get_digest_repo
from src.audio.audio_generator import AudioGenerator
from datetime import date

print("Finding digest...")
repo = get_digest_repo()
digests = repo.get_by_date(date(2025, 11, 10))

target = None
for d in digests:
    if 'Community' in d.topic and '03:35:41' in str(d.digest_timestamp):
        target = d
        break

if not target:
    print("ERROR: Could not find target digest")
    sys.exit(1)

print(f"✓ Found: {target.topic}")
print(f"  Digest ID: {target.id}")
print(f"  Script: {len(target.script_content)} chars")
print()

print("Generating audio...")
generator = AudioGenerator()

try:
    metadata = generator.generate_audio_for_digest(target)
    print(f"\n✅ SUCCESS!")
    print(f"  File: {metadata.file_path}")
    print(f"  Size: {metadata.file_size_bytes:,} bytes")
    print(f"  Duration: ~{metadata.duration_seconds:.0f}s")
except Exception as e:
    print(f"\n❌ FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
