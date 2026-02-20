#!/usr/bin/env python3
"""
Re-run Opus 4.5 with current database state for fair comparison with Sonnet 4.6.
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / '.env')

from run_comparison import get_episodes_and_topic, build_prompts

OUTPUT_DIR = Path(__file__).parent

import anthropic


def call_claude_streaming(model_id, model_label, system_prompt, user_prompt, api_key, pricing_in, pricing_out):
    client = anthropic.Anthropic(api_key=api_key)

    print(f"\n{'='*80}")
    print(f"MODEL: {model_label} ({model_id})")
    print(f"{'='*80}")

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

    cost = (input_tokens / 1_000_000 * pricing_in) + (output_tokens / 1_000_000 * pricing_out)
    print(f"  Estimated cost: ${cost:.4f}")

    return {
        'model': model_label,
        'output': output_text,
        'char_count': char_count,
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'reasoning_tokens': 0,
        'elapsed': elapsed,
        'cost': cost,
        'pricing': f'${pricing_in}/M input, ${pricing_out}/M output',
    }


def main():
    print("=" * 80)
    print("OPUS 4.5 RE-TEST (same inputs as Sonnet 4.6 run)")
    print("=" * 80)

    print("\nStep 1: Extracting inputs from database...")
    episode_data, instructions_md, voice_config, arc_context = get_episodes_and_topic()
    print(f"  Episodes: {len(episode_data)}")
    for ep in episode_data:
        print(f"    - {ep['title']} ({ep['published_date']}, score={ep['score']:.2f}, "
              f"transcript={len(ep['transcript']):,} chars)")

    print("\nStep 2: Building prompts...")
    system_prompt, user_prompt = build_prompts(episode_data, instructions_md, voice_config, arc_context)
    print(f"  System prompt: {len(system_prompt):,} chars")
    print(f"  User prompt: {len(user_prompt):,} chars")
    print(f"  Total: {len(system_prompt) + len(user_prompt):,} chars")

    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not found")

    # Run Opus 4.5
    print("\nStep 3: Calling Claude Opus 4.5...")
    r = call_claude_streaming(
        "claude-opus-4-5-20251101",
        "Claude Opus 4.5",
        system_prompt, user_prompt, api_key,
        pricing_in=15.0, pricing_out=75.0
    )

    # Save
    with open(OUTPUT_DIR / 'claude_opus45_v2.md', 'w') as f:
        f.write(f"# Claude Opus 4.5 Output (Re-test)\n\n")
        f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Metrics**:\n")
        f.write(f"- Characters: {r['char_count']}\n")
        f.write(f"- Input tokens: {r['input_tokens']}\n")
        f.write(f"- Output tokens: {r['output_tokens']}\n")
        f.write(f"- Generation time: {r['elapsed']:.1f}s\n")
        f.write(f"- Estimated cost: ${r['cost']:.4f}\n")
        f.write(f"- Pricing: {r['pricing']}\n\n---\n\n")
        f.write(r['output'])
    print(f"\nSaved: {OUTPUT_DIR / 'claude_opus45_v2.md'}")


if __name__ == '__main__':
    main()
