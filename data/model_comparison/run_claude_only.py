#!/usr/bin/env python3
"""
Run only the Claude models (Haiku 4.5 and Opus 4.5) for comparison.
GPT-5.2 results already saved from previous run.
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

from run_comparison import get_episodes_and_topic, build_prompts, save_results

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
    print("CLAUDE MODELS COMPARISON (Haiku 4.5 + Opus 4.5)")
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

    results = []

    # Claude Haiku 4.5
    print("\nStep 3: Calling Claude Haiku 4.5...")
    try:
        r = call_claude_streaming(
            "claude-haiku-4-5-20251001",
            "Claude Haiku 4.5",
            system_prompt, user_prompt, api_key,
            pricing_in=0.80, pricing_out=4.0
        )
        results.append(r)

        # Save immediately
        with open(OUTPUT_DIR / 'claude_haiku45.md', 'w') as f:
            f.write(f"# Claude Haiku 4.5 Output\n\n")
            f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**Metrics**:\n")
            f.write(f"- Characters: {r['char_count']}\n")
            f.write(f"- Input tokens: {r['input_tokens']}\n")
            f.write(f"- Output tokens: {r['output_tokens']}\n")
            f.write(f"- Generation time: {r['elapsed']:.1f}s\n")
            f.write(f"- Estimated cost: ${r['cost']:.4f}\n\n---\n\n")
            f.write(r['output'])
        print(f"Saved: {OUTPUT_DIR / 'claude_haiku45.md'}")
    except Exception as e:
        print(f"  ERROR: {e}")

    # Claude Opus 4.5
    print("\nStep 4: Calling Claude Opus 4.5...")
    try:
        r = call_claude_streaming(
            "claude-opus-4-5-20251101",
            "Claude Opus 4.5",
            system_prompt, user_prompt, api_key,
            pricing_in=15.0, pricing_out=75.0
        )
        results.append(r)

        # Save immediately
        with open(OUTPUT_DIR / 'claude_opus45.md', 'w') as f:
            f.write(f"# Claude Opus 4.5 Output\n\n")
            f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**Metrics**:\n")
            f.write(f"- Characters: {r['char_count']}\n")
            f.write(f"- Input tokens: {r['input_tokens']}\n")
            f.write(f"- Output tokens: {r['output_tokens']}\n")
            f.write(f"- Generation time: {r['elapsed']:.1f}s\n")
            f.write(f"- Estimated cost: ${r['cost']:.4f}\n\n---\n\n")
            f.write(r['output'])
        print(f"Saved: {OUTPUT_DIR / 'claude_opus45.md'}")
    except Exception as e:
        print(f"  ERROR: {e}")

    # Print summary
    print("\n" + "=" * 80)
    print("CLAUDE SUMMARY")
    print("=" * 80)
    print(f"\n{'Model':<25} {'Chars':>8} {'In Tok':>8} {'Out Tok':>8} {'Time':>8} {'Cost':>10}")
    print("-" * 75)
    for r in results:
        print(f"{r['model']:<25} {r['char_count']:>8,} {r['input_tokens']:>8,} {r['output_tokens']:>8,} "
              f"{r['elapsed']:>7.1f}s ${r['cost']:>8.4f}")

    # Now build the combined comparison report with GPT results
    print("\nBuilding combined comparison report...")

    # Load GPT results from saved files
    all_results = []

    # GPT-5.2 chat
    gpt_chat_path = OUTPUT_DIR / 'gpt52_chat.md'
    if gpt_chat_path.exists():
        all_results.append({
            'model': 'GPT-5.2 (chat)',
            'char_count': 23330,
            'input_tokens': 28894,
            'output_tokens': 5303,
            'reasoning_tokens': 0,
            'elapsed': 103.1,
            'cost': 0.1002,
            'pricing': '$2/M input, $8/M output',
        })

    # GPT-5.2 thinking
    gpt_think_path = OUTPUT_DIR / 'gpt52_thinking.md'
    if gpt_think_path.exists():
        all_results.append({
            'model': 'GPT-5.2 (thinking)',
            'char_count': 21357,
            'input_tokens': 28894,
            'output_tokens': 6155,
            'reasoning_tokens': 1360,
            'elapsed': 121.5,
            'cost': 0.1070,
            'pricing': '$2/M input, $8/M output (+reasoning)',
        })

    all_results.extend(results)

    # Write combined report
    report_path = OUTPUT_DIR / 'comparison_report.md'
    with open(report_path, 'w') as f:
        f.write("# Model Comparison Report\n\n")
        f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Task**: Dialogue-style podcast digest generation for AI and Technology topic\n\n")
        f.write(f"**Episodes used**: 4 most recent scored/digested episodes (Feb 19, 2026)\n\n")

        f.write(f"## Prompt Details\n\n")
        f.write(f"- System prompt length: {len(system_prompt):,} characters\n")
        f.write(f"- User prompt length: {len(user_prompt):,} characters\n")
        f.write(f"- Total prompt length: {len(system_prompt) + len(user_prompt):,} characters\n\n")

        f.write("## Comparison Table\n\n")
        f.write("| Metric | " + " | ".join(r['model'] for r in all_results) + " |\n")
        f.write("|--------|" + "|".join(["--------"] * len(all_results)) + "|\n")
        f.write("| Output chars | " + " | ".join(f"{r['char_count']:,}" for r in all_results) + " |\n")
        f.write("| Input tokens | " + " | ".join(f"{r['input_tokens']:,}" for r in all_results) + " |\n")
        f.write("| Output tokens | " + " | ".join(f"{r['output_tokens']:,}" for r in all_results) + " |\n")
        f.write("| Reasoning tokens | " + " | ".join(f"{r.get('reasoning_tokens', 0):,}" for r in all_results) + " |\n")
        f.write("| Generation time (s) | " + " | ".join(f"{r['elapsed']:.1f}" for r in all_results) + " |\n")
        f.write("| Estimated cost | " + " | ".join(f"${r['cost']:.4f}" for r in all_results) + " |\n")
        f.write("| Pricing | " + " | ".join(r['pricing'] for r in all_results) + " |\n")

        f.write("\n## Cost Analysis\n\n")
        costs_sorted = sorted(all_results, key=lambda r: r['cost'])
        for i, r in enumerate(costs_sorted, 1):
            f.write(f"{i}. **{r['model']}**: ${r['cost']:.4f} ({r['pricing']})\n")

        cheapest = costs_sorted[0]['cost']
        f.write(f"\n**Cost multiples relative to cheapest ({costs_sorted[0]['model']}):**\n\n")
        for r in costs_sorted:
            mult = r['cost'] / cheapest if cheapest > 0 else 0
            f.write(f"- {r['model']}: {mult:.1f}x\n")

        f.write("\n## Speed Analysis\n\n")
        speed_sorted = sorted(all_results, key=lambda r: r['elapsed'])
        for i, r in enumerate(speed_sorted, 1):
            chars_per_sec = r['char_count'] / r['elapsed'] if r['elapsed'] > 0 else 0
            f.write(f"{i}. **{r['model']}**: {r['elapsed']:.1f}s ({chars_per_sec:.0f} chars/sec)\n")

        f.write("\n## Output Length Analysis\n\n")
        f.write("Target range: 15,000-20,000 characters\n\n")
        for r in all_results:
            in_range = "IN RANGE" if 15000 <= r['char_count'] <= 20000 else "OUT OF RANGE"
            f.write(f"- **{r['model']}**: {r['char_count']:,} chars ({in_range})\n")

    print(f"Saved combined report: {report_path}")
    print("\nDone!")


if __name__ == '__main__':
    main()
