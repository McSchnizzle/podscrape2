"""
Test what _parse_dialogue_script produces from chunks.
"""
from src.audio.dialogue_chunker import chunk_dialogue_script
from src.database.models import get_digest_repo, get_topic_repo
from datetime import date
import re

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

# Get voice config
topic_repo = get_topic_repo()
topics = topic_repo.get_all_topics()
topic_config = next((t for t in topics if t.name == target_digest.topic), None)

print(f"Topic: {target_digest.topic}")
print(f"Voice config: {topic_config.voice_config}")
print()

# Chunk the script
chunks = chunk_dialogue_script(target_digest.script_content, max_chunk_size=2500)
print(f"Created {len(chunks)} chunks")
print()

# Parse each chunk like the audio generator does
voice_config = topic_config.voice_config
speaker_to_voice = {}
for speaker_name, config in voice_config.items():
    if isinstance(config, dict) and 'voice_id' in config:
        normalized_name = speaker_name.upper().replace('_', '_')
        if not normalized_name.startswith('SPEAKER_'):
            normalized_name = f'SPEAKER_{normalized_name.split("_")[-1]}'
        speaker_to_voice[normalized_name] = config['voice_id']

print(f"Speaker mappings: {speaker_to_voice}")
print()

# Parse each chunk
pattern = re.compile(r'^(SPEAKER_[12])(?:\s*\([^)]+\))?:\s*(.+?)(?=^SPEAKER_[12](?:\s*\([^)]+\))?:|\Z)', re.MULTILINE | re.DOTALL)

all_ok = True
for chunk in chunks:
    print(f"Chunk {chunk.chunk_number} ({chunk.char_count} chars, {chunk.turn_count} turns):")

    # Parse this chunk
    dialogue_inputs = []
    for match in pattern.finditer(chunk.text):
        speaker_name = match.group(1)
        text = match.group(2).strip()
        voice_id = speaker_to_voice.get(speaker_name)

        if voice_id:
            dialogue_inputs.append({"voice_id": voice_id, "text": text})

    print(f"  Parsed {len(dialogue_inputs)} turns")

    # Check each turn's length
    for idx, turn in enumerate(dialogue_inputs):
        turn_len = len(turn['text'])
        if turn_len > 3000:  # ElevenLabs API limit
            print(f"  ❌ Turn {idx+1}: {turn_len} chars (EXCEEDS 3000 limit!)")
            print(f"     First 100 chars: {turn['text'][:100]}")
            all_ok = False
        elif turn_len > 2500:
            print(f"  ⚠️  Turn {idx+1}: {turn_len} chars (close to limit)")
        else:
            print(f"  ✓ Turn {idx+1}: {turn_len} chars")

    print()

if all_ok:
    print("✅ All individual turns are under the 3000 char API limit")
else:
    print("❌ Some turns exceed the API limit and will be rejected")
