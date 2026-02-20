#!/usr/bin/env python3
"""
Model comparison script for podcast digest generation.
Sends the EXACT same prompt to 4 models and compares outputs + costs.
"""

import os
import sys
import json
import time
from datetime import date, datetime, timezone
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load .env
from dotenv import load_dotenv
load_dotenv(project_root / '.env')

from src.database.models import get_database_manager
from src.database.sqlalchemy_models import Episode, Topic
from src.database.story_arc_repo import get_story_arc_repo
from src.topic_tracking.ad_filter import AdFilter
from sqlalchemy import or_, desc

OUTPUT_DIR = Path(__file__).parent


def get_episodes_and_topic():
    """Extract real inputs from the database."""
    db_manager = get_database_manager()
    session = db_manager.get_session()

    # Get topic
    topic = session.query(Topic).filter(Topic.name == 'AI and Technology').first()
    if not topic:
        raise RuntimeError("Topic 'AI and Technology' not found")

    instructions_md = topic.instructions_md
    voice_config = topic.voice_config

    # Get episodes with AI and Technology scores >= 0.65, status scored or digested
    episodes = session.query(Episode).filter(
        or_(Episode.status == 'scored', Episode.status == 'digested')
    ).order_by(desc(Episode.published_date)).limit(50).all()

    ai_episodes = []
    for ep in episodes:
        if ep.scores and 'AI and Technology' in ep.scores:
            score = ep.scores['AI and Technology']
            if score >= 0.65:
                ai_episodes.append((ep, score))

    # Sort by published_date descending, take top 4
    ai_episodes.sort(key=lambda x: x[0].published_date, reverse=True)
    top_4 = ai_episodes[:4]

    # Extract data while session is open
    episode_data = []
    ad_filter = AdFilter()
    for ep, score in top_4:
        transcript = ep.transcript_content or ''
        # Apply ad filtering
        if ad_filter:
            transcript, _ = ad_filter.filter_transcript(transcript)
        episode_data.append({
            'title': ep.title,
            'published_date': ep.published_date.strftime('%Y-%m-%d'),
            'transcript': transcript,
            'score': score,
        })

    session.close()

    # Get story arc context
    repo = get_story_arc_repo()
    arc_context = repo.get_story_arcs_for_prompt('AI and Technology')

    return episode_data, instructions_md, voice_config, arc_context


