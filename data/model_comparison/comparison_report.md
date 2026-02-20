# Model Comparison Report (5 Models)

**Date**: 2026-02-20
**Task**: Dialogue-style podcast digest generation for AI and Technology topic
**Episodes used**: 4 most recent scored/digested episodes

## Prompt Details

- System prompt length: ~23,000 characters
- User prompt length: ~114,000-185,000 characters (varies by run due to story arc context growth)
- Total prompt length: ~137,000-208,000 characters

**Note**: Sonnet 4.6 was run later in the day after additional story arcs were extracted, resulting in higher input token counts. The core episode transcripts were the same across all runs.

## Comparison Table

| Metric | GPT-5.2 (chat) | GPT-5.2 (thinking) | Claude Haiku 4.5 | Claude Sonnet 4.6 | Claude Opus 4.5 |
|--------|--------|--------|--------|--------|--------|
| Output chars | 23,330 | 21,357 | 27,325 | 32,707 | 19,190 |
| Input tokens | 28,894 | 28,894 | 31,391 | 47,402 | 31,391 |
| Output tokens | 5,303 | 6,155 | 5,874 | 7,000 | 4,351 |
| Reasoning tokens | 0 | 1,360 | 0 | 0 | 0 |
| Generation time (s) | 103.1 | 121.5 | 72.9 | 188.1 | 118.4 |
| Estimated cost | $0.1002 | $0.1070 | $0.0486 | $0.2472 | $0.7972 |
| Pricing | $2/M in, $8/M out | $2/M in, $8/M out | $0.80/M in, $4/M out | $3/M in, $15/M out | $15/M in, $75/M out |

## Cost Analysis

1. **Claude Haiku 4.5**: $0.0486 (cheapest)
2. **GPT-5.2 (chat)**: $0.1002
3. **GPT-5.2 (thinking)**: $0.1070
4. **Claude Sonnet 4.6**: $0.2472
5. **Claude Opus 4.5**: $0.7972

**Cost multiples relative to cheapest (Claude Haiku 4.5):**

- Claude Haiku 4.5: 1.0x
- GPT-5.2 (chat): 2.1x
- GPT-5.2 (thinking): 2.2x
- Claude Sonnet 4.6: 5.1x
- Claude Opus 4.5: 16.4x

## Speed Analysis

1. **Claude Haiku 4.5**: 72.9s (375 chars/sec)
2. **GPT-5.2 (chat)**: 103.1s (226 chars/sec)
3. **Claude Opus 4.5**: 118.4s (162 chars/sec)
4. **GPT-5.2 (thinking)**: 121.5s (176 chars/sec)
5. **Claude Sonnet 4.6**: 188.1s (174 chars/sec)

## Output Length Analysis

Target range: 15,000-20,000 characters

- **Claude Opus 4.5**: 19,190 chars (IN RANGE)
- **GPT-5.2 (thinking)**: 21,357 chars (slightly over)
- **GPT-5.2 (chat)**: 23,330 chars (over by 17%)
- **Claude Haiku 4.5**: 27,325 chars (over by 37%)
- **Claude Sonnet 4.6**: 32,707 chars (over by 64%)

## Quality Assessment Summary

### Claude Opus 4.5 - Best Overall Quality
- Only model to hit the target length range (19,190 chars)
- Most nuanced analysis with sophisticated connections between stories
- Natural conversational flow, excellent use of audio tags
- Best at grounding claims in transcript evidence
- Most expensive ($0.80/digest) but justified for production use

### GPT-5.2 (thinking) - Strong Runner-Up
- Good analytical depth from reasoning capabilities
- Slightly over target length but well-structured
- Good at maintaining dialogue format
- Cost-effective at $0.107/digest

### GPT-5.2 (chat) - Solid Mid-Tier
- Good quality at a reasonable price
- Slightly over target length
- Fast generation
- Good format compliance

### Claude Sonnet 4.6 - Verbose but High Quality
- Excellent content quality and analysis depth
- Significantly over target length (32,707 chars - 64% over)
- Very detailed coverage of each story
- Good conversational flow and audio tag usage
- 5x the cost of Haiku but significantly better quality
- Would need prompt tuning to reduce length for production use

### Claude Haiku 4.5 - Best Value
- Fastest generation by far (72.9s)
- Cheapest ($0.049/digest)
- Quality is acceptable but less nuanced
- Over target length (27,325 chars)
- Best choice for cost-sensitive or high-volume scenarios

## Recommendation

**For production daily digests**: Claude Opus 4.5 remains the top choice for quality - it's the only model that respects the target length and produces the most polished output. At ~$0.80/digest, it's expensive but manageable for a daily pipeline.

**Best value alternative**: Claude Sonnet 4.6 at $0.25/digest offers near-Opus quality at 1/3 the price, but needs prompt engineering to control output length. If the verbosity can be tamed, it could be the sweet spot.

**Budget option**: Claude Haiku 4.5 at $0.05/digest is 16x cheaper than Opus with acceptable quality. Good for testing, development, or scenarios where cost matters more than polish.
