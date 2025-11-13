# ElevenLabs Text-to-Dialogue Implementation Guide

## Executive Summary

✅ **GOOD NEWS:** The Text-to-Dialogue API works perfectly and generates natural, multi-speaker dialogue in a SINGLE audio file!

⚠️ **CRITICAL TRADE-OFF:** Text-to-Dialogue **ONLY** works with Eleven v3, which has a **3,000 character limit**.

---

## The Core Decision

You must choose between two incompatible features:

### Option A: Turbo v2.5 (Current Setup) - Long Form, Single Voice
- ✅ **40,000 character limit** - fits entire 15k digest in one API call
- ✅ **50% cost savings** vs v3
- ✅ **Production-stable**
- ✅ **Low latency** (250-300ms)
- ❌ **NO multi-speaker dialogue** - would require audio concatenation (robotic)

### Option B: Eleven v3 Text-to-Dialogue - Natural Dialogue, Short Form
- ✅ **Native multi-speaker dialogue** in single audio file
- ✅ **Natural conversation flow** with emotional range
- ✅ **Audio tags** for fine-grained expression
- ❌ **3,000 character limit** - must split 15k digests into 5+ chunks
- ❌ **13x smaller limit** than Turbo v2.5
- ❌ **Alpha status** - may have instability
- ❌ **2x cost** (standard pricing)

---

## Test Results: Young Jamal + Dakota H

**Voice IDs Found:**
- **Young Jamal**: `6OzrBCQf8cjERkYgzSg8` (young male, American, chill, social media)
- **Dakota H**: `P7x743VjyZEOihNNygQ9` (middle-aged female, American, pleasant, conversational)

**Test Dialogue:**
- ✅ Successfully generated 541 character dialogue
- ✅ Returned single MP3 file (494 KB)
- ✅ Natural back-and-forth conversation
- ✅ Both voices distinct and clear

**Audio File Location:** `/tmp/test_dialogue_young_jamal_dakota.mp3`

**Recommendation:** Listen to this test file to hear how the dialogue sounds!

---

## Character Limit Deep Dive

### Your Digest Lengths (Estimated)

| Topic | Avg Characters | With v3 (3k limit) | With Turbo v2.5 (40k limit) |
|-------|---------------|-------------------|----------------------------|
| AI & Technology | 12,000 | **4 API calls** | **1 API call** |
| Psychedelics | 10,000 | **3-4 API calls** | **1 API call** |
| Community Organizing | 15,000 | **5 API calls** | **1 API call** |

### The Real Problem with Splitting

When you split a 15,000 character digest into 5 chunks:

**Technical Issues:**
- Must track dialogue state across chunks (who spoke last)
- Need to merge 5 separate audio files
- Transition quality may degrade
- Increased error surface area (5x API calls = 5x failure points)

**Cost Impact:**
- 5x API calls per digest
- 2x pricing per call (v3 vs Turbo)
- **Total: 10x cost increase** for Community Organizing

