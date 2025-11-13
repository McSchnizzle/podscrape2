# Community Organizing: Chunked Dialogue Implementation

**Date**: 2025-11-10
**Version**: v1.79
**Decision**: Full-length dialogue with chunked v3 API calls

---

## Executive Summary

Community Organizing digests will use the Text-to-Dialogue API with **intelligent chunking** to support full 15,000-20,000 character conversations between Young Jamal and Dakota H.

**Approach**: Split long dialogue scripts into 2,800 character chunks, send sequentially to Eleven v3 Text-to-Dialogue API, concatenate resulting MP3 files into single cohesive audio.

---

## Target Specifications

| Metric | Value |
|--------|-------|
| **Script Length** | 15,000-20,000 characters |
| **Chunk Size** | ~2,800 characters (under 3,000 limit) |
| **Chunks Per Digest** | 6-8 chunks |
| **API Calls** | 6-8 sequential v3 calls |
| **Processing Time** | ~8-12 seconds (sequential) |
| **Monthly Cost** | ~$100-200 (estimated, infrequent generation) |

---

## Chunking Algorithm

### Requirements

1. **Preserve dialogue structure**: Never split in middle of a speaker's turn
2. **Track speaker continuity**: Know which speaker ended previous chunk
3. **Natural boundaries**: Split at paragraph/topic transitions when possible
4. **Character limit safety**: Stay under 3,000 chars with buffer

### Chunking Logic

```python
def chunk_dialogue_script(script: str, max_chunk_size: int = 2800) -> list[dict]:
    """
    Intelligently chunk dialogue script for v3 Text-to-Dialogue API.

    Returns:
        List of chunks with metadata:
        [
            {
                "chunk_number": 1,
                "text": "SPEAKER_1: ... SPEAKER_2: ...",
                "char_count": 2750,
                "starts_with": "SPEAKER_1",
                "ends_with": "SPEAKER_2"
            },
            ...
        ]
    """
    chunks = []
    current_chunk = []
    current_length = 0
    last_speaker = None

    # Split script into individual speaker turns
    lines = script.strip().split('\n')
    speaker_turns = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith('SPEAKER_1:') or line.startswith('SPEAKER_2:'):
            speaker = 'SPEAKER_1' if line.startswith('SPEAKER_1:') else 'SPEAKER_2'
            text = line.split(':', 1)[1].strip()
            speaker_turns.append({
                'speaker': speaker,
                'text': text,
                'length': len(line)
            })

    # Group turns into chunks
    for turn in speaker_turns:
        turn_text = f"{turn['speaker']}: {turn['text']}"
        turn_length = len(turn_text) + 1  # +1 for newline

        # Check if adding this turn would exceed chunk size
        if current_length + turn_length > max_chunk_size and current_chunk:
            # Finalize current chunk
            chunk_text = '\n'.join(current_chunk)
            chunks.append({
                'chunk_number': len(chunks) + 1,
                'text': chunk_text,
                'char_count': current_length,
                'starts_with': current_chunk[0].split(':')[0],
                'ends_with': last_speaker
            })

            # Start new chunk
            current_chunk = []
            current_length = 0

        # Add turn to current chunk
        current_chunk.append(turn_text)
        current_length += turn_length
        last_speaker = turn['speaker']

    # Add final chunk
    if current_chunk:
        chunk_text = '\n'.join(current_chunk)
        chunks.append({
            'chunk_number': len(chunks) + 1,
            'text': chunk_text,
            'char_count': current_length,
            'starts_with': current_chunk[0].split(':')[0],
            'ends_with': last_speaker
        })

    return chunks
```

---

## Text-to-Dialogue API Sequential Calls

### Processing Flow

