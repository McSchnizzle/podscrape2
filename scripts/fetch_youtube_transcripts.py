#!/usr/bin/env python3
"""
Mac-side YouTube Transcript Fetcher

Runs on your Mac (residential IP) to fetch YouTube transcripts that et01 can't access
due to IP blocking. Fetches a small batch per run to look like normal human traffic.

Usage:
    python3 scripts/fetch_youtube_transcripts.py          # Default: 5 episodes
    python3 scripts/fetch_youtube_transcripts.py -n 10    # Fetch up to 10
    python3 scripts/fetch_youtube_transcripts.py --dry-run # Preview what would be fetched

Designed to run manually or via launchd/cron on your Mac. NOT for et01.
"""

import os
import sys
import re
import time
import random
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

# Bootstrap environment (.env loading, database URL)
from src.config.env import load_env, require_database_url
load_env()
require_database_url()

from src.database.models import get_database_manager
from src.database.sqlalchemy_models import Episode as EpisodeModel

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# YouTube URL patterns
YOUTUBE_PATTERNS = [
    r'youtube\.com/watch',
    r'youtube\.com/shorts/',
    r'youtu\.be/',
]


def is_youtube_url(url: str) -> bool:
    """Check if a URL is a YouTube video URL (excludes Shorts)."""
    if not url:
        return False
    if 'youtube.com/shorts/' in url:
        return False
    return any(re.search(p, url) for p in YOUTUBE_PATTERNS)


def extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url or '')
        if match:
            return match.group(1)
    return None


def get_pending_youtube_episodes(limit: int, include_failed: bool = False,
                                  include_zero_word: bool = False) -> list:
    """Query database for pending (and optionally failed/0-word) episodes with YouTube URLs."""
    db = get_database_manager()
    with db.get_session() as session:
        statuses = ['pending']
        if include_failed:
            statuses.append('failed')

        from sqlalchemy import or_
        filters = [EpisodeModel.status.in_(statuses)]
        if include_zero_word:
            # Rescue episodes that were scored/not_relevant with 0-word transcripts
            filters = [or_(
                EpisodeModel.status.in_(statuses),
                (EpisodeModel.transcript_word_count == 0) | (EpisodeModel.transcript_word_count.is_(None))
            )]

        episodes = session.query(EpisodeModel)\
            .filter(*filters)\
            .order_by(EpisodeModel.published_date.asc())\
            .all()

        # Filter to YouTube URLs
        youtube_eps = []
        for ep in episodes:
            if is_youtube_url(ep.audio_url):
                vid = extract_video_id(ep.audio_url)
                if vid:
                    youtube_eps.append({
                        'guid': ep.episode_guid,
                        'title': ep.title,
                        'audio_url': ep.audio_url,
                        'video_id': vid,
                        'published_date': ep.published_date,
                    })

        # Return up to limit, oldest first
        return youtube_eps[:limit]


