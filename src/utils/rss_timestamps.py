#!/usr/bin/env python3
"""
RSS Timestamp Utilities
Provides functions to generate unique publication timestamps for same-day episodes
"""

from datetime import datetime, timedelta
from typing import Dict, List
import hashlib

# Topic-based time offsets to ensure unique timestamps
# Maps topic names to hour offsets from midnight UTC
TOPIC_TIME_OFFSETS = {
    "AI and Technology": 10,  # 10:00 AM UTC
    "Social Movements and Community Organizing": 14,  # 2:00 PM UTC
    "Psychedelics and Spirituality": 16,  # 4:00 PM UTC
}

def generate_unique_pubdate(digest_date: str, topic: str, creation_time: datetime = None) -> datetime:
    """
    Generate unique publication timestamp for RSS episodes

    Args:
        digest_date: Date string in YYYY-MM-DD format
        topic: Topic name for the digest
        creation_time: Optional creation time for fallback uniqueness

    Returns:
        Unique datetime with timezone info
    """
    # Parse base date
    base_date = datetime.fromisoformat(digest_date)

    # Get topic-specific hour offset
    hour_offset = TOPIC_TIME_OFFSETS.get(topic, 12)  # Default to noon

    # Create base publication time
    pub_datetime = base_date.replace(hour=hour_offset, minute=0, second=0, microsecond=0)

    # If creation_time is provided, add minute offset based on creation time
    # This provides additional uniqueness for topics published close together
    if creation_time:
        # Use hash of topic + creation time to generate consistent minute offset
        hash_input = f"{topic}:{creation_time.isoformat()}"
        hash_digest = hashlib.md5(hash_input.encode()).hexdigest()
        minute_offset = int(hash_digest[:2], 16) % 60  # 0-59 minutes
        pub_datetime = pub_datetime.replace(minute=minute_offset)

    return pub_datetime

def get_topic_publication_times() -> Dict[str, int]:
    """
    Get the publication hour for each topic

    Returns:
        Dictionary mapping topic names to publication hours (0-23)
    """
    return TOPIC_TIME_OFFSETS.copy()

def add_topic_time_offset(topic: str, hour: int) -> None:
    """
    Add or update time offset for a topic

    Args:
        topic: Topic name
        hour: Publication hour (0-23)
    """
    if not 0 <= hour <= 23:
        raise ValueError("Hour must be between 0-23")

    TOPIC_TIME_OFFSETS[topic] = hour

def validate_unique_timestamps(episodes: List[Dict]) -> List[str]:
    """
    Validate that episode timestamps are unique

    Args:
        episodes: List of episode dictionaries with pub_date field

    Returns:
        List of warnings about duplicate timestamps
    """
    timestamps = {}
    warnings = []

    for episode in episodes:
        pub_date = episode.get('pub_date')
        if not pub_date:
            continue

        timestamp_str = pub_date.isoformat()

        if timestamp_str in timestamps:
            warnings.append(
                f"Duplicate timestamp {timestamp_str}: "
                f"{timestamps[timestamp_str]} and {episode.get('title', 'Unknown')}"
            )
        else:
            timestamps[timestamp_str] = episode.get('title', 'Unknown')

    return warnings

# CLI testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='RSS Timestamp Utilities')
    parser.add_argument('--test-timestamps', action='store_true',
                       help='Test timestamp generation')
    parser.add_argument('--date', default='2025-09-15',
                       help='Test date (YYYY-MM-DD)')

    args = parser.parse_args()

    if args.test_timestamps:
        print(f"Testing timestamp generation for {args.date}")
        print("-" * 50)

        topics = ["AI and Technology", "Social Movements and Community Organizing", "Psychedelics and Spirituality"]
        creation_time = datetime.now()

        for topic in topics:
            pub_date = generate_unique_pubdate(args.date, topic, creation_time)
            print(f"{topic:40} -> {pub_date.strftime('%a, %d %b %Y %H:%M:%S %z')}")

        print("\nTopic time offsets:")
        for topic, hour in get_topic_publication_times().items():
            print(f"  {topic}: {hour:02d}:00 UTC")