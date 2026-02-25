#!/usr/bin/env python3
"""
Test claude -p digest generation with tuned prompt.

Pulls the same transcripts used in a baseline digest (generated via direct API),
regenerates using claude -p with the tuned skill prompt, and saves both for comparison.

Usage:
    python3 scripts/test_claude_p_digest.py --baseline-digest-id 548
"""

import os
import sys
import json
import time
import subprocess
import argparse
from pathlib import Path
from datetime import date

# Ensure project root is on sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Load environment variables
env_path = Path(project_root) / '.env'
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            key, _, value = line.partition('=')
            os.environ[key.strip()] = value.strip()


def get_baseline_data(digest_id: int):
    """Pull baseline digest and its episode transcripts from database."""
    from src.database.models import get_database_manager
    from src.database.sqlalchemy_models import Digest, Episode
    from sqlalchemy import text

    db = get_database_manager()
    session = db.get_session()

    # Get the baseline digest
    digest = session.query(Digest).filter(Digest.id == digest_id).first()
    if not digest:
        print(f"ERROR: Digest {digest_id} not found")
        sys.exit(1)

    # Get linked episode IDs
    result = session.execute(
        text("SELECT episode_id FROM digest_episode_links WHERE digest_id = :did"),
        {"did": digest_id}
    )
    ep_ids = [r[0] for r in result.fetchall()]

    # Get episode data
    episodes = []
    for eid in ep_ids:
        ep = session.query(Episode).filter(Episode.id == eid).first()
        if ep and ep.transcript_content:
            episodes.append({
                'id': ep.id,
                'title': ep.title,
                'published_date': ep.published_date.strftime('%Y-%m-%d') if ep.published_date else 'unknown',
                'transcript': ep.transcript_content,
                'score': ep.scores.get('AI and Technology', 0.0) if ep.scores else 0.0,
            })

    # Get topic instructions
    result = session.execute(
        text("SELECT instructions_md FROM topics WHERE name = 'AI and Technology'")
    )
    row = result.fetchone()
    topic_instructions = row[0] if row else ""

    session.close()

    return {
        'digest': {
            'id': digest.id,
            'date': str(digest.digest_date),
            'script': digest.script_content,
            'chars': len(digest.script_content or ''),
            'episode_count': digest.episode_count,
        },
        'episodes': episodes,
        'topic_instructions': topic_instructions,
    }


def load_skill_prompt():
    """Load the tuned digest generation skill."""
    skill_path = Path(project_root) / '.claude' / 'commands' / 'generate-digest.md'
    if not skill_path.exists():
        print(f"ERROR: Skill file not found: {skill_path}")
        sys.exit(1)
    return skill_path.read_text()


def build_prompt(skill_content: str, topic_instructions: str, episodes: list, digest_date: str):
    """Build the full prompt for claude -p, mirroring _build_claude_p_dialogue_prompt."""

    system_part = (
        f"{skill_content}\n\n"
        f"## Topic-Specific Instructions\n{topic_instructions}\n\n"
        f"Date: {digest_date}\n"
        f"Topic: AI and Technology\n"
        f"Episodes: {len(episodes)}\n\n"
        f"CHARACTER ROLES:\n"
        f"- SPEAKER_1 (Natasha): Primary host, introduces topics, asks questions\n"
        f"- SPEAKER_2 (Zuri): Expert analyst, provides insights and analysis"
    )

    user_part = f"""Create a dialogue-style digest script from these {len(episodes)} episodes.

You have COMPLETE access to ALL {len(episodes)} episode transcripts below. Each transcript is provided in full.

"""

    for i, ep in enumerate(episodes, 1):
        user_part += f"""Episode {i}: "{ep['title']}" (Published: {ep['published_date']}, Score: {ep['score']:.2f})

Transcript:
{ep['transcript']}

---

"""

    user_part += f"""Generate a dialogue script between SPEAKER_1 (Natasha) and SPEAKER_2 (Zuri).

REMINDERS:
- Target 18,000-22,000 characters. Do NOT exceed 25,000.
- Audio tags on 30-40% of turns MAX. Most turns have NO tag. Max 25 tags total.
- Use EXACT format: SPEAKER_1: [tag] text... or SPEAKER_1: text...
- Cover all {len(episodes)} episodes using the transcripts above.
"""

    return system_part + "\n\n" + user_part