```python
def generate_chunked_dialogue_audio(
    topic: Topic,
    script: str,
    output_dir: Path
) -> str:
    """
    Generate dialogue audio from chunked script.

    Returns:
        Path to final concatenated MP3 file
    """
    # Step 1: Chunk the script
    chunks = chunk_dialogue_script(script, max_chunk_size=2800)

    logger.info(f"Split script into {len(chunks)} chunks")
    for chunk in chunks:
        logger.info(f"  Chunk {chunk['chunk_number']}: {chunk['char_count']} chars, "
                   f"{chunk['starts_with']} → {chunk['ends_with']}")

    # Step 2: Generate audio for each chunk sequentially
    chunk_audio_files = []

    for chunk in chunks:
        logger.info(f"Generating audio for chunk {chunk['chunk_number']}/{len(chunks)}...")

        # Parse chunk into dialogue inputs
        dialogue_inputs = parse_dialogue_script(
            chunk['text'],
            topic.voice_config
        )

        # Call Text-to-Dialogue API
        response = requests.post(
            'https://api.elevenlabs.io/v1/text-to-dialogue',
            headers={
                'xi-api-key': elevenlabs_api_key,
                'Content-Type': 'application/json'
            },
            json={
                'inputs': dialogue_inputs,
                'model_id': 'eleven_v3',
                'apply_text_normalization': 'auto'
            },
            params={'output_format': 'mp3_44100_128'},
            timeout=60
        )

        if response.status_code != 200:
            raise Exception(f"Chunk {chunk['chunk_number']} failed: {response.status_code} - {response.text}")

        # Save chunk audio
        chunk_file = output_dir / f"chunk_{chunk['chunk_number']:02d}.mp3"
        chunk_file.write_bytes(response.content)
        chunk_audio_files.append(chunk_file)

        logger.info(f"  ✓ Chunk {chunk['chunk_number']} saved ({len(response.content)} bytes)")

    # Step 3: Concatenate all chunks into final MP3
    final_audio_path = concatenate_audio_chunks(chunk_audio_files, output_dir)

    # Step 4: Clean up chunk files
    for chunk_file in chunk_audio_files:
        chunk_file.unlink()

    logger.info(f"✓ Final dialogue audio: {final_audio_path}")
    return str(final_audio_path)
```

---

## Audio Concatenation

### Using FFmpeg

```python
def concatenate_audio_chunks(chunk_files: list[Path], output_dir: Path) -> Path:
    """
    Concatenate MP3 chunks into single file using ffmpeg.

    Uses concat demuxer for fast, lossless concatenation.
    """
    # Create concat list file
    concat_list = output_dir / "concat_list.txt"
    with concat_list.open('w') as f:
        for chunk_file in chunk_files:
            # FFmpeg concat format: file '/path/to/file.mp3'
            f.write(f"file '{chunk_file.absolute()}'\n")

    # Output file
    final_output = output_dir / "dialogue_full.mp3"

    # FFmpeg concat command
    cmd = [
        'ffmpeg',
        '-f', 'concat',
        '-safe', '0',
        '-i', str(concat_list),
        '-c', 'copy',  # Copy codec (no re-encoding, fast)
        '-y',  # Overwrite output file
        str(final_output)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise Exception(f"FFmpeg concatenation failed: {result.stderr}")

    # Clean up concat list
    concat_list.unlink()

    return final_output
```

### Alternative: Using pydub (Pure Python)

```python
from pydub import AudioSegment

def concatenate_audio_chunks_pydub(chunk_files: list[Path], output_dir: Path) -> Path:
    """
    Concatenate MP3 chunks using pydub (pure Python, no ffmpeg needed).
    """
    # Load all chunks
    combined = AudioSegment.empty()

    for chunk_file in chunk_files:
        audio = AudioSegment.from_mp3(chunk_file)
        combined += audio  # Concatenate

    # Export final MP3
    final_output = output_dir / "dialogue_full.mp3"
    combined.export(
        final_output,
        format='mp3',
        bitrate='128k',
        parameters=['-ar', '44100']
    )

    return final_output
```

**Recommendation**: Use **FFmpeg** (already required for audio processing) - faster and lossless.

---

## Error Handling

### Retry Logic for API Failures

