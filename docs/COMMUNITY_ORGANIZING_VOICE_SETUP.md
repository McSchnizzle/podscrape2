# Community Organizing Topic: Multi-Voice Configuration Guide

## Current Situation

**Topic:** Social Movements and Community Organizing
**Current Voice ID:** `Qxm2h3F1LF2mSoFwF8Vp` (same as AI and Technology - male voice)
**Issue:** Digest instructions call for "two-voice conversation" but currently uses single male voice
**Desired:** Two older Black women voices for dialogue-based digest

---

## Available Voice Options

### Your Current ElevenLabs Voices

**Premade Female Voices (6 total):**

| Name | Voice ID | Age | Accent | Notes |
|------|----------|-----|--------|-------|
| **Alice** | `Xb7hH8MSUJpSbSDYk0k2` | Middle-aged | British | Advertisement use case |
| **Matilda** | `XrExE9yKIg1WjnnlVkGX` | Middle-aged | American | Informative/educational |
| **Lily** | `pFZP5JQG7iQjIQuC4Bku` | Middle-aged | (unspecified) | Narration use case |
| Sarah | `EXAVITQu4vr4xnSDxMaL` | Young | American | - |
| Laura | `FGY2WhTYpPnrIDTdsKH5` | Young | American | - |
| Jessica | `cgSgspJ2msm6clMCkdW9` | Young | American | - |

**Your Custom Professional Voice Clones (3 total):**
- Deepak Chopra™ - Meditation Guru
- Richard Feynman™ - Raw Genius
- Burt Reynolds™ - Masculine Iconic Storyteller

**Note:** None of your current voices match the specific request for "two older Black women." The ElevenLabs API doesn't expose ethnicity/race metadata in voice labels.

---

## Recommended Solutions (Ranked)

### Option 1: Use ElevenLabs Voice Library Search (RECOMMENDED) ✅

**What:** Browse the full 10,000+ community voice library via web interface to find appropriate voices.

**How:**
1. Visit https://elevenlabs.io/voice-library
2. Filter by:
   - Gender: Female
   - Age: Mature / Elderly / Middle-aged
   - Accent: American (or other as appropriate)
   - Use Case: Narration, Conversational, Storytelling
3. Listen to voice previews
4. Look for voices with characteristics matching your vision:
   - Warm, grounded, wise tone
   - Mature/elderly age range
   - Conversational, storytelling quality
5. Copy voice IDs of 2 selected voices
6. Update database `topics` table with voice configuration

**Pros:**
- ✅ Access to 10,000+ community voices
- ✅ Can preview voices before selecting
- ✅ Free to use community voices
- ✅ Can filter by exact characteristics needed
- ✅ Immediate implementation once voices selected

**Cons:**
- ⚠️ Manual search process (no race/ethnicity filter)
- ⚠️ Voice quality varies (community-contributed)
- ⚠️ Popular voices may have usage restrictions

**Implementation Time:** 30-60 minutes (search + database update)

---

### Option 2: Create Custom Voices with Instant Voice Cloning ✅

**What:** Use your Pro plan's Instant Voice Cloning feature to create custom voices from audio samples.

**How:**
1. Source audio samples (15+ seconds each) of two older Black women speakers
   - Podcasts, interviews, audiobooks, YouTube content (with permission/fair use)
   - Clean audio with minimal background noise
   - Natural, conversational speech
2. Use ElevenLabs Instant Voice Cloning:
   - Upload audio samples
   - Generate voice ID
   - Test quality
3. Store voice IDs in database configuration

**Your Pro Plan Includes:**
- ✅ 160 custom voices (Instant Voice Cloning slots)
- ✅ Unlimited Instant Voice Cloning generations
- ✅ High-quality voice replication

**Pros:**
- ✅ **Perfect match** - Create exactly the voices you envision
- ✅ **High quality** - Pro plan provides best cloning quality
- ✅ **Unlimited usage** - No per-use fees for your cloned voices
- ✅ **Full control** - Voice characteristics, tone, style

**Cons:**
- ⚠️ Requires sourcing appropriate audio samples
- ⚠️ Copyright/permission considerations
- ⚠️ May need multiple attempts to get quality right
- ⚠️ 15+ seconds of clean audio needed per voice

**Implementation Time:** 2-4 hours (sourcing audio + cloning + testing)

**Ethical Note:** Ensure you have permission to clone voices or use fair use principles (transformative use, limited samples, educational/commentary purpose).

---

### Option 3: Commission Professional Voice Cloning (Enterprise)

**What:** Have ElevenLabs create professional voice clones from longer audio samples.

**How:**
1. Contact ElevenLabs for Professional Voice Clone quote
2. Provide 30+ minutes of high-quality audio per voice
3. ElevenLabs creates ultra-high-quality voice models
4. Receive voice IDs for integration

