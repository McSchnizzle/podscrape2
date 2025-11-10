# ElevenLabs TTS-Friendly Script Writing Guidelines

## Purpose
This document provides comprehensive guidelines for creating digest scripts optimized for ElevenLabs Text-to-Speech (TTS) conversion. These guidelines should be incorporated into the AI digest generation prompts to ensure generated scripts produce natural, expressive, and error-free audio output.

**Current System TTS Model**: `eleven_turbo_v2_5` (configurable via web_settings)

---

## Table of Contents
1. [Text Normalization & Formatting](#text-normalization--formatting)
2. [Emotion & Expression Control](#emotion--expression-control)
3. [Multi-Voice Support](#multi-voice-support)
4. [Pauses & Pacing](#pauses--pacing)
5. [Model-Specific Features](#model-specific-features)
6. [Script Structure Best Practices](#script-structure-best-practices)

---

## Text Normalization & Formatting

### Numbers & Monetary Values
**Rule**: Always write numbers in full spoken form, never as digits.

**Examples**:
- ❌ `$100` → ✅ `one hundred dollars` or `a hundred dollars`
- ❌ `3.5 million` → ✅ `three point five million`
- ❌ `2024` → ✅ `twenty twenty-four` (year) or `two thousand twenty-four`
- ❌ `14:30` → ✅ `two thirty PM` or `fourteen thirty`
- ❌ `1/2` → ✅ `one-half` or `half`

**Phone Numbers**: Spell out individually
- ❌ `123-456-7890` → ✅ `one two three, four five six, seven eight nine zero`

**Large Numbers**: Use natural language
- ❌ `1,234,567` → ✅ `one million, two hundred thirty-four thousand, five hundred sixty-seven`

### Dates & Times
**Rule**: Expand dates fully and consider locale context.

**Examples**:
- ❌ `01/02/2024` → ✅ `January second, twenty twenty-four` (US format)
- ❌ `2024-12-25` → ✅ `December twenty-fifth, twenty twenty-four`
- ❌ `Q3 2024` → ✅ `third quarter of twenty twenty-four`

### Abbreviations & Acronyms
**Rule**: Expand ALL abbreviations to their full spoken forms.

**Common Expansions**:
- ❌ `Dr.` → ✅ `Doctor`
- ❌ `Ave.` → ✅ `Avenue`
- ❌ `St.` → ✅ `Street` (unless proper noun like "St. Patrick")
- ❌ `etc.` → ✅ `etcetera` or rephrase to avoid
- ❌ `e.g.` → ✅ `for example`
- ❌ `i.e.` → ✅ `that is`
- ❌ `USA` → ✅ `United States` or `U.S.A.` (spelled out)
- ❌ `CEO` → ✅ `C.E.O.` or `Chief Executive Officer`

**Month Names**: Always spell out fully
- ❌ `Jan`, `Feb`, `Mar` → ✅ `January`, `February`, `March`

**Units of Measurement**:
- ❌ `100km` → ✅ `one hundred kilometers`
- ❌ `5lb` → ✅ `five pounds`
- ❌ `25%` → ✅ `twenty-five percent`

### Symbols & Special Characters
**Rule**: Convert all symbols to spoken equivalents.

**Examples**:
- ❌ `&` → ✅ `and`
- ❌ `@` → ✅ `at`
- ❌ `#` → ✅ `number` or `hashtag` (context-dependent)
- ❌ `Ctrl + Z` → ✅ `control Z`
- ❌ `100%` → ✅ `one hundred percent`
- ❌ `$` → ✅ `dollars` (with number spelled out)

### URLs & Email Addresses
**Rule**: Either spell out phonetically or describe contextually.

**Examples**:
- ❌ `elevenlabs.io/docs` → ✅ `eleven labs dot io slash docs`
- ❌ `info@example.com` → ✅ Rephrase: `email us at info at example dot com`

---

## Emotion & Expression Control

### Model Compatibility

#### Turbo v2.5 / Turbo v2 / Flash v2.5 / Flash v2 (Current System)
These models use **narrative-style prompting** and **SSML tags** for emotional control.

**Narrative-Style Emotion Injection**:
- Write emotions and delivery cues as if writing a screenplay or novel
- Use dialogue tags and descriptive context
- Note: The model will speak the tags aloud, so they must sound natural

**Examples**:
```
"She said excitedly, this is the most important discovery of the decade."
"He paused, taking a deep breath before continuing."
"The researcher explained thoughtfully, we need to consider multiple perspectives."
```

**Punctuation for Emotion**:
- Use exclamation marks for excitement: `This is incredible!`
- Use question marks for curiosity: `What does this mean?`
- Use ellipses for trailing off or pauses: `Well... that's interesting.`
- Use capitalization sparingly for emphasis: `This is CRITICAL information.`

#### Eleven v3 (Future Upgrade Path)
If the system upgrades to Eleven v3, audio tags become available:

**Audio Tag Examples**:
```
[excitedly] This is the most important discovery!
[whispers] The data reveals something unexpected.
[sighs] Unfortunately, the results were inconclusive.
[laughs] That's quite an unusual finding.
[curious] What could explain this phenomenon?
[serious tone] We need to address this immediately.
```

**Tag Categories**:
- **Emotional**: `[sad]`, `[angry]`, `[happily]`, `[excited]`, `[nervous]`, `[calm]`
- **Delivery**: `[whispers]`, `[sighs]`, `[exhales]`, `[sarcastic]`, `[mischievously]`
- **Intensity**: `[laughs]`, `[laughs harder]`, `[starts laughing]`
- **Tone**: `[serious tone]`, `[conversational tone]`, `[matter-of-fact]`, `[reflective]`

---

## Multi-Voice Support

### Current System (Single Voice Per Topic)
The system currently assigns one voice per topic based on `config/topics.json` voice mappings. Scripts should be written for single-voice narration.

### Multi-Character Dialogue (Future Enhancement)

If multi-voice support is implemented, follow these guidelines:

**Script Format**:
```
SPEAKER_1: This is the first character speaking.
SPEAKER_2: And this is the second character responding.
NARRATOR: Meanwhile, the data shows an interesting trend.
```

**Best Practices**:
- Assign distinct, complementary voices for each speaker
- Use clear speaker labels (SPEAKER_1, SPEAKER_2, NARRATOR, etc.)
- Ensure natural conversational flow with appropriate turn-taking
- Add emotional context for each speaker's lines

**Interruptions & Overlaps** (v3 with audio tags):
```
SPEAKER_1: I think we should consider—
SPEAKER_2: [interrupting] Wait, look at this data point!
SPEAKER_1: [sighs] As I was saying...
```

**Community Organizing Use Case**:
For topics like "Community Organizing" that could benefit from multiple perspectives:
```
ORGANIZER: Today's episode discusses building coalition power.
COMMUNITY_MEMBER: The approach they used in Seattle is particularly effective.
NARRATOR: Let's examine three key strategies from this week's episodes.
```

---

## Pauses & Pacing

### SSML Break Tags (Turbo v2.5 / Flash v2.5)
**Rule**: Use `<break time="x.xs" />` for precise pauses up to 3 seconds.

**Usage**:
```
This is a major breakthrough. <break time="1.5s" /> Let me explain why.
The study found three key results. <break time="0.8s" /> First, the data shows...
```

**Warning**: Excessive break tags can cause instability (speed changes, audio artifacts). Use sparingly.

**Alternative Pause Methods**:
- Ellipses: `The results were... unexpected.` (natural pause)
- Em dashes: `The conclusion—and this is critical—changes everything.` (brief pause)
- Period with spacing: `Important finding. [pause] Now let's discuss implications.`

### Current System Implementation
The AudioGenerator already adds pauses automatically:
```python
text = text.replace('. ', '. ... ')  # Pause after sentences
text = text.replace('! ', '! ... ')  # Pause after exclamations
text = text.replace('? ', '? ... ')  # Pause after questions
```

**Recommendation**: Write natural sentence structures. The system will add appropriate pauses automatically. Only use explicit `<break>` tags for dramatic effect or critical timing.

### Speed Control
The system can adjust voice speed via API settings (0.7 to 1.2, default 1.0). Scripts should be written for normal pacing unless specific speed adjustments are needed.

---

## Model-Specific Features

### Turbo v2.5 (Current Default) ✅ RECOMMENDED
**Characteristics**:
- Max characters: 40,000 (~40 min of audio)
- Low latency: 250-300ms
- SSML break tags supported
- SSML phoneme tags supported (CMU Arpabet, IPA)
- Production-stable and reliable
- Cost: 50% lower than v2 models
- Best for: High-volume, long-form content generation

**Why This is Your Best Choice**:
✅ **40,000 character limit** - fits ALL your digest scripts (2k-35k chars) in one API call
✅ **50% cost savings** vs highest quality models (critical for Pro plan optimization)
✅ **Production-stable** - no alpha issues or inconsistencies
✅ **Low latency** - fast pipeline execution
✅ **No script splitting** - maintains consistent prosody and voice quality

**Optimizations**:
- Text normalization adds latency but ensures proper pronunciation
- System default: 35,000 character limit (configurable via web_settings)
- Latency mode 4: Max speed, no normalization (may mispronounce numbers/dates)

### Eleven v3 ⚠️ NOT RECOMMENDED for Your Use Case
**Characteristics**:
- Max characters: **3,000** (~3 min of audio) ⚠️ **MAJOR LIMITATION**
- Latency: Variable (higher than Turbo)
- Status: Alpha (subject to change)
- Audio tags: ✅ [excited], [whispers], [sighs], etc.
- Multi-speaker: ✅ Single API call for dialogue
- Emotional range: Highest available
- Cost: Standard pricing (2x Turbo v2.5)
- Best for: Short-form, highly expressive content with multiple characters

**Why v3 is NOT Suitable for Digest Scripts**:
❌ **3,000 character limit** - would require 10+ API calls per digest (2k-35k chars)
❌ **13x smaller limit** than Turbo v2.5 (3k vs 40k)
❌ **Inconsistent prosody** across split chunks
❌ **10-12x higher cost** (multiple API calls + 2x pricing)
❌ **Much higher latency** (alpha model + multiple calls)
❌ **Complex pipeline logic** needed to split/merge audio
❌ **Alpha status** - not production-ready

**Only Consider v3 If:**
- You need audio tags for fine-grained emotion control (`[whispers]`, `[excited]`, etc.)
- You need multi-speaker dialogue in single API call
- Your scripts are consistently under 2,500 characters
- You're willing to accept alpha instability and higher costs

**Current System Decision**:
🎯 **Stick with Turbo v2.5** - The 3,000 character limit makes v3 a deal-breaker for digest scripts averaging 10k-20k characters. The only advantage (audio tags) doesn't justify the massive increase in complexity and cost.

### Flash v2.5
**Characteristics**:
- Max characters: 40,000
- Ultra-low latency
- SSML support
- Best for: Real-time or high-frequency generation

### Flash v2 / Turbo v2
**Characteristics**:
- Max characters: 30,000
- SSML phoneme tags supported
- Slightly older models, still production-ready

### Multilingual v2 / v1
**Characteristics**:
- Max characters: 10,000
- No phoneme tag support
- Use alias tags instead
- Best for: Non-English content

---

## Script Structure Best Practices

### Character Length Guidelines
**Minimum**: 250 characters for consistency
- Very short prompts risk inconsistent output
- Aim for substantive content

**Maximum**: Respect model limits
- Turbo v2.5 / Flash v2.5: 40,000 characters
- System default: 35,000 characters (allows buffer)
- Current AudioGenerator enforces limit and truncates at sentence boundaries

### Sentence Structure
**Rule**: Write clear, natural speech patterns.

**Good Practices**:
- Use conversational language, not formal academic prose
- Vary sentence length for natural rhythm
- Avoid complex nested clauses
- Use active voice when possible

**Examples**:
- ❌ `The study, which was conducted by researchers at the university, found that...`
- ✅ `Researchers at the university conducted a study. They found that...`

### Paragraph Breaks
Use paragraph breaks to create natural pauses and segment topics:
```
This week, three episodes explored climate policy.

The first episode discussed carbon pricing. The host interviewed an economist
who explained how cap-and-trade systems work.

The second episode shifted to renewable energy. We heard about recent advances
in solar technology.
```

### Avoiding TTS Artifacts

**Don't Include**:
- Stage directions meant for readers: `[Host pauses for dramatic effect]`
- Meta-commentary: `(This section needs expansion)`
- Formatting instructions: `Read this part slowly`
- Visual references: `As shown in the chart above`

**Do Include** (if using narrative style):
- Natural speech indicators: `She paused, considering the question carefully.`
- Emotional context: `He said enthusiastically...`
- Logical transitions: `Meanwhile...`, `However...`, `To summarize...`

### Content Organization
**Opening**: Strong, clear introduction
```
Welcome to today's digest. We're covering three episodes about artificial intelligence,
with a focus on recent breakthroughs in language models.
```

**Body**: Clear transitions between topics
```
First, let's discuss the Stanford research.
<break time="0.5s" />
Next, we'll examine the ethical implications.
<break time="0.5s" />
Finally, we'll look at practical applications.
```

**Closing**: Concise summary and sign-off
```
That's today's digest covering advances in A.I. research. For more information,
visit the show notes. Thanks for listening.
```

---

## Implementation Recommendations

### Phase 1: Immediate Improvements (No Code Changes)
Modify the digest generation prompts to include these guidelines:

1. **Text Normalization Section**: Instruct GPT to write all numbers, dates, and abbreviations in full spoken form
2. **Narrative Emotion Style**: Encourage use of dialogue tags and emotional context
3. **Script Structure**: Emphasize natural speech patterns and appropriate length
4. **Abbreviation Avoidance**: Explicitly list common abbreviations to avoid

### Phase 2: Enhanced Instructions (Database Update)
Update the `instructions_md` field for each topic in the `topics` table to include:

```markdown
## TTS Optimization Instructions

When creating digest scripts:

1. Write ALL numbers in full spoken form (e.g., "twenty twenty-four" not "2024")
2. Expand ALL abbreviations (e.g., "January" not "Jan", "Doctor" not "Dr.")
3. Convert symbols to words (e.g., "and" not "&", "dollars" not "$")
4. Use narrative style for emotion: "she said excitedly" instead of emotion markers
5. Maintain 2,000-35,000 character length for optimal TTS performance
6. Write in conversational, natural speech patterns
7. Use clear paragraph breaks for topic transitions
```

### Phase 3: Multi-Voice Support (Future Enhancement)
If multi-voice conversations are desired:

1. **Database Schema**: Add support for multiple voice_id assignments per topic
2. **Script Format**: Implement speaker label parsing (SPEAKER_1:, SPEAKER_2:, etc.)
3. **API Integration**: Use ElevenLabs Text-to-Dialogue API or multi-voice concatenation
4. **Topic Configuration**: Allow topics to specify dialogue mode and voice assignments

Example topic configuration:
```json
{
  "name": "Community Organizing",
  "voice_mode": "multi",
  "voices": [
    {"role": "ORGANIZER", "voice_id": "voice_id_1"},
    {"role": "NARRATOR", "voice_id": "voice_id_2"}
  ]
}
```

### Phase 4: Model Upgrade Considerations
If upgrading to Eleven v3:

1. **Audio Tags**: Add support for `[emotion]` and `[delivery]` tags in scripts
2. **Prompt Updates**: Teach GPT to use v3 audio tag syntax
3. **Web Settings**: Add model selection UI with feature compatibility warnings
4. **Tag Validation**: Implement tag syntax checking before TTS generation

---

## Testing & Validation

### Pre-TTS Validation Checklist
Before sending scripts to TTS:

- [ ] No digit-only numbers (except voice passwords/codes)
- [ ] No abbreviated month names (Jan → January)
- [ ] No abbreviated titles (Dr. → Doctor)
- [ ] No symbol characters ($, &, %, @)
- [ ] No URLs in raw format (convert to speech)
- [ ] Character count within model limits
- [ ] Natural sentence structure (conversational tone)
- [ ] Appropriate paragraph breaks for pacing

### Quality Assurance
After TTS generation:

- [ ] Listen to first 30 seconds for pronunciation issues
- [ ] Check pacing and pause naturalness
- [ ] Verify emotional tone matches content
- [ ] Ensure no unexpected artifacts or speed changes
- [ ] Validate audio file size and duration are reasonable

---

## Resources & References

### ElevenLabs Documentation
- [Prompting Eleven v3](https://elevenlabs.io/docs/best-practices/prompting/eleven-v3)
- [Text Normalization](https://elevenlabs.io/docs/best-practices/prompting/normalization)
- [Speech Controls](https://elevenlabs.io/docs/best-practices/prompting/controls)
- [Text to Dialogue API](https://elevenlabs.io/docs/capabilities/text-to-dialogue)

### Model Specifications
See `src/config/web_config.py` for current model limits:
- `AI_MODELS['elevenlabs']` - Character limits and display names
- Web UI Settings page - Configure model and character limits

### Current System Files
- **TTS Generation**: `src/audio/audio_generator.py`
- **Web Configuration**: `src/config/web_config.py`
- **Voice Management**: `src/audio/voice_manager.py`
- **Digest Generation**: `src/generation/script_generator.py`

---

## Revision History
- **2024-01-10**: Initial version based on ElevenLabs best practices research
- **Current System**: eleven_turbo_v2_5 with 35,000 character limit