```python
def call_text_to_dialogue_with_retry(
    dialogue_inputs: list[dict],
    max_retries: int = 3,
    retry_delay: int = 2
) -> bytes:
    """
    Call Text-to-Dialogue API with exponential backoff retry.
    """
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                'https://api.elevenlabs.io/v1/text-to-dialogue',
                headers={
                    'xi-api-key': elevenlabs_api_key,
                    'Content-Type': 'application/json'
                },
                json={
                    'inputs': dialogue_inputs,
                    'model_id': 'eleven_v3',
                    'apply_text_normalization': 'auto'
                },
                params={'output_format': 'mp3_44100_128'},
                timeout=60
            )

            if response.status_code == 200:
                return response.content

            # Log error but retry
            logger.warning(f"API call failed (attempt {attempt}/{max_retries}): "
                         f"{response.status_code} - {response.text}")

            if attempt < max_retries:
                sleep_time = retry_delay * (2 ** (attempt - 1))  # Exponential backoff
                logger.info(f"Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)

        except requests.exceptions.RequestException as e:
            logger.warning(f"Request exception (attempt {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                sleep_time = retry_delay * (2 ** (attempt - 1))
                time.sleep(sleep_time)

    # All retries failed
    raise Exception(f"Text-to-Dialogue API failed after {max_retries} attempts")
```

### Partial Failure Recovery

```python
def generate_chunked_dialogue_with_recovery(
    topic: Topic,
    script: str,
    output_dir: Path
) -> str:
    """
    Generate dialogue with recovery from partial failures.

    If chunks 1-4 succeed but chunk 5 fails, save progress and allow retry.
    """
    chunks = chunk_dialogue_script(script)

    # Check for existing progress
    progress_file = output_dir / "progress.json"
    if progress_file.exists():
        progress = json.loads(progress_file.read_text())
        completed_chunks = set(progress['completed'])
        logger.info(f"Resuming from previous run, {len(completed_chunks)} chunks already complete")
    else:
        completed_chunks = set()
        progress = {'completed': [], 'failed': []}

    chunk_audio_files = []

    for chunk in chunks:
        chunk_num = chunk['chunk_number']
        chunk_file = output_dir / f"chunk_{chunk_num:02d}.mp3"

        # Skip if already completed
        if chunk_num in completed_chunks and chunk_file.exists():
            logger.info(f"Chunk {chunk_num} already completed, skipping")
            chunk_audio_files.append(chunk_file)
            continue

        try:
            # Generate chunk audio
            dialogue_inputs = parse_dialogue_script(chunk['text'], topic.voice_config)
            audio_data = call_text_to_dialogue_with_retry(dialogue_inputs)

            # Save chunk
            chunk_file.write_bytes(audio_data)
            chunk_audio_files.append(chunk_file)

            # Update progress
            completed_chunks.add(chunk_num)
            progress['completed'].append(chunk_num)
            progress_file.write_text(json.dumps(progress, indent=2))

            logger.info(f"✓ Chunk {chunk_num}/{len(chunks)} complete")

        except Exception as e:
            logger.error(f"✗ Chunk {chunk_num} failed: {e}")
            progress['failed'].append({'chunk': chunk_num, 'error': str(e)})
            progress_file.write_text(json.dumps(progress, indent=2))
            raise Exception(f"Chunk {chunk_num} failed, progress saved. Retry generation to resume.")

    # All chunks complete, concatenate
    final_audio = concatenate_audio_chunks(chunk_audio_files, output_dir)

    # Clean up progress and chunks
    progress_file.unlink()
    for chunk_file in chunk_audio_files:
        chunk_file.unlink()

    return str(final_audio)
```

---

## Script Generation Updates

### ScriptGenerator Prompt Changes