def fetch_transcript(video_id: str) -> dict | None:
    """Fetch transcript text for a YouTube video using youtube-transcript-api."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import (
            NoTranscriptFound, TranscriptsDisabled, CouldNotRetrieveTranscript
        )
    except ImportError:
        logger.error("youtube-transcript-api not installed: pip3 install youtube-transcript-api")
        return None

    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)

        # Try manual English first, then auto-generated, then anything
        transcript = None
        language = 'en'
        is_generated = False

        for lang in ['en', 'en-US', 'en-GB']:
            try:
                transcript = transcript_list.find_manually_created_transcript([lang])
                language = lang
                is_generated = False
                break
            except NoTranscriptFound:
                continue

        if transcript is None:
            for lang in ['en', 'en-US', 'en-GB']:
                try:
                    transcript = transcript_list.find_generated_transcript([lang])
                    language = lang
                    is_generated = True
                    break
                except NoTranscriptFound:
                    continue

        if transcript is None:
            available = list(transcript_list)
            if available:
                transcript = available[0]
                language = transcript.language_code
                is_generated = transcript.is_generated
            else:
                logger.warning(f"  No transcripts available for {video_id}")
                return None

        # Fetch the actual transcript data
        data = transcript.fetch()

        # Build text from segments
        full_text = " ".join(seg.text.strip() for seg in data if seg.text.strip())
        word_count = len(full_text.split())

        if word_count == 0:
            logger.warning(f"  Transcript has 0 words for {video_id}")
            return None

        return {
            'text': full_text,
            'word_count': word_count,
            'language': language,
            'is_generated': is_generated,
        }

    except Exception as e:
        logger.error(f"  Transcript fetch failed for {video_id}: {e}")
        return None


def save_transcript(episode_guid: str, video_id: str, title: str, transcript: dict):
    """Save transcript to database and mark episode as transcribed."""
    db = get_database_manager()
    with db.get_session() as session:
        ep = session.query(EpisodeModel)\
            .filter(EpisodeModel.episode_guid == episode_guid).first()

        if not ep:
            logger.error(f"  Episode not found in database: {episode_guid}")
            return False

        source_type = "auto-generated" if transcript['is_generated'] else "manual"
        transcript_content = (
            f"# Complete Transcript\n"
            f"# Episode: {title}\n"
            f"# Source: YouTube transcript API ({video_id}, {source_type})\n"
            f"# Language: {transcript['language']}\n"
            f"# GUID: {episode_guid}\n"
            f"# Fetched: {datetime.now().isoformat()}\n"
            f"# Words: {transcript['word_count']:,}\n\n"
            + transcript['text']
        )

        ep.transcript_content = transcript_content
        ep.transcript_word_count = transcript['word_count']
        ep.transcript_generated_at = datetime.now(timezone.utc)
        ep.status = 'transcribed'
        ep.updated_at = datetime.now(timezone.utc)
        session.commit()

        return True


def main():
    parser = argparse.ArgumentParser(description='Fetch YouTube transcripts from Mac')
    parser.add_argument('-n', '--limit', type=int, default=5,
                        help='Max episodes to fetch (default: 5)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be fetched without doing it')
    parser.add_argument('--include-failed', action='store_true',
                        help='Also retry episodes in failed status')
    parser.add_argument('--include-zero-word', action='store_true',
                        help='Also retry episodes with 0-word transcripts (rescues bad not_relevant)')
    parser.add_argument('--base-delay', type=float, default=3.0,
                        help='Base delay in seconds (default: 3, escalates per request)')
    args = parser.parse_args()

    logger.info(f"YouTube Transcript Fetcher (Mac-side)")
    logger.info(f"Batch size: {args.limit}, base delay: {args.base_delay}s (escalating)")

    # Get pending YouTube episodes
    episodes = get_pending_youtube_episodes(args.limit, include_failed=args.include_failed,
                                              include_zero_word=args.include_zero_word)

    if not episodes:
        logger.info("No pending YouTube episodes found.")
        return

    logger.info(f"Found {len(episodes)} pending YouTube episode(s):")
    for ep in episodes:
        logger.info(f"  - {ep['title'][:60]}  [{ep['video_id']}]")

    if args.dry_run:
        logger.info("Dry run - no transcripts fetched.")
        return

    # Fetch transcripts with random delays
    success = 0
    failed = 0

    for i, ep in enumerate(episodes):
        logger.info(f"\n[{i+1}/{len(episodes)}] {ep['title'][:60]}")
        logger.info(f"  Video: {ep['video_id']}")

        transcript = fetch_transcript(ep['video_id'])

        if transcript:
            saved = save_transcript(ep['guid'], ep['video_id'], ep['title'], transcript)
            if saved:
                logger.info(f"  Saved: {transcript['word_count']:,} words ({transcript['language']})")
                success += 1
            else:
                failed += 1
        else:
            failed += 1

        # Escalating delay: 3s, 3s, 10s, 30s, 60s, 120s, 120s, ...
        # Clamped to [3s, 120s] with jitter. Looks like a human, not a bot.
        if i < len(episodes) - 1:
            delay_schedule = [3, 3, 10, 30, 60, 120]
            base = delay_schedule[min(i, len(delay_schedule) - 1)]
            jitter = random.uniform(0.7, 1.3)
            delay = max(3.0, min(120.0, base * jitter))
            logger.info(f"  Waiting {delay:.0f}s before next request...")
            time.sleep(delay)

    logger.info(f"\nDone: {success} succeeded, {failed} failed out of {len(episodes)} attempted")


if __name__ == '__main__':
    main()