def build_prompts(episode_data, instructions_md, voice_config, arc_context):
    """Build the exact system and user prompts matching _generate_dialogue_script()."""
    topic = "AI and Technology"
    digest_date = date.today()

    # Extract speaker names from voice_config
    speaker_1_name = "Host"
    speaker_2_name = "Analyst"
    if voice_config:
        speaker_1 = voice_config.get('speaker_1', {})
        speaker_2 = voice_config.get('speaker_2', {})
        speaker_1_name = speaker_1.get('name', speaker_1.get('role', 'Host'))
        speaker_2_name = speaker_2.get('name', speaker_2.get('role', 'Analyst'))

    # Build story arc context using the same method as script_generator
    # We use the raw arc_context from get_story_arcs_for_prompt and embed it
    story_arc_section = ""
    if arc_context:
        story_arc_section = f"\n\nSTORY ARC CONTEXT:\n{arc_context}\n"

    # Calculate transcript limit (matching _calculate_transcript_limit logic)
    # With max_input_tokens=150000, 80% = 120000, minus 3000 reserved = 117000 tokens
    # 117000 * 4 chars = 468000 chars total, / 4 episodes = 117000 per episode
    # But capped at transcript_max_chars = 200000
    transcript_limit = 117000  # per episode

    transcripts = episode_data

    system_prompt = f"""You are a professional podcast script writer creating a conversational digest for the topic "{topic}".

DIALOGUE FORMAT (CRITICAL - EXACT FORMAT REQUIRED):
EVERY speaker turn MUST follow this EXACT format:

SPEAKER_1: [audio_tag] dialogue text here...
SPEAKER_2: [audio_tag] dialogue text here...

REQUIREMENTS:
1. Speaker label MUST be exactly "SPEAKER_1:" or "SPEAKER_2:" (with colon immediately after number)
2. Colon comes IMMEDIATELY after speaker number, BEFORE any audio tags
3. Audio tag MUST come AFTER the colon, wrapped in square brackets [like_this]
4. NO speaker names, NO parentheses, NO brackets before the colon

CORRECT FORMAT:
SPEAKER_1: [excited] This is a groundbreaking development!
SPEAKER_2: [thoughtful] Let me think about the implications here...
SPEAKER_1: [concerned] This raises some important questions.
SPEAKER_2: [hopeful] But there's reason for optimism.

INCORRECT FORMATS (DO NOT USE):
SPEAKER_1 [excited] text... (missing colon)
SPEAKER_1 [excited]: text... (colon after tag)
Host 1: text... (wrong speaker name)
SPEAKER_1 (Jamal): text... (name before colon)

CHARACTER ROLES:
- SPEAKER_1 ({speaker_1_name}): Primary host, introduces topics, asks questions
- SPEAKER_2 ({speaker_2_name}): Expert analyst, provides insights and analysis
- Create natural, engaging conversation with back-and-forth exchanges

TOPIC INSTRUCTIONS:
{instructions_md}
{story_arc_section}

**CRITICAL - STORY ARC GROUNDING:**
Only reference story arcs that have supporting evidence in the episode transcripts provided below.
Do not invent or assume developments not present in the transcript content.
If a story arc is listed above but has no supporting content in today's episodes, do not mention it.

REQUIREMENTS:
- Target 15,000-20,000 characters (this is measured in characters, not words)
- Create engaging dialogue between {speaker_1_name} and {speaker_2_name}
- Use audio tags liberally to add emotional warmth and expression
- Follow the structure outlined in the topic instructions
- Include episode titles and dates when relevant
- Focus on the most important insights and developments
- Maintain natural conversational flow with appropriate turn-taking

Date: {digest_date.strftime('%B %d, %Y')}
Topic: {topic}
Episodes: {len(transcripts)}"""

    user_prompt = f"""Create a dialogue-style digest script from these {len(transcripts)} episode(s):

IMPORTANT - TRANSCRIPT AVAILABILITY:
You have COMPLETE access to ALL {len(transcripts)} episode transcripts provided below. Each transcript contains the full content needed to discuss that episode in detail. DO NOT claim you don't have access to any transcript, as all transcripts are fully provided. If a transcript seems shorter, it's because the episode itself was shorter or content was truncated for length - the key insights are present.

"""

    for i, transcript_data in enumerate(transcripts, 1):
        user_prompt += f"""Episode {i}: "{transcript_data['title']}" (Published: {transcript_data['published_date']}, Relevance Score: {transcript_data['score']:.2f})

Transcript:
{transcript_data['transcript'][:transcript_limit]}

---

"""

    user_prompt += f"""Generate a dialogue script between SPEAKER_1 ({speaker_1_name}) and SPEAKER_2 ({speaker_2_name}) that covers the key insights from these episodes.

REMINDER: You have full transcripts for ALL {len(transcripts)} episodes above. Discuss each episode's content directly based on the transcript provided - do not claim any transcripts are missing or unavailable.

CRITICAL: Use EXACT format for EVERY turn:
SPEAKER_1: [audio_tag] dialogue text...
SPEAKER_2: [audio_tag] dialogue text...

The colon MUST come immediately after the speaker number, BEFORE the audio tag.

Target 15,000-20,000 characters. Use audio tags like [excited], [thoughtful], [concerned], [hopeful], [curious] to add emotional expression."""

    return system_prompt, user_prompt