```python
def _generate_dialogue_script(self, topic, episodes) -> str:
    """
    Generate dialogue-format script for Community Organizing with v3 audio tags.

    Target: 15,000-20,000 characters (will be chunked for v3 API).
    Uses v3 audio tags for full emotional range and expression.
    """
    system_prompt = f"""You are creating a Community Organizing digest as a natural conversation
    between two speakers: Young Jamal (community organizer) and Dakota H (activist).

    CRITICAL REQUIREMENTS:
    - Target script length: 15,000-20,000 characters
    - Format: SPEAKER_1: / SPEAKER_2: dialogue labels
    - USE AUDIO TAGS for emotional expression (v3 feature)
    - Natural conversation with back-and-forth discussion
    - Cover 5-7 key highlights from the episodes
    - Use conversational language, contractions, reactions
    - Each speaker turn: 150-300 characters (short, natural exchanges)

    AUDIO TAGS (Use liberally for emotional warmth and expression):
    - [excited] - for victories, breakthroughs, inspiring moments
    - [thoughtful] - for analysis, reflection, strategic discussion
    - [passionate] - for calls to action, urgent issues
    - [conversational tone] - for casual, friendly exchanges
    - [serious tone] - for challenges, setbacks, important context
    - [laughs] - for light moments, irony, camaraderie
    - [sighs] - for frustration, disappointment
    - [emphatic] - for key points, emphasis
    - [warm] - for community connection, solidarity

    Speaker Personalities:
    - SPEAKER_1 (Young Jamal): Community organizer perspective, strategic, experienced, warm
    - SPEAKER_2 (Dakota H): Activist perspective, passionate, grassroots focus, energetic

    Format Example with Audio Tags:
    SPEAKER_1: [excited] Hey, this week brought some incredible wins in tenant organizing! The Minneapolis union just secured rent stabilization for over fifty thousand households.

    SPEAKER_2: [passionate] That's huge! What really stood out to me was [thoughtful] how they built that coalition over two years. They didn't just chase policy wins—they went block by block, building by building, creating real relationships.

    SPEAKER_1: [emphatic] Exactly. That's the blueprint right there. [conversational tone] Strong local organizing, clear demands, and they managed to bring together tenants across race and class lines. That's how you build lasting power.

    SPEAKER_2: [warm] And that's what gives me hope. When communities organize from the ground up like that, [serious tone] they're not just winning individual campaigns—they're building the infrastructure for long-term change.

    Episode Data:
    {self._format_episodes_for_prompt(episodes)}

    Generate a comprehensive dialogue covering the key themes and highlights from these episodes.
    Target length: 15,000-20,000 characters.
    """

    response = openai.ChatCompletion.create(
        model='gpt-4',
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': 'Generate the Community Organizing dialogue digest.'}
        ],
        temperature=0.7,
        max_tokens=6000  # Enough for 15-20k char response
    )

    script = response.choices[0].message.content.strip()

    # Validate length
    char_count = len(script)
    if char_count < 10000:
        logger.warning(f"Script too short: {char_count} chars (target 15k-20k)")
    elif char_count > 25000:
        logger.warning(f"Script too long: {char_count} chars (target 15k-20k), will truncate")
        script = script[:24000]  # Truncate to reasonable length

    logger.info(f"Generated dialogue script: {char_count} characters")

    return script
```

---

## AudioGenerator Integration

### Updated generate_audio() Method

```python
def generate_audio(self, topic_name: str, script: str) -> str:
    """Route to appropriate TTS method based on topic configuration."""
    topic = self._get_topic_config(topic_name)

    if topic.use_dialogue_api:
        return self._generate_chunked_dialogue_audio(topic, script)
    else:
        return self._generate_single_voice_audio(topic, script)

def _generate_chunked_dialogue_audio(self, topic: Topic, script: str) -> str:
    """
    Generate multi-speaker dialogue audio with chunking for long scripts.

    Handles scripts up to 25,000 characters by chunking into 2,800 char segments.
    """
    # Create temp directory for chunks
    temp_dir = Path(tempfile.mkdtemp(prefix='dialogue_chunks_'))

    try:
        # Generate chunked dialogue audio
        final_audio_path = generate_chunked_dialogue_with_recovery(
            topic,
            script,
            temp_dir
        )

        # Move to final location
        final_destination = self._get_output_path(topic.name)
        shutil.move(final_audio_path, final_destination)

        return str(final_destination)

    finally:
        # Clean up temp directory
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
```

