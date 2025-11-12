#!/usr/bin/env python3
"""
Backfill database digest records for November 11, 2025 MP3s from GitHub release.

This script:
1. Lists MP3 assets in the daily-2025-11-11 GitHub release
2. Parses filenames to extract topic and timestamp
3. Creates digest database records with GitHub URLs
4. Marks them as 'published' so they appear in RSS feed
"""

import os
import sys
import json
import subprocess
from datetime import datetime, timezone, date
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.database.models import DatabaseManager
from src.database.sqlalchemy_models import Digest


def parse_mp3_filename(filename: str) -> dict:
    """
    Parse MP3 filename to extract metadata.

    Format: Topic_Name_YYYYMMDD_HHMMSS.mp3
    Example: AI_and_Technology_20251111_000602.mp3
    """
    # Remove .mp3 extension
    base = filename.replace('.mp3', '')

    # Split by underscore
    parts = base.split('_')

    # Last part is HHMMSS, second-to-last is YYYYMMDD
    time_str = parts[-1]
    date_str = parts[-2]

    # Everything before date is topic (with underscores)
    topic_parts = parts[:-2]
    topic = ' '.join(topic_parts)

    # Parse date and time
    year = int(date_str[0:4])
    month = int(date_str[4:6])
    day = int(date_str[6:8])

    hour = int(time_str[0:2])
    minute = int(time_str[2:4])
    second = int(time_str[4:6])

    digest_date = date(year, month, day)
    digest_timestamp = datetime(year, month, day, hour, minute, second)

    return {
        'topic': topic,
        'digest_date': digest_date,
        'digest_timestamp': digest_timestamp,
        'filename': filename
    }


def get_github_release_assets(release_tag: str) -> list:
    """Get list of MP3 assets from GitHub release."""
    repo = os.environ.get('GITHUB_REPOSITORY', 'McSchnizzle/podscrape2')

    try:
        result = subprocess.run(
            ['gh', 'release', 'view', release_tag, '--repo', repo, '--json', 'assets'],
            capture_output=True,
            text=True,
            check=True
        )

        data = json.loads(result.stdout)
        assets = data.get('assets', [])

        # Filter to MP3 files only
        mp3_assets = [a for a in assets if a['name'].endswith('.mp3')]

        return mp3_assets

    except subprocess.CalledProcessError as e:
        print(f"Error fetching release assets: {e}")
        print(f"stderr: {e.stderr}")
        return []


def generate_title_and_summary(topic: str, digest_date: date) -> tuple[str, str]:
    """Generate title and summary for digest."""
    title = f"{topic} Digest - {digest_date.strftime('%B %d, %Y')}"
    summary = f"AI-curated daily digest for {topic} from {digest_date.strftime('%B %d, %Y')}. Insights from leading podcasts on {topic.lower()}."

    return title, summary


def create_digest_record(asset: dict, parsed: dict, repo: str) -> Digest:
    """Create a digest database record from GitHub asset."""
    topic = parsed['topic']
    digest_date = parsed['digest_date']
    digest_timestamp = parsed['digest_timestamp']
    filename = parsed['filename']

    # Generate GitHub download URL
    release_tag = f"daily-{digest_date.strftime('%Y-%m-%d')}"
    github_url = f"https://github.com/{repo}/releases/download/{release_tag}/{filename}"

    # Generate title and summary
    mp3_title, mp3_summary = generate_title_and_summary(topic, digest_date)

    # Create digest record
    digest = Digest(
        topic=topic,
        digest_date=digest_date,
        digest_timestamp=digest_timestamp,
        mp3_path=f"data/completed-tts/{filename}",  # Path for reference (file doesn't exist locally)
        mp3_title=mp3_title,
        mp3_summary=mp3_summary,
        mp3_duration_seconds=None,  # Unknown, will be filled if we re-process
        github_url=github_url,
        published_at=datetime.now(timezone.utc),
        generated_at=digest_timestamp,  # Use timestamp from filename
        status='published',
        episode_count=0,  # Unknown, these were generated outside normal pipeline
        episode_ids=None,
        script_content=None,  # Not available
        script_word_count=None
    )

    return digest


def main():
    """Main execution."""
    print("=" * 80)
    print("Backfill November 11, 2025 Digest Records")
    print("=" * 80)

    release_tag = "daily-2025-11-11"
    repo = os.environ.get('GITHUB_REPOSITORY', 'McSchnizzle/podscrape2')

    print(f"\n📦 Fetching assets from GitHub release: {release_tag}")
    assets = get_github_release_assets(release_tag)

    if not assets:
        print("❌ No MP3 assets found in release")
        return 1

    print(f"✓ Found {len(assets)} MP3 files:")
    for asset in assets:
        print(f"  - {asset['name']}")

    print(f"\n📝 Parsing filenames and creating digest records...")

    db = DatabaseManager()
    session = db.get_session()

    created_count = 0
    skipped_count = 0

    try:
        for asset in assets:
            filename = asset['name']

            # Parse filename
            try:
                parsed = parse_mp3_filename(filename)
            except Exception as e:
                print(f"⚠️  Failed to parse filename '{filename}': {e}")
                continue

            # Check if digest already exists
            existing = session.query(Digest).filter(
                Digest.topic == parsed['topic'],
                Digest.digest_date == parsed['digest_date'],
                Digest.digest_timestamp == parsed['digest_timestamp']
            ).first()

            if existing:
                print(f"⏭️  Skipping {parsed['topic']} (already exists in database)")
                skipped_count += 1
                continue

            # Create digest record
            digest = create_digest_record(asset, parsed, repo)
            session.add(digest)

            print(f"✅ Created: {digest.topic} - {digest.digest_timestamp}")
            created_count += 1

        # Commit all changes
        session.commit()

        print(f"\n" + "=" * 80)
        print(f"✅ Backfill Complete!")
        print(f"=" * 80)
        print(f"Created: {created_count} digest records")
        print(f"Skipped: {skipped_count} existing records")
        print(f"\n📡 The RSS feed will now include these episodes:")
        print(f"   https://podcast.paulrbrown.org/daily-digest.xml")
        print(f"\n💡 RSS feed has 5-minute cache, so changes may take up to 5 minutes to appear")

        return 0

    except Exception as e:
        session.rollback()
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        session.close()


if __name__ == '__main__':
    sys.exit(main())