**Your Pro Plan:**
- Includes 1 Professional Voice Clone slot (currently unused for female voices)

**Pros:**
- ✅ Highest quality cloning
- ✅ Best for long-form content
- ✅ Reviewed and optimized by ElevenLabs team

**Cons:**
- ⚠️ Cost: Requires Professional Voice Clone quota
- ⚠️ Time: 2-4 weeks for voice creation
- ⚠️ Audio requirements: 30+ minutes of clean audio per voice

**Implementation Time:** 2-4 weeks + audio sourcing

---

### Option 4: Temporary Solution - Use Best Available Middle-Aged Voices

**What:** Use **Matilda** + **Lily** (or **Alice**) as interim solution while you find/create ideal voices.

**Voice Recommendations:**

**Speaker 1: Matilda**
- Voice ID: `XrExE9yKIg1WjnnlVkGX`
- Age: Middle-aged
- Accent: American
- Use Case: Informative/educational
- **Why:** American accent, informative tone, suitable for community organizing content

**Speaker 2: Lily**
- Voice ID: `pFZP5JQG7iQjIQuC4Bku`
- Age: Middle-aged
- Accent: (unspecified)
- Use Case: Narration
- **Why:** Different from Matilda, narration-focused, conversational

**Alternate: Alice**
- Voice ID: `Xb7hH8MSUJpSbSDYk0k2`
- Age: Middle-aged
- Accent: British
- **Why:** Distinct British accent provides contrast, advertisement/presentation quality

**Pros:**
- ✅ **Immediate implementation** - Voices already available
- ✅ **Free** - Premade voices at no extra cost
- ✅ **Middle-aged** - Mature, grounded tone
- ✅ **Professional quality** - ElevenLabs premade standards
- ✅ **Test multi-voice workflow** - Validate technical implementation

**Cons:**
- ⚠️ **Not the exact match** - Not specifically older Black women voices
- ⚠️ **Limited choice** - Only 3 middle-aged options
- ⚠️ **May not match vision** - Temporary compromise

**Implementation Time:** 15-30 minutes (database update only)

---

## Technical Implementation

### Database Configuration

**Current Configuration:**
```sql
SELECT name, voice_id, instructions_md
FROM topics
WHERE name = 'Social Movements and Community Organizing';
```

**Result:**
- Topic: Social Movements and Community Organizing
- Voice ID: `Qxm2h3F1LF2mSoFwF8Vp` (single voice, male, same as AI/Tech)
- Instructions: Begin with "Shape a living, **two-voice conversation**..."

### Multi-Voice Configuration Options

#### Option A: Store Multiple Voice IDs in Topic Table

**Add new columns to `topics` table:**
```sql
ALTER TABLE topics
ADD COLUMN voice_id_primary VARCHAR(255),
ADD COLUMN voice_id_secondary VARCHAR(255),
ADD COLUMN multi_voice_enabled BOOLEAN DEFAULT FALSE;
```

**Update Community Organizing:**
```sql
UPDATE topics
SET
    voice_id_primary = 'XrExE9yKIg1WjnnlVkGX',  -- Matilda
    voice_id_secondary = 'pFZP5JQG7iQjIQuC4Bku',  -- Lily
    multi_voice_enabled = TRUE
WHERE name = 'Social Movements and Community Organizing';
```

#### Option B: JSON Configuration in Existing Column

**Store multiple voices in `voice_id` as JSON:**
```sql
UPDATE topics
SET voice_id = '{"speaker_1": "XrExE9yKIg1WjnnlVkGX", "speaker_2": "pFZP5JQG7iQjIQuC4Bku", "multi_voice": true}'
WHERE name = 'Social Movements and Community Organizing';
```

**Parse in code:**
```python
import json
voice_config = json.loads(topic.voice_id)
if voice_config.get('multi_voice'):
    speaker_1_id = voice_config['speaker_1']
    speaker_2_id = voice_config['speaker_2']
```

---

## Script Format for Multi-Voice Dialogue

### Digest Instructions Update

**Add to instructions_md:**