---

## Cost Analysis

### Estimated Monthly Costs

**Assumptions**:
- Community Organizing digest generated 2-3 times per week (not daily)
- Average script: 17,500 characters
- Chunks per digest: 7 chunks @ 2,500 chars each

**Per Digest Cost**:
- 7 API calls × 2,500 chars = 17,500 chars
- Eleven v3 pricing: ~$0.30 per 1,000 characters (standard tier)
- Cost per digest: **$5.25**

**Monthly Cost**:
- 10 digests/month × $5.25 = **$52.50/month**
- Within Pro plan limits (included v3 credits)

**Annual Cost**: ~$630/year for Community Organizing dialogue

---

## Performance Characteristics

### Latency

| Phase | Time |
|-------|------|
| Script generation | ~10-15 seconds (GPT-4) |
| Chunking | <1 second |
| API calls (7 chunks) | ~7-10 seconds (sequential, 1s each) |
| Audio concatenation | ~1-2 seconds (ffmpeg) |
| **Total** | **~18-28 seconds** |

**Comparison**:
- Single-voice Turbo v2.5: ~2-3 seconds
- Short v3 dialogue (single call): ~2-3 seconds
- Chunked v3 dialogue: ~18-28 seconds

**Trade-off accepted**: 10x latency for natural full-length dialogue

---

## V3 Audio Tags - Full Emotional Range

### Why V3 Audio Tags Matter

Audio tags give you **fine-grained control over emotional delivery**, creating warmer, more engaging content that feels like a real conversation between people who care about the topics.

### Complete Audio Tag Reference

**Emotional Tags**:
- `[excited]` - High energy, enthusiasm, celebration
- `[happy]` - Positive, upbeat, cheerful
- `[sad]` - Somber, melancholic, disappointed
- `[angry]` - Frustration, outrage, intensity
- `[nervous]` - Uncertainty, concern, worry
- `[calm]` - Composed, steady, reassuring
- `[passionate]` - Driven, intense, motivated
- `[thoughtful]` - Reflective, analytical, considering
- `[warm]` - Friendly, comforting, supportive
- `[emphatic]` - Strong emphasis, conviction

**Delivery Tags**:
- `[whispers]` - Quiet, confidential, intimate
- `[shouts]` - Loud, urgent, commanding attention
- `[sighs]` - Disappointment, resignation, relief
- `[laughs]` - Amusement, joy, lightness
- `[gasps]` - Surprise, shock, realization
- `[exhales]` - Relief, release, transition

**Tone Tags**:
- `[conversational tone]` - Natural, casual, friendly
- `[serious tone]` - Grave, important, focused
- `[sarcastic]` - Ironic, dry humor, playful critique
- `[matter-of-fact]` - Straightforward, informational
- `[reflective]` - Contemplative, looking back

**Style Tags**:
- `[starts laughing]` / `[stops laughing]` - Transition markers
- `[interrupting]` - Cut into conversation
- `[trailing off]` - Incomplete thought, fade out

### Usage Guidelines

**1. Use tags liberally** - Don't be shy! V3 is designed for expressive dialogue:
```
❌ SPEAKER_1: This is an important victory for the movement.
✅ SPEAKER_1: [excited] This is an important victory for the movement!
```

**2. Combine tags within a single turn**:
```
SPEAKER_2: [thoughtful] You know, when I look at this organizing campaign... [excited] it's actually brilliant how they approached coalition building!
```

**3. Match emotional arc to content**:
- Victories: `[excited]`, `[passionate]`, `[warm]`
- Analysis: `[thoughtful]`, `[serious tone]`, `[reflective]`
- Challenges: `[sighs]`, `[sad]`, `[emphatic]`
- Light moments: `[laughs]`, `[conversational tone]`

**4. Create emotional contrast**:
```
SPEAKER_1: [excited] The campaign won!
SPEAKER_2: [serious tone] But we need to talk about what comes next.
SPEAKER_1: [thoughtful] You're right. The real work is just beginning.
```

