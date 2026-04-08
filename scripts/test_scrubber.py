#!/usr/bin/env python3
"""Smoke test for src/generation/transcript_scrubber.py.

Loads one episode's transcript and runs the scrubber against a list of
saturated topics. Prints a diff summary so we can verify the scrub is
removing the right content without mangling the rest.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))
from src.utils.phase_bootstrap import bootstrap_phase
bootstrap_phase()

from src.database.models import get_episode_repo
from src.generation.transcript_scrubber import scrub_transcript

# Episode 1887: "Claude Code source code LEAKED" (feed 7). Should have plenty
# of Claude Code leak content, which we'll ask the scrubber to remove.
EPISODE_ID = 1887
SATURATED_TOPICS = [
    "Claude Code internal source code leak",
    "OpenAI major financing round and valuation",
    "Anthropic DMCA takedown blitz",
]

ep = get_episode_repo().get_by_id(EPISODE_ID)
if not ep:
    print(f"ERROR: episode {EPISODE_ID} not found")
    sys.exit(1)

print(f"Episode {ep.id}: '{ep.title[:70]}'")
print(f"  transcript chars: {len(ep.transcript_content or '')}")
print(f"  saturated topics: {SATURATED_TOPICS}")
print()

cleaned, result = scrub_transcript(ep.transcript_content or "", SATURATED_TOPICS, timeout=900)

print("=== Scrub result ===")
print(f"  before: {result.chars_before}")
print(f"  after:  {result.chars_after}")
print(f"  delta:  {result.delta:+d}")
print(f"  skipped: {result.skipped} ({result.skip_reason or '—'})")

if not result.skipped:
    # Show what's left — first 400 chars and last 400 chars
    print()
    print("=== First 400 chars of cleaned transcript ===")
    print(cleaned[:400])
    print()
    print("=== Last 400 chars ===")
    print(cleaned[-400:])
