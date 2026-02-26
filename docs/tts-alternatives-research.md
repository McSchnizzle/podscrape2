# TTS Alternatives Research

Research and evaluation of Text-to-Speech alternatives to ElevenLabs for the podcast digest pipeline.

## Current Setup

**ElevenLabs Pro Plan ($99/month)**
- Base allocation: 500K characters
- Extension allocation: 1M characters
- Total monthly quota: 1.5M characters
- APIs in use:
  - Text-to-Dialogue API (eleven_v3) for multi-speaker dialogue mode
  - Text-to-Speech API for single-voice narrative mode
- Current usage: ~1.5M characters per month (hitting quota limits)
- Quota reset: Monthly on subscription renewal date

**Quota Management History**
- Testing double digests, regional variations, and script refinements have caused regular quota overages
- Recent pattern: Primary digest scripts use ~1.2M chars, test variations push beyond allocation
- Fallback strategy needed to prevent production failures when quota exceeded

## Implemented Fallback: OpenAI TTS

**Status: IMPLEMENTED** - Automatic fallback when ElevenLabs quota_exceeded error occurs

### API Details
- Models: `tts-1` (lower latency) and `tts-1-hd` (higher quality)
- Cost structure:
  - tts-1: $0.015 per 1K characters ($15/1M chars)
  - tts-1-hd: $0.030 per 1K characters ($30/1M chars)
- Max input per request: 4096 characters
- Available voices: alloy, echo, fable, onyx, nova, shimmer
- Audio format: MP3 (24kHz sample rate)

### Multi-Speaker Dialogue Implementation
- Approach: Per-turn audio generation with speaker voice assignment and ffmpeg concatenation
- Speaker voice mapping:
  - SPEAKER_1 → nova (warm, clear)
  - SPEAKER_2 → onyx (deep, resonant)
  - Mapping is configurable per topic via database settings
- Processing:
  1. Parse dialogue script by SPEAKER_X turns
  2. Generate audio for each turn with assigned voice
  3. Concatenate MP3 files using ffmpeg
  4. Add minimal crossfade (50ms) to smooth speaker transitions
- Limitations:
  - Emotion/audio tags from ElevenLabs format (e.g., [excited], [thoughtful]) are stripped before sending to OpenAI
  - No native multi-speaker API means slightly longer processing time per episode
  - Quality impact: Noticeable reduction in emotional expressiveness compared to ElevenLabs dialogue mode

### Quality Assessment
- Single-voice narrative: Good quality, professional sounding
- Multi-speaker dialogue: Acceptable quality but less natural than ElevenLabs, especially for:
  - Emotional expressiveness (no tag support)
  - Conversation flow and pacing
  - Speaker personality differentiation
- Use case recommendation: Suitable for fallback/overflow scenarios; maintain ElevenLabs as primary for best dialogue quality

### Implementation Files
- Fallback logic: `src/audio/audio_generator.py` (checks quota_exceeded and routes to OpenAI)
- Voice mapping: Topic configuration in database `topics` table
- Dialogue chunking: `src/audio/dialogue_chunker.py` (same chunking logic for both providers)
- ffmpeg concatenation: `src/audio/audio_processor.py`

## Evaluation Candidate: Fish Audio

**Website:** fish.audio

**Status: NEEDS EVALUATION** - Create sample episodes to compare with ElevenLabs and OpenAI

### Key Features
- Cost: Approximately $15 per 1M characters (aligned with OpenAI tts-1 pricing)
- Emotion/audio tags: Native support for emotion notation using `(angry)`, `(excited)`, `(sad)` syntax
  - Similar functionality to ElevenLabs tags like [excited], [thoughtful]
  - Potential to preserve some emotional expressiveness lost in OpenAI fallback
- Multi-speaker support: Voice cloning and multiple voice options available
- API: REST API with similar request/response structure to ElevenLabs
- Voice quality: Reports suggest natural, expressive voices comparable to ElevenLabs
- Response time: Reasonable latency for production use

### Potential Advantages Over OpenAI
- Native emotion tag support for dialogue quality improvement
- Lower cost than ElevenLabs while maintaining emotional expressiveness
- Could replace OpenAI fallback if quality proves superior
- May handle longer dialogue exchanges more naturally

### Integration Considerations
- API documentation review needed for request format and limits
- Voice ID mapping required in database (similar to ElevenLabs setup)
- Testing needed to validate emotion tag rendering in practice
- Account setup and quota management required

### Evaluation Tasks
- [ ] Sign up for Fish Audio account and obtain API credentials
- [ ] Generate sample episode using dialogue scripts with emotion tags
- [ ] Compare output quality to ElevenLabs primary and OpenAI fallback
- [ ] Measure processing time and API reliability
- [ ] Document voice options and selection process for integration
- [ ] Create cost comparison spreadsheet with actual usage data

## Evaluation Candidate: Deepgram Aura

**Website:** deepgram.com/aura

**Status: NEEDS EVALUATION** - Create sample episodes to compare with ElevenLabs and OpenAI

### Key Features
- Cost: Approximately $30 per 1M characters (aligned with OpenAI tts-1-hd pricing)
- Voice variety: 40+ voices available across different languages and accents
- Quality focus: Enterprise-grade TTS optimized for clarity and professional delivery
- Multi-speaker support: Multiple voice options available, voice cloning capabilities
- API: REST API with comprehensive documentation
- Response format: Multiple audio format options (MP3, WAV, etc.)

### Potential Advantages
- Enterprise-grade voice quality suitable for professional podcast contexts
- Extensive voice selection enables better speaker differentiation
- No native emotion tags, but voice variety may compensate for speaker personality
- Reliable API with strong uptime reputation
- Good for scenarios prioritizing clarity over emotional expressiveness