def call_gpt52_chat(system_prompt, user_prompt, openai_key):
    """GPT-5.2 chat mode (no reasoning)."""
    from openai import OpenAI
    client = OpenAI(api_key=openai_key)

    print("\n" + "="*80)
    print("MODEL 1: GPT-5.2 (chat mode, no reasoning)")
    print("="*80)

    start = time.time()
    response = client.responses.create(
        model="gpt-5.2",
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        max_output_tokens=25000
    )
    elapsed = time.time() - start

    output_text = response.output_text
    char_count = len(output_text)

    # Extract token usage
    usage = response.usage
    input_tokens = usage.input_tokens if usage else 0
    output_tokens = usage.output_tokens if usage else 0

    # Check for reasoning tokens
    reasoning_tokens = 0
    if hasattr(usage, 'output_tokens_details') and usage.output_tokens_details:
        reasoning_tokens = getattr(usage.output_tokens_details, 'reasoning_tokens', 0)

    print(f"  Time: {elapsed:.1f}s")
    print(f"  Output chars: {char_count}")
    print(f"  Input tokens: {input_tokens}")
    print(f"  Output tokens: {output_tokens}")
    print(f"  Reasoning tokens: {reasoning_tokens}")

    # GPT-5.2 pricing: $2/M input, $8/M output (approximate)
    cost = (input_tokens / 1_000_000 * 2.0) + (output_tokens / 1_000_000 * 8.0)
    print(f"  Estimated cost: ${cost:.4f}")

    print(f"\n--- FULL OUTPUT ---\n")
    print(output_text)
    print(f"\n--- END OUTPUT ---\n")

    return {
        'model': 'GPT-5.2 (chat)',
        'output': output_text,
        'char_count': char_count,
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'reasoning_tokens': reasoning_tokens,
        'elapsed': elapsed,
        'cost': cost,
        'pricing': '$2/M input, $8/M output',
    }


def call_gpt52_thinking(system_prompt, user_prompt, openai_key):
    """GPT-5.2 with thinking/reasoning enabled."""
    from openai import OpenAI
    client = OpenAI(api_key=openai_key)

    print("\n" + "="*80)
    print("MODEL 2: GPT-5.2 (with thinking, effort=medium)")
    print("="*80)

    start = time.time()
    response = client.responses.create(
        model="gpt-5.2",
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        reasoning={"effort": "medium"},
        max_output_tokens=25000
    )
    elapsed = time.time() - start

    output_text = response.output_text
    char_count = len(output_text)

    # Extract token usage
    usage = response.usage
    input_tokens = usage.input_tokens if usage else 0
    output_tokens = usage.output_tokens if usage else 0

    # Check for reasoning tokens
    reasoning_tokens = 0
    if hasattr(usage, 'output_tokens_details') and usage.output_tokens_details:
        reasoning_tokens = getattr(usage.output_tokens_details, 'reasoning_tokens', 0)

    print(f"  Time: {elapsed:.1f}s")
    print(f"  Output chars: {char_count}")
    print(f"  Input tokens: {input_tokens}")
    print(f"  Output tokens: {output_tokens}")
    print(f"  Reasoning tokens: {reasoning_tokens}")

    # GPT-5.2 with reasoning: $2/M input, $8/M output + reasoning tokens at output rate
    cost = (input_tokens / 1_000_000 * 2.0) + (output_tokens / 1_000_000 * 8.0)
    print(f"  Estimated cost: ${cost:.4f}")

    print(f"\n--- FULL OUTPUT ---\n")
    print(output_text)
    print(f"\n--- END OUTPUT ---\n")

    return {
        'model': 'GPT-5.2 (thinking)',
        'output': output_text,
        'char_count': char_count,
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'reasoning_tokens': reasoning_tokens,
        'elapsed': elapsed,
        'cost': cost,
        'pricing': '$2/M input, $8/M output (+ reasoning)',
    }