### Example: Full Dialogue with Rich Audio Tags

```
SPEAKER_1: [excited] Okay, so this week was absolutely packed with organizing wins! [conversational tone] Where do we even start?

SPEAKER_2: [laughs] Right? There's so much happening! [thoughtful] But I think we should talk about what's going on in Minneapolis with the tenants' union. [passionate] They just secured rent stabilization for over fifty thousand households!

SPEAKER_1: [emphatic] Fifty thousand! [warm] That's life-changing for so many families. [serious tone] But what really gets me is the strategy behind it. This wasn't some top-down policy push.

SPEAKER_2: [excited] Exactly! [conversational tone] They spent two full years doing the ground work—block by block, building by building. [thoughtful] Just creating relationships, building trust, understanding what people actually need.

SPEAKER_1: [reflective] And that's the model, isn't it? [emphatic] You can't build real power without those relationships. [warm] When you bring people together across race, across class, across neighborhoods... that's when movements become unstoppable.

SPEAKER_2: [passionate] Yes! [sighs] And it's frustrating because we see the opposite happening in some places. [serious tone] Campaigns that rush to policy without building the base first. They might get short-term wins, but—

SPEAKER_1: [interrupting] [thoughtful] But they don't build the infrastructure for sustained change. Right. [conversational tone] Okay, so what else caught your attention this week?

SPEAKER_2: [excited] The mutual aid networks in Atlanta! [warm] During those storms, community members set up distribution centers faster than FEMA could respond.
```

This creates a **living, breathing conversation** - not just information delivery, but two people genuinely engaging with the material and each other.

---

## Future: Migrating Other Topics to V3

### Current Configuration

| Topic | Model | Reason |
|-------|-------|--------|
| Community Organizing | **eleven_v3** | Dialogue mode + emotional range |
| AI & Technology | eleven_turbo_v2_5 | Single voice, long-form (40k limit) |
| Psychedelics | eleven_turbo_v2_5 | Single voice, long-form (40k limit) |

### Migration Path (When Ready)

**If you decide to move AI & Technology or Psychedelics to v3:**

**Option 1**: Single-voice v3 (no chunking needed for 3k limit)
```sql
-- Switch to v3 but keep single-voice
UPDATE topics
SET dialogue_model = 'eleven_v3'
WHERE name = 'AI and Technology';
-- Scripts would need to be shortened to <3k or implement chunking
```

**Option 2**: Enable chunking for full-length scripts
```sql
-- Use v3 with chunking (like Community Organizing)
UPDATE topics
SET
    dialogue_model = 'eleven_v3',
    use_dialogue_api = FALSE  -- Single voice, not dialogue
WHERE name = 'AI and Technology';
```

**Benefits of V3 for Other Topics**:
- ✅ Audio tags for emotional warmth: `[excited]` for breakthroughs, `[thoughtful]` for analysis
- ✅ Better prosody and naturalness
- ✅ More engaging listening experience

**Cost Impact**:
- Current (Turbo v2.5): Included in Pro plan
- V3 (single voice, chunked): ~$3-4/digest
- Total monthly (if all 3 topics): ~$100-150/month for daily digests

**The Database Already Supports It**: Just update `dialogue_model` column, no code changes!

---

## Database Configuration (Already Complete)

```sql
-- Community Organizing is already configured for dialogue mode
SELECT
    name,
    use_dialogue_api,
    dialogue_model,
    voice_config
FROM topics
WHERE name = 'Social Movements and Community Organizing';

-- Result:
-- use_dialogue_api: TRUE
-- dialogue_model: eleven_v3
-- voice_config: {"speaker_1": {"name": "Young Jamal", "voice_id": "6OzrBCQf8cjERkYgzSg8"}, ...}
```

---

## Implementation Checklist