def call_claude_p(prompt: str, timeout: int = 600) -> str:
    """Call claude -p with the prompt via stdin."""
    claude_path = os.path.expanduser("~/.local/bin/claude")
    if not os.path.exists(claude_path):
        claude_path = "claude"

    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    result = subprocess.run(
        [claude_path, "-p", "-"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )

    if result.returncode != 0:
        raise RuntimeError(f"claude -p failed (exit {result.returncode}): {result.stderr[:500]}")

    return result.stdout.strip()


def analyze_script(script: str, label: str):
    """Quick quality metrics for a script."""
    import re
    lines = script.strip().split('\n')
    speaker_lines = [l for l in lines if l.startswith('SPEAKER_')]
    tag_pattern = re.compile(r'\[([a-z]+)\]')

    all_tags = []
    tagged_turns = 0
    for line in speaker_lines:
        tags = tag_pattern.findall(line)
        if tags:
            tagged_turns += 1
            all_tags.extend(tags)

    from collections import Counter
    tag_counts = Counter(all_tags)

    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(f"  Characters:      {len(script):,}")
    print(f"  Speaker turns:   {len(speaker_lines)}")
    print(f"  Tagged turns:    {tagged_turns} ({tagged_turns/max(len(speaker_lines),1)*100:.0f}%)")
    print(f"  Total tags:      {len(all_tags)}")
    print(f"  Unique tags:     {len(tag_counts)}")
    print(f"  Tag distribution:")
    for tag, count in tag_counts.most_common():
        print(f"    [{tag}]: {count}")
    print(f"  Preview (first 500 chars):")
    print(f"    {script[:500]}")
    print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline-digest-id', type=int, default=548,
                        help='Digest ID to use as baseline (default: 548)')
    args = parser.parse_args()

    print("=" * 60)
    print("CLAUDE -P DIGEST GENERATION TEST")
    print("=" * 60)

    # 1. Get baseline data
    print(f"\n1. Loading baseline digest {args.baseline_digest_id} and transcripts...")
    data = get_baseline_data(args.baseline_digest_id)
    print(f"   Baseline: {data['digest']['chars']:,} chars, {data['digest']['episode_count']} episodes")
    print(f"   Episodes:")
    for ep in data['episodes']:
        print(f"     - {ep['title'][:60]} ({len(ep['transcript']):,} chars)")

    # 2. Load skill prompt
    print(f"\n2. Loading tuned skill prompt...")
    skill_content = load_skill_prompt()
    print(f"   Skill: {len(skill_content)} chars")

    # 3. Build prompt
    print(f"\n3. Building prompt...")
    prompt = build_prompt(skill_content, data['topic_instructions'], data['episodes'], data['digest']['date'])
    print(f"   Total prompt: {len(prompt):,} chars")

    # 4. Generate via claude -p
    print(f"\n4. Generating digest via claude -p...")
    start = time.time()
    new_script = call_claude_p(prompt, timeout=900)
    elapsed = time.time() - start
    print(f"   Generated in {elapsed:.1f}s")

    # 5. Analyze both
    analyze_script(data['digest']['script'], f"BASELINE (Digest {args.baseline_digest_id}, Sonnet via API)")
    analyze_script(new_script, "TUNED CLAUDE -P")

    # 6. Save outputs
    output_dir = Path(project_root) / 'data' / 'claude_p_comparison'
    output_dir.mkdir(exist_ok=True)

    baseline_path = output_dir / f"baseline_{args.baseline_digest_id}.md"
    baseline_path.write_text(data['digest']['script'])

    tuned_path = output_dir / f"tuned_claude_p_{args.baseline_digest_id}.md"
    tuned_path.write_text(new_script)

    print(f"\n6. Saved outputs to {output_dir}/")
    print(f"   Baseline: {baseline_path.name}")
    print(f"   Tuned:    {tuned_path.name}")

    # 7. Summary comparison
    print(f"\n{'='*60}")
    print(f"  COMPARISON SUMMARY")
    print(f"{'='*60}")
    print(f"  {'Metric':<25} {'Baseline':<15} {'Tuned -p':<15}")
    print(f"  {'-'*55}")
    print(f"  {'Characters':<25} {data['digest']['chars']:<15,} {len(new_script):<15,}")

    print(f"\n  Both scripts saved for manual review and scoring.")


if __name__ == "__main__":
    main()
