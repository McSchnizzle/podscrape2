# Plan: Enhance Story Arc Integration in Digest Generation (v2 - Post Codex Review)

## Problem Statement

Story arcs ARE being tracked (10 active arcs, 21 events from 12 sources for the top arc), and context IS being generated and passed to GPT prompts. However, the digests don't meaningfully reference these arcs because:

1. **Weak prompt instructions** - Current context just says "Consider including significant developments" which GPT treats as optional
2. **No structural framing requirements** - GPT doesn't frame coverage as "continuing stories"
3. **No arc prominence indicators** - Hot arcs (many events/sources) aren't prioritized

## Root Cause Analysis

The `_get_recent_story_arc_context()` method (lines 247-320 in `script_generator.py`) produces good context:
- Lists arc names, categories, event counts, source counts
- Includes 3 recent events per arc with perspectives

But the insertion point at lines 607/810 just drops it into the prompt without strong framing requirements.

## Proposed Solution (Updated with Codex Feedback)

### 1. Add `_classify_story_arcs()` helper method

New method to classify arcs by prominence with **consistent thresholds**:
- **Hot**: 5+ events OR 3+ sources - priority framing
- **Developing**: 2-4 events with 1-2 sources - standard tracking
- **Emerging**: Will NOT include 1-event arcs (keep min_events=2 to avoid noise)

### 2. Add `_match_arcs_to_episodes()` grounding method (NEW - Codex feedback)

**Critical for avoiding hallucinations**: Before including an arc in the prompt, verify it has supporting evidence in the provided episode transcripts.

```python
def _match_arcs_to_episodes(self, arcs: List[Dict], episodes: List[Episode]) -> List[Dict]:
    """
    Filter arcs to only those with supporting evidence in episode transcripts.
    Returns arcs enriched with matching episode titles.
    """
    # For each arc, check if key terms appear in any episode transcript
    # Only include arcs that have at least one supporting episode
    # Add 'supporting_episodes' field to each arc for prompt context
```

### 3. Enhance `_get_recent_story_arc_context()` method

Transform from passive to active, with **grounding guardrails**:

```
## STORY ARC INTEGRATION

This digest is part of an ongoing series tracking evolving narratives. The following story arcs have supporting evidence in today's episodes:

**HOT STORIES** (5+ events OR 3+ sources - PRIORITY):
### [Arc Name] (X events from Y sources)
Supported by: "[Episode Title 1]", "[Episode Title 2]"
Recent developments: [event summaries]

**DEVELOPING STORIES** (2+ events):
[Similar format]

**FRAMING INSTRUCTIONS:**
1. When covering content related to a story arc, reference it naturally
2. Use phrases like "In the ongoing [topic] story..." or "Building on recent coverage of..."
3. ONLY reference arcs that have supporting evidence in the transcripts above
4. If an arc has no new developments in today's content, do not force a mention
5. For previously covered arcs, focus on what's NEW - don't rehash background
```

### 4. Add token budget management (NEW - Codex feedback)

Adjust `_calculate_transcript_limit()` to account for arc context:

```python
def _calculate_transcript_limit(self, num_episodes: int, arc_context_length: int = 0) -> int:
    """Calculate transcript limit, reserving space for arc context."""
    # Reserve tokens for: system prompt (~2k), arc context, repetition instructions
    reserved_tokens = 3000 + (arc_context_length // 4)  # chars to tokens
    available_input_tokens = int(self.max_input_tokens * 0.8) - reserved_tokens
    # ... rest of calculation
```

Also cap arc context to max 4000 chars to prevent overflow.

### 5. Add TTS-safe arc name normalization (NEW - Codex feedback)

For narrative mode, provide spoken-friendly arc names:

```python
def _normalize_arc_name_for_tts(self, arc_name: str) -> str:
    """Convert arc name to TTS-safe spoken form."""
    # "GPT-4" -> "G P T four"
    # "AI" -> "A I"
    # Numbers stay as-is (TTS prompt already handles number expansion)
```

Include both raw and normalized names in context for narrative scripts.

### 6. Define precedence for repetition vs mandatory (NEW - Codex feedback)

Update `_build_repetition_avoidance_instructions()` with clear precedence:

```
If an arc was covered in the last 3 days:
- Frame as UPDATE only ("The latest on [arc]...")
- Focus exclusively on NEW developments
- If no new developments exist, skip the arc entirely
- Do NOT rehash previously covered information
```

### 7. Update prompt templates

In both `_generate_dialogue_script()` and `_generate_narrative_script()`:

Add after topic instructions:
```
## STORY ARC INTEGRATION

[Generated arc context with grounding info]

CRITICAL: Only reference story arcs that have supporting evidence in the episode
transcripts provided. Do not invent or assume developments not present in the content.
```

### 8. Verify arc marking post-generation

Confirm `mark_covered_story_arcs()` at line 1171 is working. The key-term extraction approach should work well since we're not introducing aliases in this iteration.

## Files to Modify

1. **`src/generation/script_generator.py`**
   - Add `_classify_story_arcs()` method
   - Add `_match_arcs_to_episodes()` method
   - Add `_normalize_arc_name_for_tts()` method
   - Enhance `_get_recent_story_arc_context()` (lines 247-320)
   - Update `_calculate_transcript_limit()` to accept arc_context_length
   - Update `_build_repetition_avoidance_instructions()` with precedence rules
   - Update dialogue system prompt (lines 573-620)
   - Update narrative system prompt (lines 807-857)

## Testing Strategy

1. Generate a test digest with the new prompts
2. Verify that:
   - Story arc references appear only when supported by transcript content
   - Framing language is natural ("In the ongoing...", "Building on...")
   - Hot arcs get appropriate treatment when evidence exists
   - Token limits are not exceeded
   - `story_arcs.included_in_digest_id` is populated after generation
   - TTS output handles arc names correctly (for narrative mode)

## Deployment Notes

- Changes affect Python scripts on et01 server
- Will need to sync changes to et01 after local testing
- No database migrations required
- Test with a real digest generation before deploying to production

## Expected Outcome

Before: "Today we're discussing Claude Code features and trust in AI..."

After: "In the ongoing Claude Code story we've been tracking—now covered by ten different sources—there's a significant new development... And the debate about user trust in AI monetization continues to evolve..."

## Design Decisions (Addressing Codex Questions)

1. **Arcs only when supported by transcripts** - Yes, we require grounding to avoid hallucinations
2. **Source counts** - Will use sparingly and naturally ("covered by multiple sources" rather than exact numbers)
3. **Framing style** - Natural integration, not forced ("In the ongoing..." rather than "STORY ARC UPDATE:")
4. **Arc vs episode balance** - Arcs provide framing context, episodes provide content. No dedicated "arc section"