### Phase 1: Core Chunking Logic
- [ ] Add `chunk_dialogue_script()` function to new module: `src/audio/dialogue_chunker.py`
- [ ] Add unit tests for chunking at dialogue boundaries
- [ ] Test with sample 15k-20k character scripts

### Phase 2: API Integration
- [ ] Add `call_text_to_dialogue_with_retry()` with exponential backoff
- [ ] Add `generate_chunked_dialogue_audio()` sequential processing
- [ ] Add progress tracking and recovery logic

### Phase 3: Audio Concatenation
- [ ] Add `concatenate_audio_chunks()` using ffmpeg
- [ ] Test concatenation quality (no gaps, consistent volume)
- [ ] Add cleanup for temporary chunk files

### Phase 4: ScriptGenerator Updates
- [ ] Update `_generate_dialogue_script()` prompt for 15k-20k target
- [ ] Add dialogue format validation
- [ ] Test with real episode data

### Phase 5: AudioGenerator Integration
- [ ] Update `generate_audio()` routing logic
- [ ] Add `_generate_chunked_dialogue_audio()` method
- [ ] Handle temp directories and cleanup

### Phase 6: End-to-End Testing
- [ ] Generate Community Organizing digest (full pipeline)
- [ ] Verify script is 15k-20k characters
- [ ] Verify 6-8 API calls made
- [ ] Listen to final MP3 for quality
- [ ] Test error recovery (simulate chunk failure)

### Phase 7: Production Deployment
- [ ] Update documentation
- [ ] Add monitoring for chunked dialogue generation
- [ ] Deploy and test in production

---

## Success Metrics

- ✅ Scripts consistently 15,000-20,000 characters
- ✅ 6-8 chunks per digest
- ✅ Natural dialogue flow across chunk boundaries
- ✅ No audible gaps or artifacts in concatenated audio
- ✅ <30 second total generation time
- ✅ Graceful handling of API failures with recovery

---

## Future Enhancements

### Intelligent Chunking Improvements

1. **Topic-aware chunking**: Split at topic transitions, not arbitrary boundaries
2. **Balanced speakers**: Ensure roughly equal speaking time across chunks
3. **Dynamic chunk sizing**: Adjust chunk size based on content (2,500-2,900 chars)

### Audio Quality Improvements

1. **Crossfade**: Add 50ms crossfade between chunks for smoother transitions
2. **Volume normalization**: Ensure consistent volume across chunks
3. **Prosody matching**: Analyze ending/starting prosody to improve continuity

### Cost Optimization

1. **Caching**: Cache chunk audio for retry scenarios
2. **Parallel processing**: If ElevenLabs allows, parallelize independent chunks
3. **Compression**: Use more efficient audio formats for intermediate chunks

---

## Resources

- **ElevenLabs Text-to-Dialogue API**: https://elevenlabs.io/docs/capabilities/text-to-dialogue
- **FFmpeg Concat**: https://trac.ffmpeg.org/wiki/Concatenate
- **Test Audio**: `/Users/paulbrown/Music/test_dialogue_young_jamal_dakota.mp3`
- **Implementation Status**: `docs/VOICE_IMPLEMENTATION_STATUS.md`

---

## Summary

Community Organizing digests will feature **full 15-20k character conversations** between Young Jamal and Dakota H, chunked intelligently and processed through Eleven v3's Text-to-Dialogue API. The chunking approach maintains the natural dialogue quality you loved in the test audio while supporting comprehensive episode coverage.

**Trade-offs Accepted**:
- ✅ Higher cost (~$5/digest vs $1/digest for single-voice)
- ✅ Longer processing time (~20s vs 2s)
- ✅ Increased complexity (chunking, concatenation, error recovery)

**Value Delivered**:
- 🎉 Natural multi-speaker dialogue across full conversation
- 🎉 Comprehensive coverage (5-7 episode highlights)
- 🎉 Young Jamal + Dakota H engaging, authentic discussion
- 🎉 Single cohesive MP3 file output

The implementation provides the best of both worlds: the dialogue quality that excited you in the test audio, plus the depth and comprehensiveness of full-length digests.