def call_claude_haiku(system_prompt, user_prompt, anthropic_key):
    """Claude Haiku 4.5 using streaming to handle long requests."""
    import anthropic
    client = anthropic.Anthropic(api_key=anthropic_key)

    print("\n" + "="*80)
    print("MODEL 3: Claude Haiku 4.5")
    print("="*80)

    start = time.time()

    # Use streaming to handle long-running requests
    output_text = ""
    input_tokens = 0
    output_tokens = 0

    with client.messages.stream(
        model="claude-haiku-4-5-20251001",
        max_tokens=16000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}]
    ) as stream:
        for text in stream.text_stream:
            output_text += text
            print(text, end="", flush=True)

    # Get final message for usage stats
    final_message = stream.get_final_message()
    elapsed = time.time() - start

    char_count = len(output_text)
    input_tokens = final_message.usage.input_tokens
    output_tokens = final_message.usage.output_tokens

    print(f"\n\n  Time: {elapsed:.1f}s")
    print(f"  Output chars: {char_count}")
    print(f"  Input tokens: {input_tokens}")
    print(f"  Output tokens: {output_tokens}")

    # Claude Haiku 4.5: $0.80/M input, $4/M output
    cost = (input_tokens / 1_000_000 * 0.80) + (output_tokens / 1_000_000 * 4.0)
    print(f"  Estimated cost: ${cost:.4f}")

    return {
        'model': 'Claude Haiku 4.5',
        'output': output_text,
        'char_count': char_count,
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'reasoning_tokens': 0,
        'elapsed': elapsed,
        'cost': cost,
        'pricing': '$0.80/M input, $4/M output',
    }


def call_claude_opus(system_prompt, user_prompt, anthropic_key):
    """Claude Opus 4.5 using streaming."""
    import anthropic
    client = anthropic.Anthropic(api_key=anthropic_key)

    print("\n" + "="*80)
    print("MODEL 4: Claude Opus 4.5")
    print("="*80)

    # Try different model IDs
    model_ids = [
        "claude-opus-4-5-20251101",
    ]

    for model_id in model_ids:
        try:
            print(f"  Trying model ID: {model_id}")
            start = time.time()

            output_text = ""
            with client.messages.stream(
                model=model_id,
                max_tokens=16000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            ) as stream:
                for text in stream.text_stream:
                    output_text += text
                    print(text, end="", flush=True)

            final_message = stream.get_final_message()
            elapsed = time.time() - start

            char_count = len(output_text)
            input_tokens = final_message.usage.input_tokens
            output_tokens = final_message.usage.output_tokens

            print(f"\n\n  Time: {elapsed:.1f}s")
            print(f"  Output chars: {char_count}")
            print(f"  Input tokens: {input_tokens}")
            print(f"  Output tokens: {output_tokens}")

            # Claude Opus 4.5: $15/M input, $75/M output
            cost = (input_tokens / 1_000_000 * 15.0) + (output_tokens / 1_000_000 * 75.0)
            print(f"  Estimated cost: ${cost:.4f}")

            return {
                'model': f'Claude Opus 4.5 ({model_id})',
                'output': output_text,
                'char_count': char_count,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'reasoning_tokens': 0,
                'elapsed': elapsed,
                'cost': cost,
                'pricing': '$15/M input, $75/M output',
            }
        except anthropic.NotFoundError as e:
            print(f"  Model not found: {model_id}: {e}")
            continue
        except Exception as e:
            print(f"  Failed with {model_id}: {e}")
            raise

    raise RuntimeError("All Claude Opus model IDs failed")