**Latency:**
- 5 sequential API calls (can't parallelize dialogue continuity)
- Variable v3 latency > Turbo's 250ms
- **Estimated 5-10 seconds per digest** vs < 1 second

---

## Recommended Solution: Hybrid Approach

### Use BOTH models based on topic requirements

**Turbo v2.5 Topics** (Long-form, single narrator):
- AI & Technology
- Psychedelics & Spirituality

**Eleven v3 Topics** (Dialogue-based, shorter scripts):
- Community Organizing

### Why This Works

**Community Organizing Optimization:**
1. **Shorten scripts to 2,500-2,800 characters** (fits v3 limit)
2. Focus on 2-3 key highlights instead of 5
3. More concise, punchy dialogue format
4. Natural for "hot take" conversation style

**Example Structure:**
```
INTRO (200 chars)
HIGHLIGHT 1 - Discussion (800 chars)
HIGHLIGHT 2 - Discussion (800 chars)
HIGHLIGHT 3 - Discussion (700 chars)
CLOSING (300 chars)
---
Total: ~2,800 characters
```

**Benefits:**
- ✅ Single v3 API call (no splitting needed)
- ✅ Natural multi-speaker dialogue
- ✅ Keeps Young Jamal + Dakota H conversation feel
- ✅ Faster to consume (5-7 min vs 15-20 min audio)
- ✅ Better for "hot topics social media" use case

---

## API Implementation

### Text-to-Dialogue Request Format

```python
import requests
import os

api_key = os.getenv('ELEVENLABS_API_KEY')

dialogue_data = {
    "inputs": [
        {
            "text": "First speaker's text here",
            "voice_id": "6OzrBCQf8cjERkYgzSg8"  # Young Jamal
        },
        {
            "text": "Second speaker's response",
            "voice_id": "P7x743VjyZEOihNNygQ9"  # Dakota H
        },
        {
            "text": "First speaker continues...",
            "voice_id": "6OzrBCQf8cjERkYgzSg8"  # Young Jamal
        }
    ],
    "model_id": "eleven_v3",
    "apply_text_normalization": "auto"
}

headers = {
    'xi-api-key': api_key,
    'Content-Type': 'application/json'
}

response = requests.post(
    'https://api.elevenlabs.io/v1/text-to-dialogue',
    headers=headers,
    json=dialogue_data,
    params={'output_format': 'mp3_44100_128'}
)

if response.status_code == 200:
    with open('dialogue.mp3', 'wb') as f:
        f.write(response.content)
```

### Digest Script Format

Update `src/generation/script_generator.py` to generate:

```markdown
## Community Organizing Digest - [Date]

### Intro
[First speaker introduces the topic - 150-200 chars]

### Highlight 1: [Topic]
SPEAKER_1: [Opening statement about first highlight - 200-250 chars]
SPEAKER_2: [Response and analysis - 200-250 chars]
SPEAKER_1: [Follow-up point - 150-200 chars]

### Highlight 2: [Topic]
SPEAKER_2: [Opens second highlight - 200-250 chars]
SPEAKER_1: [Builds on it - 200-250 chars]
SPEAKER_2: [Key insight - 150-200 chars]

### Highlight 3: [Topic]
SPEAKER_1: [Third highlight intro - 200-250 chars]
SPEAKER_2: [Analysis and connection - 200-250 chars]

### Closing
SPEAKER_1: [Wrap up and call to action - 100-150 chars]
SPEAKER_2: [Final thought - 100-150 chars]
```

---

## Database Configuration

### Add Multi-Model Support to Topics Table

```sql
-- Add columns for v3 dialogue configuration
ALTER TABLE topics
ADD COLUMN use_dialogue_api BOOLEAN DEFAULT FALSE,
ADD COLUMN dialogue_model VARCHAR(50) DEFAULT 'eleven_turbo_v2_5',
ADD COLUMN voice_config JSONB;  -- For multi-voice setup

-- Configure Community Organizing for v3 dialogue
UPDATE topics
SET
    use_dialogue_api = TRUE,
    dialogue_model = 'eleven_v3',
    voice_config = '{
        "speaker_1": {
            "name": "Young Jamal",
            "voice_id": "6OzrBCQf8cjERkYgzSg8",
            "role": "community_organizer"
        },
        "speaker_2": {
            "name": "Dakota H",
            "voice_id": "P7x743VjyZEOihNNygQ9",
            "role": "activist"
        }
    }'::jsonb
WHERE name = 'Social Movements and Community Organizing';

-- Keep other topics on Turbo v2.5
UPDATE topics
SET
    use_dialogue_api = FALSE,
    dialogue_model = 'eleven_turbo_v2_5'
WHERE name IN ('AI and Technology', 'Psychedelics and Spirituality');
```

---

## Code Changes Required

### 1. Update AudioGenerator (`src/audio/audio_generator.py`)

Add dialogue detection and routing:

```python
def generate_audio(self, topic_name: str, script: str) -> str:
    """Generate audio using appropriate API based on topic configuration."""

    topic = self._get_topic_config(topic_name)

    if topic.use_dialogue_api:
        return self._generate_dialogue_audio(topic, script)
    else:
        return self._generate_single_voice_audio(topic, script)

def _generate_dialogue_audio(self, topic, script: str) -> str:
    """Generate multi-speaker dialogue using v3 API."""

    # Parse script for speaker labels
    dialogue_inputs = self._parse_dialogue_script(script, topic.voice_config)

    # Validate character limit
    total_chars = sum(len(input['text']) for input in dialogue_inputs)
    if total_chars > 3000:
        logger.warning(f"Dialogue script exceeds 3000 chars ({total_chars}), may need splitting")

    # Call Text-to-Dialogue API
    response = requests.post(
        'https://api.elevenlabs.io/v1/text-to-dialogue',
        headers={
            'xi-api-key': self.api_key,
            'Content-Type': 'application/json'
        },
        json={
            'inputs': dialogue_inputs,
            'model_id': 'eleven_v3',
            'apply_text_normalization': 'auto'
        },
        params={'output_format': 'mp3_44100_128'}
    )

    if response.status_code == 200:
        return self._save_audio_file(response.content, topic_name)
    else:
        raise Exception(f"Dialogue API failed: {response.status_code} - {response.text}")

def _parse_dialogue_script(self, script: str, voice_config: dict) -> list:
    """Parse script with SPEAKER_1/SPEAKER_2 labels into dialogue inputs."""

    dialogue_inputs = []
    lines = script.split('\n')

    for line in lines:
        line = line.strip()
        if line.startswith('SPEAKER_1:'):
            text = line.replace('SPEAKER_1:', '').strip()
            voice_id = voice_config['speaker_1']['voice_id']
            dialogue_inputs.append({'text': text, 'voice_id': voice_id})
        elif line.startswith('SPEAKER_2:'):
            text = line.replace('SPEAKER_2:', '').strip()
            voice_id = voice_config['speaker_2']['voice_id']
            dialogue_inputs.append({'text': text, 'voice_id': voice_id})

    return dialogue_inputs
```

### 2. Update Script Generator (`src/generation/script_generator.py`)

Add dialogue-specific prompting:

```python
def generate_digest(self, topic_name: str, episodes: list) -> str:
    """Generate digest script optimized for topic's TTS method."""

    topic = self._get_topic_config(topic_name)

    if topic.use_dialogue_api:
        return self._generate_dialogue_script(topic, episodes)
    else:
        return self._generate_narrative_script(topic, episodes)

def _generate_dialogue_script(self, topic, episodes) -> str:
    """Generate dialogue-format script for v3 Text-to-Dialogue API."""

    system_prompt = f"""You are creating a {topic.name} digest as a natural conversation
    between two speakers. Generate a dialogue format script with these requirements:

    CRITICAL: Keep total script under 2,800 characters (including speaker labels).

    Format:
    SPEAKER_1: [First speaker's text]
    SPEAKER_2: [Second speaker's response]

    Guidelines:
    - Focus on 2-3 key highlights only (be selective, not comprehensive)
    - Each speaker turn: 150-250 characters max
    - Natural conversation flow with back-and-forth
    - Use conversational language, contractions, casual tone
    - Include reactions ("Yeah!", "Right?", "Exactly")
    - Avoid formal academic language
    - Total script: 2,500-2,800 characters max

    Speaker Personalities:
    - SPEAKER_1 ({topic.voice_config.speaker_1.name}): {topic.voice_config.speaker_1.role}
    - SPEAKER_2 ({topic.voice_config.speaker_2.name}): {topic.voice_config.speaker_2.role}

    {topic.instructions_md}
    """

    # Generate with GPT
    # ... implementation
```

---

## Cost Analysis: Hybrid Approach

**Monthly Costs (30 digests):**

| Topic | Model | API Calls | Chars/Digest | Monthly Cost |
|-------|-------|-----------|--------------|--------------|
| AI & Tech | Turbo v2.5 | 30 x 1 | 12,000 | Included in Pro plan |
| Psychedelics | Turbo v2.5 | 30 x 1 | 10,000 | Included in Pro plan |
| Community Org | v3 | 30 x 1 | 2,800 | ~84,000 chars = ~$20-40/mo |

**Total:** Still well within your Pro plan limits (1M Turbo credits + v3 usage)

---

## Implementation Steps

### Phase 1: Database Schema (30 minutes)
1. Run SQL migration to add `use_dialogue_api`, `dialogue_model`, `voice_config` columns
2. Update Community Organizing topic configuration
3. Test database queries

### Phase 2: Audio Generator Update (2-3 hours)
1. Add `_generate_dialogue_audio()` method
2. Add `_parse_dialogue_script()` parser
3. Add model routing logic
4. Add error handling for v3 API
5. Test with sample dialogue

### Phase 3: Script Generator Update (2-3 hours)
1. Add `_generate_dialogue_script()` method
2. Create dialogue-specific system prompt
3. Add character count validation
4. Implement 2,800 character target
5. Test with real episode data

### Phase 4: Testing & Refinement (3-4 hours)
1. Generate test Community Organizing digest
2. Verify character count < 3,000
3. Test Text-to-Dialogue API call
4. Listen to generated audio
5. Refine prompts for better dialogue flow
6. Test edge cases (very short/long episodes)

**Total Implementation Time:** 8-12 hours

---

## Brittney vs Nayva for AI & Tech

**Issue:** Brittney and Nayva not found in your current voice library.

**Your Available Voices:**
- Professional Clones: Deepak Chopra, Richard Feynman, Burt Reynolds, Young Jamal, Dakota H, Natasha
- Premade Female (Young): Sarah, Laura, Jessica
- Premade Female (Middle-aged): Alice, Matilda, Lily
- Premade Neutral (Middle-aged): River

**Recommendations for "Hot Topics Social Media" style:**

1. **Sarah** (`EXAVITQu4vr4xnSDxMaL`) - Young, American, energetic
2. **Jessica** (`cgSgspJ2msm6clMCkdW9`) - Young, American, conversational
3. **Laura** (`FGY2WhTYpPnrIDTdsKH5`) - Young, American, modern

**Action Required:**
- If Brittney/Nayva are community voices you found, please provide voice IDs
- Or select from available voices above
- Or use Instant Voice Cloning to create custom voice

---

## Recommended Path Forward

### Immediate (Today):
1. **Listen to test audio:** `/tmp/test_dialogue_young_jamal_dakota.mp3`
2. **Decide on hybrid approach:** v3 for Community Organizing, Turbo for others
3. **Select AI & Tech voice:** Choose from Sarah, Jessica, Laura (or provide Brittney/Nayva IDs)

### This Week:
1. Implement database schema changes
2. Update AudioGenerator for dialogue support
3. Update ScriptGenerator for shorter, punchier Community Organizing scripts
4. Test end-to-end with real digest generation

### Next Steps:
1. Monitor v3 quality and stability
2. Refine dialogue prompts based on generated scripts
3. Consider extending to other topics if successful

---

## Key Takeaway

**You CAN have natural multi-speaker dialogue - but only by using v3 with shorter scripts.**

The hybrid approach gives you:
- ✅ Best of both worlds: long-form Turbo + dialogue v3
- ✅ Optimal use of your Pro plan credits
- ✅ Better user experience for dialogue-based content
- ✅ Production-ready stability for most content

**The 3,000 character limit is manageable** if you optimize Community Organizing for concise, conversational dialogue instead of comprehensive summaries.
