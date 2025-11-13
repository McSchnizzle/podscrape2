"""
Test dialogue chunker in isolation to diagnose the issue.
"""
from src.audio.dialogue_chunker import chunk_dialogue_script
from src.database.models import get_digest_repo
from datetime import date

# Get the problematic script
repo = get_digest_repo()
digests = repo.get_by_date(date(2025, 11, 10))

target_digest = None
for digest in digests:
    if 'Community' in digest.topic and '03:35:41' in str(digest.digest_timestamp):
        target_digest = digest
        break

if not target_digest:
    print("Could not find target digest")
    exit(1)

print(f"Testing chunker with: {target_digest.topic}")
print(f"Script length: {len(target_digest.script_content)} chars")
print()

# Run chunker
max_chunk_size = 2500
print(f"Running chunker with max_chunk_size={max_chunk_size}...")
print()

try:
    chunks = chunk_dialogue_script(target_digest.script_content, max_chunk_size=max_chunk_size)

    print(f"✓ Created {len(chunks)} chunks")
    print()

    # Validate each chunk
    errors = []
    for chunk in chunks:
        print(f"Chunk {chunk.chunk_number}:")
        print(f"  Characters: {chunk.char_count}")
        print(f"  Turns: {chunk.turn_count}")
        print(f"  Speakers: {chunk.speakers}")

        # Check if chunk exceeds limit
        if chunk.char_count > max_chunk_size:
            error_msg = f"  ❌ EXCEEDS LIMIT: {chunk.char_count} > {max_chunk_size}"
            print(error_msg)
            errors.append(error_msg)

            # Show problematic content
            print(f"  First 200 chars: {chunk.text[:200]}")
        else:
            print(f"  ✓ Within limit")
        print()

    if errors:
        print(f"\n❌ CHUNKER FAILED: {len(errors)} chunks exceed limit")
        for error in errors:
            print(f"  {error}")
        exit(1)
    else:
        print(f"\n✅ SUCCESS: All {len(chunks)} chunks are within {max_chunk_size} char limit")
        exit(0)

except Exception as e:
    print(f"❌ Chunker raised exception: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