```markdown
## Multi-Voice Format

Generate the script with clear speaker labels for two voices:
- **SPEAKER_1**: Community organizer perspective (experienced, strategic)
- **SPEAKER_2**: Activist/movement member perspective (grassroots, passionate)

Format:
```
SPEAKER_1: [First speaker's dialogue here]

SPEAKER_2: [Second speaker's dialogue here]

SPEAKER_1: [First speaker continues...]
```

- Use natural conversational flow
- Each speaker turn should be 2-4 sentences
- Create authentic back-and-forth dialogue
- Include transitions, reactions, agreements, questions
- Avoid robotic turn-taking - allow natural interruptions and follow-ups
```

### Example Digest Script (Two-Voice Format)

```
SPEAKER_1: This week brought some powerful wins in community organizing. The Minneapolis tenants' union secured rent stabilization protections that will impact over fifty thousand households.

SPEAKER_2: And what stood out to me was how they built that coalition. They didn't just go after policy—they spent two years building relationships block by block, building by building. That grassroots work is what made the difference.

SPEAKER_1: Exactly. That's the blueprint right there. Strong local organizing, clear demands, and they brought together tenants across race and class lines. That's how you build real power.

SPEAKER_2: I also want to highlight what's happening in Atlanta with the mutual aid networks. During the recent storms, community members organized distribution centers faster than FEMA could respond. It's proof that we don't need to wait for institutions to help each other.

SPEAKER_1: That's transformative work. When communities take care of their own, they're not just responding to crisis—they're building the foundations for long-term solidarity. These networks become the infrastructure for future organizing.

SPEAKER_2: Right. And that's what makes me hopeful about the movement. We're seeing people move from reacting to crises to actually building alternative systems. That's the cultural shift we need.
```

---

## Immediate Next Steps

### Step 1: Select Voices (Choose One Option)

**Option A: Quick Test (Recommended for immediate validation)**
- Use **Matilda** (`XrExE9yKIg1WjnnlVkGX`) and **Lily** (`pFZP5JQG7iQjIQuC4Bku`)
- Test multi-voice workflow
- Validate technical implementation
- Can replace later with custom voices

**Option B: Voice Library Search**
- Search ElevenLabs Voice Library (https://elevenlabs.io/voice-library)
- Filter: Female, Mature/Elderly, American, Conversational
- Preview and select 2 voices
- Copy voice IDs

**Option C: Create Custom Voices**
- Source audio samples (15+ seconds each, clean audio)
- Use Instant Voice Cloning
- Test and refine
- Store voice IDs

### Step 2: Update Database Configuration

Run SQL migration or direct update:
```sql
-- Option 1: Add new columns
ALTER TABLE topics
ADD COLUMN voice_id_primary VARCHAR(255),
ADD COLUMN voice_id_secondary VARCHAR(255),
ADD COLUMN multi_voice_enabled BOOLEAN DEFAULT FALSE;

UPDATE topics
SET
    voice_id_primary = 'XrExE9yKIg1WjnnlVkGX',  -- Replace with selected voice
    voice_id_secondary = 'pFZP5JQG7iQjIQuC4Bku',  -- Replace with selected voice
    multi_voice_enabled = TRUE
WHERE name = 'Social Movements and Community Organizing';

-- Option 2: Use JSON in existing voice_id column
UPDATE topics
SET voice_id = '{"speaker_1": "XrExE9yKIg1WjnnlVkGX", "speaker_2": "pFZP5JQG7iQjIQuC4Bku", "multi_voice": true}'
WHERE name = 'Social Movements and Community Organizing';
```

### Step 3: Update Script Generator

Modify `src/generation/script_generator.py` to:
1. Detect multi-voice topics
2. Generate scripts with speaker labels (`SPEAKER_1:`, `SPEAKER_2:`)
3. Pass speaker format requirements to GPT prompt

### Step 4: Implement Multi-Voice TTS Pipeline

Modify `src/audio/audio_generator.py` to:
1. Parse script for speaker labels
2. Split text by speaker
3. Call ElevenLabs API for each speaker segment with appropriate voice_id
4. Concatenate audio files using `pydub` or `ffmpeg`
5. Save final merged audio file

**Reference:** See `docs/TTS_PROVIDER_COMPARISON.md` Section: "Multi-Speaker Support Deep Dive"

### Step 5: Test End-to-End

1. Run digest generation for Community Organizing topic
2. Verify script has speaker labels
3. Run TTS generation
4. Verify audio has distinct voices
5. Listen for natural transitions and quality

---

## Resources

- **ElevenLabs Voice Library:** https://elevenlabs.io/voice-library
- **ElevenLabs Voice Cloning Guide:** https://elevenlabs.io/docs/product-guides/voices/voice-cloning
- **API Voice Listing:** `curl -X GET https://api.elevenlabs.io/v1/voices -H "xi-api-key: YOUR_API_KEY"`
- **Pro Plan Voice Limits:** 160 custom voices (Instant Voice Cloning)

---

## Current Status

**Voice Configuration:**
- ⚠️ **Issue Identified:** Single male voice used for two-voice conversation topic
- ✅ **Research Complete:** ElevenLabs voice options documented
- ⚠️ **Database Update Needed:** Configure multi-voice setup
- ⚠️ **Code Changes Needed:** Implement multi-voice TTS pipeline

**Recommended Immediate Action:**
1. Use **Matilda + Lily** as temporary voices to test workflow (15-30 min)
2. Simultaneously search Voice Library for ideal voices (1-2 hours)
3. Replace with custom cloned voices if needed (future enhancement)

This approach gets you a working multi-voice system immediately while allowing time to find or create the perfect voices for your vision.