def save_results(results, system_prompt, user_prompt):
    """Save all results to files."""
    filenames = {
        'GPT-5.2 (chat)': 'gpt52_chat.md',
        'GPT-5.2 (thinking)': 'gpt52_thinking.md',
        'Claude Haiku 4.5': 'claude_haiku45.md',
    }

    for result in results:
        model = result['model']
        # Find matching filename
        fname = None
        for key, val in filenames.items():
            if key in model:
                fname = val
                break
        if fname is None:
            if 'Opus' in model:
                fname = 'claude_opus45.md'
            else:
                fname = model.replace(' ', '_').replace('(', '').replace(')', '') + '.md'

        filepath = OUTPUT_DIR / fname
        with open(filepath, 'w') as f:
            f.write(f"# {model} Output\n\n")
            f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**Metrics**:\n")
            f.write(f"- Characters: {result['char_count']}\n")
            f.write(f"- Input tokens: {result['input_tokens']}\n")
            f.write(f"- Output tokens: {result['output_tokens']}\n")
            f.write(f"- Reasoning tokens: {result['reasoning_tokens']}\n")
            f.write(f"- Generation time: {result['elapsed']:.1f}s\n")
            f.write(f"- Estimated cost: ${result['cost']:.4f}\n")
            f.write(f"- Pricing: {result['pricing']}\n\n")
            f.write(f"---\n\n")
            f.write(result['output'])
        print(f"Saved: {filepath}")

    # Save comparison report
    report_path = OUTPUT_DIR / 'comparison_report.md'
    with open(report_path, 'w') as f:
        f.write("# Model Comparison Report\n\n")
        f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Task**: Dialogue-style podcast digest generation for AI and Technology topic\n\n")
        f.write(f"**Episodes used**: 4 most recent scored/digested episodes\n\n")

        # Prompt lengths
        f.write(f"## Prompt Details\n\n")
        f.write(f"- System prompt length: {len(system_prompt):,} characters\n")
        f.write(f"- User prompt length: {len(user_prompt):,} characters\n")
        f.write(f"- Total prompt length: {len(system_prompt) + len(user_prompt):,} characters\n\n")

        # Comparison table
        f.write("## Comparison Table\n\n")
        f.write("| Metric | " + " | ".join(r['model'] for r in results) + " |\n")
        f.write("|--------|" + "|".join(["--------"] * len(results)) + "|\n")
        f.write("| Output chars | " + " | ".join(f"{r['char_count']:,}" for r in results) + " |\n")
        f.write("| Input tokens | " + " | ".join(f"{r['input_tokens']:,}" for r in results) + " |\n")
        f.write("| Output tokens | " + " | ".join(f"{r['output_tokens']:,}" for r in results) + " |\n")
        f.write("| Reasoning tokens | " + " | ".join(f"{r['reasoning_tokens']:,}" for r in results) + " |\n")
        f.write("| Generation time (s) | " + " | ".join(f"{r['elapsed']:.1f}" for r in results) + " |\n")
        f.write("| Estimated cost | " + " | ".join(f"${r['cost']:.4f}" for r in results) + " |\n")
        f.write("| Pricing | " + " | ".join(r['pricing'] for r in results) + " |\n")

        f.write("\n## Cost Analysis\n\n")
        costs_sorted = sorted(results, key=lambda r: r['cost'])
        for i, r in enumerate(costs_sorted, 1):
            f.write(f"{i}. **{r['model']}**: ${r['cost']:.4f} ({r['pricing']})\n")

        cheapest = costs_sorted[0]['cost']
        f.write(f"\n**Cost multiples relative to cheapest ({costs_sorted[0]['model']}):**\n\n")
        for r in costs_sorted:
            mult = r['cost'] / cheapest if cheapest > 0 else 0
            f.write(f"- {r['model']}: {mult:.1f}x\n")

        f.write("\n## Speed Analysis\n\n")
        speed_sorted = sorted(results, key=lambda r: r['elapsed'])
        for i, r in enumerate(speed_sorted, 1):
            chars_per_sec = r['char_count'] / r['elapsed'] if r['elapsed'] > 0 else 0
            f.write(f"{i}. **{r['model']}**: {r['elapsed']:.1f}s ({chars_per_sec:.0f} chars/sec)\n")

        f.write("\n## Output Length Analysis\n\n")
        f.write("Target range: 15,000-20,000 characters\n\n")
        for r in results:
            in_range = "IN RANGE" if 15000 <= r['char_count'] <= 20000 else "OUT OF RANGE"
            f.write(f"- **{r['model']}**: {r['char_count']:,} chars ({in_range})\n")

    print(f"Saved: {report_path}")