### Integration Considerations
- Higher cost than Fish Audio may not justify unless quality is significantly superior
- No native emotion tag support means manual voice selection for tone conveyance
- Multi-speaker dialogue requires per-turn voice assignment and concatenation (similar to OpenAI)
- Account setup and API key management required

### Evaluation Tasks
- [ ] Sign up for Deepgram Aura account and obtain API credentials
- [ ] Generate sample episode comparing voice variety options
- [ ] Test multi-speaker dialogue with different voice combinations
- [ ] Compare quality to ElevenLabs for professional podcast contexts
- [ ] Measure processing time and API performance under load
- [ ] Evaluate voice consistency across multiple episodes

## ElevenLabs Plan Upgrade Analysis

### Current Economics
- Pro plan: $99/month for 1.5M characters
- Current usage pattern: ~1.5M characters per month (hitting quota)
- Usage spikes: Testing variations, regional digests, double episodes push beyond allocation

### Upgrade Path: ElevenLabs Scale Plan
- Price: $330/month (exact quota varies, approximately 11M characters)
- Pricing model: Allocation + usage-based overflow at $0.24 per 1K characters
- At current steady-state usage (~1.5M/month): Scale plan over-provisioned by 7.5x
- Break-even analysis:
  - Overflow overflow cost at OpenAI rates: $15/1M characters
  - ElevenLabs Scale plan adds $231/month in cost
  - Monthly overflow would need to exceed ~15.4M characters to justify upgrade
  - Current max observed: ~1.8M characters (well below break-even)

### Recommendation: OpenAI Fallback Strategy
- Maintaining $99 ElevenLabs plan + OpenAI fallback is more cost-effective than Scale plan
- Fallback usage cost: ~$22.50/month for typical overflow scenarios (1.5M chars)
- Total monthly cost: ~$121.50 (vs $330 for Scale plan)
- Savings: ~$208/month vs Scale plan
- Trade-off: Fallback episodes use OpenAI quality instead of ElevenLabs, but primary production remains premium

### Long-Term Evaluation Trigger
- If regular monthly usage consistently exceeds 3M characters: Evaluate Scale plan
- If Fish Audio testing proves comparable quality: Consider switching primary to Fish Audio (saves $84/month vs ElevenLabs)
- If Deepgram Aura proves acceptable for production: Cost equivalent to OpenAI with more voice variety

## Testing Plan

### Phase 1: Sample Generation (Immediate)
1. Generate sample episode using current OpenAI TTS fallback implementation
   - Use existing dialogue script from recent digest
   - Compare output to equivalent ElevenLabs-generated episode
   - Document: voice quality, dialogue naturalness, emotional impact, processing time

### Phase 2: Fish Audio Evaluation (Weeks 1-2)
1. Sign up for Fish Audio account and obtain API credentials
2. Implement Fish Audio provider module (similar to existing OpenAI provider)
3. Generate sample episode with dialogue scripts containing emotion tags
4. Compare:
   - Dialogue quality and naturalness
   - Emotion tag rendering in practice
   - Processing time per episode
   - API reliability and error handling
   - Cost per 1M characters in actual usage
5. Document decision: Continue evaluation or proceed to integration

### Phase 3: Deepgram Aura Evaluation (Weeks 2-3)
1. Sign up for Deepgram Aura account and obtain API credentials
2. Implement Deepgram provider module
3. Generate sample episode testing voice variety for speaker differentiation
4. Compare:
   - Voice quality and professionalism
   - Multi-speaker dialogue voice pairing effectiveness
   - Processing time per episode
   - Voice consistency across multiple episodes
   - Cost per 1M characters in actual usage
5. Document decision: Integration recommendation or archival

### Phase 4: Comparative Analysis
1. Create side-by-side audio samples of same script from all providers
2. Evaluation criteria:
   - Naturalness of speech (narrative and dialogue)
   - Emotional expressiveness and impact
   - Voice personality and distinctiveness
   - Processing time and reliability
   - Cost per episode at scale
3. Recommendation decision:
   - Keep current OpenAI fallback as-is
   - Promote Fish Audio to primary or fallback (if quality sufficient)
   - Upgrade ElevenLabs plan (if cost analysis justifies)
   - Maintain multi-provider strategy with priority ordering

## Decision Matrix

| Provider | Cost/1M | Dialogue Quality | Emotion Support | Processing | Recommendation Status |
|----------|---------|------------------|-----------------|------------|----------------------|
| ElevenLabs (current) | $66 | Excellent | Native tags | Fast | Primary (at quota limits) |
| OpenAI tts-1 | $15 | Good | None (stripped) | Medium | Implemented fallback |
| OpenAI tts-1-hd | $30 | Very Good | None (stripped) | Slower | Fallback alternative |
| Fish Audio | ~$15 | TBD | Emotion syntax | TBD | Pending evaluation |
| Deepgram Aura | ~$30 | TBD | None | TBD | Pending evaluation |

## Next Steps

1. **Immediate:** Monitor OpenAI fallback performance in production
2. **Week 1:** Set up Fish Audio account and testing environment
3. **Week 2:** Generate and document Fish Audio sample comparisons
4. **Week 2:** Set up Deepgram Aura account and testing environment
5. **Week 3:** Generate and document Deepgram sample comparisons
6. **Week 3:** Compile decision analysis with quality/cost recommendations
7. **Week 4:** Implement chosen primary strategy (upgrade plan, provider switch, or multi-provider setup)

## References

- ElevenLabs Pricing: https://elevenlabs.io/pricing
- OpenAI TTS Pricing: https://openai.com/pricing/
- Fish Audio: https://fish.audio
- Deepgram Aura: https://deepgram.com/aura
