#!/usr/bin/env python3
"""
RSS Timestamp Utilities
Provides functions to generate unique publication timestamps for same-day episodes
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import hashlib
import re
from pathlib import Path

# Pacific timezone offset
PACIFIC_TZ = timezone(timedelta(hours=-8))  # PST/PDT - simplified for now

def extract_timestamp_from_mp3_path(mp3_path: str) -> Optional[datetime]:
    """
    Extract timestamp from MP3 filename format: {topic}_{YYYYMMDD}_{HHMMSS}.mp3

    Args:
        mp3_path: Path to the MP3 file

    Returns:
        datetime object in Pacific timezone if found, None otherwise
    """
    if not mp3_path:
        return None

    filename = Path(mp3_path).stem  # Get filename without extension

    # Pattern: {topic}_{YYYYMMDD}_{HHMMSS}
    pattern = r'_(\d{8})_(\d{6})$'
    match = re.search(pattern, filename)

    if not match:
        return None

    date_str, time_str = match.groups()

    try:
        # Parse YYYYMMDD and HHMMSS
        year = int(date_str[:4])
        month = int(date_str[4:6])
        day = int(date_str[6:8])
        hour = int(time_str[:2])
        minute = int(time_str[2:4])
        second = int(time_str[4:6])

        # Create datetime in Pacific timezone
        return datetime(year, month, day, hour, minute, second, tzinfo=PACIFIC_TZ)

    except (ValueError, IndexError):
        return None

def generate_unique_pubdate(digest_date: str, topic: str, creation_time: datetime = None, mp3_path: str = None) -> datetime:
    """
    Generate unique publication timestamp for RSS episodes using actual MP3 creation time

    Args:
        digest_date: Date string in YYYY-MM-DD format
        topic: Topic name for the digest
        creation_time: Optional creation time for fallback uniqueness
        mp3_path: Path to MP3 file to extract actual creation timestamp

    Returns:
        Unique datetime with timezone info in Pacific timezone
    """
    # First, try to extract timestamp from MP3 filename
    if mp3_path:
        mp3_timestamp = extract_timestamp_from_mp3_path(mp3_path)
        if mp3_timestamp:
            return mp3_timestamp

    # Fallback: Use creation_time if provided
    if creation_time:
        # Ensure it has Pacific timezone
        if creation_time.tzinfo is None:
            creation_time = creation_time.replace(tzinfo=PACIFIC_TZ)
        return creation_time

    # Final fallback: Use topic-based time offsets (legacy behavior)
    base_date = datetime.fromisoformat(digest_date)

    # Topic-based time offsets in Pacific timezone for uniqueness
    topic_offsets = {
        "AI and Technology": 9,  # 9:00 AM Pacific
        "Social Movements and Community Organizing": 12,  # 12:00 PM Pacific
        "Psychedelics and Spirituality": 15,  # 3:00 PM Pacific
    }

    hour_offset = topic_offsets.get(topic, 11)  # Default to 11:00 AM Pacific

    # Create base publication time in Pacific timezone
    pub_datetime = base_date.replace(hour=hour_offset, minute=0, second=0, microsecond=0, tzinfo=PACIFIC_TZ)

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