#!/usr/bin/env python3
"""
Run Sonnet 4.6 comparison using same inputs as the other model comparisons.
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load .env
from dotenv import load_dotenv
load_dotenv(project_root / '.env')

from run_comparison import get_episodes_and_topic, build_prompts

OUTPUT_DIR = Path(__file__).parent

import anthropic


def call_claude_streaming(model_id, model_label, system_prompt, user_prompt, api_key, pricing_in, pricing_out):
    """Generic Claude streaming call."""
    client = anthropic.Anthropic(api_key=api_key)

    print("\n" + "="*80)
    print(f"MODEL: {model_label} ({model_id})")
    print("="*80)

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
    print("CLAUDE SONNET 4.6 COMPARISON")
    print("=" * 80)

    # Extract inputs
    print("\nStep 1: Extracting inputs from database...")
    episode_data, instructions_md, voice_config, arc_context = get_episodes_and_topic()
    print(f"  Episodes: {len(episode_data)}")
    for ep in episode_data:
        print(f"    - {ep['title']} ({ep['published_date']}, score={ep['score']:.2f}, "
              f"transcript={len(ep['transcript']):,} chars)")

    # Build prompts
    print("\nStep 2: Building prompts...")
    system_prompt, user_prompt = build_prompts(episode_data, instructions_md, voice_config, arc_context)
    print(f"  System prompt: {len(system_prompt):,} chars")
    print(f"  User prompt: {len(user_prompt):,} chars")

    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not found")

    # Claude Sonnet 4.5 (to match the comparison with Haiku 4.5 and Opus 4.5)
    # Try multiple model IDs
    model_ids = [
        ("claude-sonnet-4-5-20241022", "Claude Sonnet 4.5"),
        ("claude-sonnet-4-6", "Claude Sonnet 4.6"),
    ]

    r = None
    for model_id, label in model_ids:
        try:
            print(f"\nStep 3: Calling {label} ({model_id})...")
            r = call_claude_streaming(
                model_id,
                label,
                system_prompt, user_prompt, api_key,
                pricing_in=3.0, pricing_out=15.0
            )
            break
        except Exception as e:
            print(f"  Model {model_id} failed: {e}")
            continue

    if r is None:
        raise RuntimeError("All Sonnet model IDs failed")

    # Save result
    fname = 'claude_sonnet46.md' if '4.6' in r['model'] else 'claude_sonnet45.md'
    with open(OUTPUT_DIR / fname, 'w') as f:
        f.write(f"# {r['model']} Output\n\n")
        f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Metrics**:\n")
        f.write(f"- Characters: {r['char_count']}\n")
        f.write(f"- Input tokens: {r['input_tokens']}\n")
        f.write(f"- Output tokens: {r['output_tokens']}\n")
        f.write(f"- Generation time: {r['elapsed']:.1f}s\n")
        f.write(f"- Estimated cost: ${r['cost']:.4f}\n")
        f.write(f"- Pricing: {r['pricing']}\n\n---\n\n")
        f.write(r['output'])
    print(f"Saved: {OUTPUT_DIR / fname}")

    # Print summary
    print("\n" + "=" * 80)
    print("SONNET SUMMARY")
    print("=" * 80)
    print(f"\n{'Model':<25} {'Chars':>8} {'In Tok':>8} {'Out Tok':>8} {'Time':>8} {'Cost':>10}")
    print("-" * 75)
    print(f"{r['model']:<25} {r['char_count']:>8,} {r['input_tokens']:>8,} {r['output_tokens']:>8,} "
          f"{r['elapsed']:>7.1f}s ${r['cost']:>8.4f}")

    print("\nDone!")


if __name__ == '__main__':
    main()