def main():
    print("=" * 80)
    print("PODCAST DIGEST MODEL COMPARISON")
    print("=" * 80)
    print()

    # Step 1: Extract inputs
    print("Step 1: Extracting inputs from database...")
    episode_data, instructions_md, voice_config, arc_context = get_episodes_and_topic()
    print(f"  Episodes: {len(episode_data)}")
    for ep in episode_data:
        print(f"    - {ep['title']} ({ep['published_date']}, score={ep['score']:.2f}, "
              f"transcript={len(ep['transcript']):,} chars)")
    print(f"  Instructions: {len(instructions_md):,} chars")
    print(f"  Arc context: {len(arc_context):,} chars")
    print()

    # Step 2: Build prompts
    print("Step 2: Building prompts...")
    system_prompt, user_prompt = build_prompts(episode_data, instructions_md, voice_config, arc_context)
    print(f"  System prompt: {len(system_prompt):,} chars")
    print(f"  User prompt: {len(user_prompt):,} chars")
    print(f"  Total prompt: {len(system_prompt) + len(user_prompt):,} chars")
    print()

    # API keys
    openai_key = os.getenv('OPENAI_API_KEY')
    anthropic_key = os.getenv('ANTHROPIC_API_KEY')

    if not openai_key:
        raise RuntimeError("OPENAI_API_KEY not found in environment")
    if not anthropic_key:
        raise RuntimeError("ANTHROPIC_API_KEY not found in environment")

    # Step 3: Call all 4 models sequentially
    results = []

    print("Step 3: Calling models sequentially...")

    # Model 1: GPT-5.2 chat
    try:
        r1 = call_gpt52_chat(system_prompt, user_prompt, openai_key)
        results.append(r1)
    except Exception as e:
        print(f"  ERROR: GPT-5.2 chat failed: {e}")

    # Model 2: GPT-5.2 thinking
    try:
        r2 = call_gpt52_thinking(system_prompt, user_prompt, openai_key)
        results.append(r2)
    except Exception as e:
        print(f"  ERROR: GPT-5.2 thinking failed: {e}")

    # Model 3: Claude Haiku 4.5
    try:
        r3 = call_claude_haiku(system_prompt, user_prompt, anthropic_key)
        results.append(r3)
    except Exception as e:
        print(f"  ERROR: Claude Haiku 4.5 failed: {e}")

    # Model 4: Claude Opus 4.5
    try:
        r4 = call_claude_opus(system_prompt, user_prompt, anthropic_key)
        results.append(r4)
    except Exception as e:
        print(f"  ERROR: Claude Opus 4.5 failed: {e}")

    # Step 4: Save results
    print("\n" + "=" * 80)
    print("Step 4: Saving results...")
    print("=" * 80)
    save_results(results, system_prompt, user_prompt)

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\n{'Model':<30} {'Chars':>8} {'In Tok':>8} {'Out Tok':>8} {'Think':>8} {'Time':>8} {'Cost':>10}")
    print("-" * 90)
    for r in results:
        print(f"{r['model']:<30} {r['char_count']:>8,} {r['input_tokens']:>8,} {r['output_tokens']:>8,} "
              f"{r['reasoning_tokens']:>8,} {r['elapsed']:>7.1f}s ${r['cost']:>8.4f}")

    total_cost = sum(r['cost'] for r in results)
    total_time = sum(r['elapsed'] for r in results)
    print("-" * 90)
    print(f"{'TOTAL':<30} {'':>8} {'':>8} {'':>8} {'':>8} {total_time:>7.1f}s ${total_cost:>8.4f}")
    print()

    print("Done! Files saved to:", OUTPUT_DIR)


if __name__ == '__main__':
    main()
