# Script formats: dialogue and narrative

Moved out of `CLAUDE.md` (2026-07-31) so the guidance file stays about how to
work here, not about reference detail. Nothing below changed in the move.

Mode is set per topic by the `script_mode` column in the `topics` table.

## Dialogue mode

Conversational digests, two voices.

- **Format**: `SPEAKER_1:` / `SPEAKER_2:` turns with inline audio tags
- **Length**: 15,000-20,000 characters
- **TTS**: ElevenLabs Text-to-Dialogue API (v3)
- **Chunking**: split automatically into ~3,000-character chunks at speaker
  boundaries
- **Voices**: requires both `voice_1_id` and `voice_2_id`

```
SPEAKER_1: [excited] Hey everyone, welcome back! Today we're diving into some
incredible stories from the world of community organizing.

SPEAKER_2: [thoughtful] That's right. We've been following some amazing
movements, and the energy behind these grassroots efforts is inspiring.

SPEAKER_1: [serious] Let's start with the transit justice campaign in Los Angeles...
```

## Narrative mode

Single-voice digests.

- **Format**: prose optimised for TTS
- **Length**: 10,000-15,000 characters
- **TTS**: ElevenLabs standard Text-to-Speech
- **Normalisation**: numbers spelled out, abbreviations expanded
- **Voices**: `voice_1_id` only

```
Welcome to today's digest on artificial intelligence and technology. We're
exploring developments in AI safety, machine learning, and the future of
autonomous systems.

Recent research from Stanford reveals insights into large language model
capabilities. Scientists have found that these models can exhibit emergent
properties...
```

## Audio tag vocabulary

Supported ElevenLabs tags in dialogue mode:

| Group | Tags |
|---|---|
| Emotion | `[excited]` `[thoughtful]` `[serious]` `[concerned]` `[hopeful]` |
| Action | `[laughs]` `[sighs]` `[chuckles]` |
| Pacing | `[pause]` `[quickly]` `[slowly]` |

Budget, enforced by the generation prompt: **max 25 tags per script, and no more
than 35% of turns tagged.** Over-tagging is one of the loudest AI tells in the
finished audio.

## Topic configuration fields

```typescript
// topics table
script_mode:     'dialogue' | 'narrative'
voice_1_id:      string        // ElevenLabs voice for voice 1 / narrator
voice_2_id:      string | null // dialogue only
dialogue_model:  string        // generation model
instructions_md: string        // topic-specific instructions
```

Edit via the Web UI Topics page, or the `topics` table directly.

## Implementation

| Concern | File |
|---|---|
| Script generation | `src/generation/script_generator.py` |
| Anti-AI rules (canonical) | `.claude/commands/generate-digest.md` |
| Dedup pass | `src/generation/dedup_pass.py` |
| Audio generation | `src/audio/audio_generator.py` |
| Dialogue chunking | `src/audio/dialogue_chunker.py` |
| Web UI config | `web_ui_hosted/app/topics/page.tsx` |
| Script preview | `web_ui_hosted/app/api/script-lab/preview/route.ts` |

**The banned-phrase list is duplicated** across `.claude/commands/generate-digest.md`,
two prompts inside `script_generator.py`, and `dedup_pass.py`, and the copies have
already drifted apart. Adding a rule to only one of them enforces it in only one
pass.
