#!/usr/bin/env python3
"""
Reset episodes to pending status for testing the audio pipeline.
Usage: python3 reset_episodes_for_testing.py [--count N] [--delete-transcripts]
"""

import sys
import argparse
import os
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from database.models import get_episode_repo

def delete_transcript_files(episodes, transcript_dir="data/transcripts"):
    """Delete transcript files for given episodes"""
    transcript_dir = Path(transcript_dir)
    deleted_files = []

    for episode in episodes:
        if episode.transcript_path:
            transcript_path = Path(episode.transcript_path)

            # Delete the main transcript file
            if transcript_path.exists():
                try:
                    transcript_path.unlink()
                    deleted_files.append(str(transcript_path))
                    print(f"🗑️  Deleted transcript: {transcript_path}")
                except Exception as e:
                    print(f"❌ Failed to delete {transcript_path}: {e}")

            # Also look for and delete progress files and related files
            episode_guid = episode.episode_guid
            progress_file = transcript_dir / f"{episode_guid}-progress.txt"
            if progress_file.exists():
                try:
                    progress_file.unlink()
                    deleted_files.append(str(progress_file))
                    print(f"🗑️  Deleted progress file: {progress_file}")
                except Exception as e:
                    print(f"❌ Failed to delete progress file {progress_file}: {e}")

    return deleted_files

def get_recent_episodes_from_past_week(repo, max_count=10):
    """Get episodes from the past week, up to max_count"""
    # Get recent episodes (more than we need to ensure we have enough from past week)
    all_recent = repo.get_recent_episodes(50)

    # Filter to episodes from past 7 days
    one_week_ago = datetime.now() - timedelta(days=7)
    past_week_episodes = []

    for ep in all_recent:
        if ep.published_date and ep.published_date >= one_week_ago:
            past_week_episodes.append(ep)

    # Return up to max_count episodes
    return past_week_episodes[:max_count]

def main():
    parser = argparse.ArgumentParser(description='Reset episodes for testing')
    parser.add_argument('--count', '-c', type=int, default=10,
                       help='Number of episodes to reset (default: 10)')
    parser.add_argument('--status', '-s', default='pending',
                       help='Status to reset episodes to (default: pending)')
    parser.add_argument('--delete-transcripts', '-d', action='store_true',
                       help='Delete transcript files for reset episodes')
    parser.add_argument('--past-week', '-w', action='store_true', default=True,
                       help='Only select episodes from past week (default: True)')
    args = parser.parse_args()

    repo = get_episode_repo()

    if args.delete_transcripts:
        print(f"Resetting {args.count} episodes from past week to '{args.status}' status and DELETING transcripts...")
    else:
        print(f"Resetting {args.count} episodes from past week to '{args.status}' status...")

    # Get candidates based on whether we want past week only
    if args.past_week:
        candidates = get_recent_episodes_from_past_week(repo, 50)
        print(f"Found {len(candidates)} episodes from past week")
    else:
        episodes = repo.get_recent_episodes(50)
        candidates = [ep for ep in episodes if ep.status != args.status]

    # Filter out episodes already at target status
    candidates = [ep for ep in candidates if ep.status != args.status]

    if len(candidates) < args.count:
        print(f"Warning: Only {len(candidates)} episodes available to reset")
        args.count = len(candidates)

    episodes_to_reset = candidates[:args.count]

    # Delete transcript files first if requested
    if args.delete_transcripts and episodes_to_reset:
        print(f"\n🗑️  Deleting transcript files for {len(episodes_to_reset)} episodes...")
        deleted_files = delete_transcript_files(episodes_to_reset)
        print(f"Deleted {len(deleted_files)} transcript-related files")

        # Clear transcript_path from database
        for ep in episodes_to_reset:
            if ep.transcript_path:
                repo.update_transcript_path(ep.id, None)
                print(f"🔄 Cleared transcript path for: {ep.title[:50]}...")

    # Reset status
    reset_count = 0
    for ep in episodes_to_reset:
        print(f"Resetting: {ep.title[:50]}... | {ep.status} -> {args.status}")
        repo.update_status(ep.episode_guid, args.status)
        reset_count += 1

    print(f"\n✅ Successfully reset {reset_count} episodes to '{args.status}' status")

    # Show current pending episodes
    episodes = repo.get_recent_episodes(15)
    target_episodes = [ep for ep in episodes if ep.status == args.status]

    print(f"\nEpisodes now in '{args.status}' status:")
    for ep in target_episodes:
        transcript_status = "📄" if ep.transcript_path else "❌"
        print(f"- {transcript_status} {ep.title[:55]:<55} | {ep.published_date}")

    print(f"\nTotal {args.status} episodes: {len(target_episodes)}")
    if args.status == 'pending':
        print(f"\nYou can now test the pipeline with: python3 run_full_pipeline_orchestrator.py --phase audio --limit {len(target_episodes)}")

if __name__ == "__main__":
    main()