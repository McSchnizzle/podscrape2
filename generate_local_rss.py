#!/usr/bin/env python3
"""
Generate RSS XML file locally from existing digests
No GitHub upload required - creates local RSS for manual testing
"""

import os
import sys
from datetime import datetime, date
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Set up environment
from dotenv import load_dotenv
load_dotenv()

from src.database.models import get_digest_repo
from src.publishing.rss_generator import create_rss_generator, PodcastEpisode, PodcastMetadata

def create_local_episode(digest, mp3_path):
    """Create a PodcastEpisode from digest with local MP3 path"""
    # Use GitHub raw URL pattern for the MP3 file 
    repo = "McSchnizzle/podscrape2"
    date_str = digest.digest_date.isoformat()
    mp3_filename = Path(mp3_path).name
    
    # GitHub release asset URL pattern
    mp3_url = f"https://github.com/{repo}/releases/download/daily-{date_str}/{mp3_filename}"
    
    return PodcastEpisode(
        title=digest.mp3_title or f"Daily Digest: {digest.topic}",
        description=digest.mp3_summary or f"AI-curated digest for {digest.topic}",
        audio_url=mp3_url,
        pub_date=datetime.combine(digest.digest_date, datetime.min.time().replace(hour=12)),
        duration_seconds=digest.mp3_duration_seconds or 0,
        file_size=Path(mp3_path).stat().st_size if Path(mp3_path).exists() else 0,
        guid=f"digest-{date_str}-{digest.topic.lower().replace(' ', '-')}"
    )

def main():
    print("🎵 Generating RSS XML from existing digests...")
    
    # Get digest repo
    digest_repo = get_digest_repo()
    
    # Get recent digests with MP3 files
    recent_digests = digest_repo.get_recent_digests(days=30)
    print(f"Found {len(recent_digests)} total recent digests")
    
    # Filter for digests with MP3 files that exist
    valid_digests = []
    for digest in recent_digests:
        if digest.mp3_path:
            # Check both possible locations
            mp3_paths_to_check = [
                digest.mp3_path,  # Database path
                f"data/completed-tts/current/{Path(digest.mp3_path).name}"  # Current directory
            ]
            
            for mp3_path in mp3_paths_to_check:
                if Path(mp3_path).exists():
                    print(f"✅ {digest.topic} ({digest.digest_date}) -> {Path(mp3_path).name}")
                    valid_digests.append((digest, mp3_path))
                    break
            else:
                print(f"⚠️  {digest.topic} ({digest.digest_date}) -> MP3 not found")
    
    print(f"\n📻 Creating RSS feed with {len(valid_digests)} episodes...")
    
    # Create podcast metadata
    podcast_metadata = PodcastMetadata(
        title="Daily AI & Tech Digest",
        description="AI-curated daily digest of podcast conversations about artificial intelligence, technology trends, and digital innovation.",
        author="Paul Brown", 
        email="paul@paulrbrown.org",
        category="Technology",
        subcategory="Tech News",
        website_url="https://podcast.paulrbrown.org",
        copyright="© 2025 Paul Brown"
    )
    
    # Create RSS generator
    rss_generator = create_rss_generator(podcast_metadata)
    
    # Create episodes
    episodes = []
    for digest, mp3_path in valid_digests:
        episode = create_local_episode(digest, mp3_path)
        episodes.append(episode)
    
    # Generate RSS XML
    rss_xml = rss_generator.generate_rss_feed(episodes)
    
    # Write to file
    output_file = "daily-digest.xml"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(rss_xml)
    
    print(f"✅ RSS XML generated: {output_file}")
    print(f"📊 Episodes included: {len(episodes)}")
    print(f"📁 File size: {Path(output_file).stat().st_size:,} bytes")
    
    # Show preview
    print("\n📋 RSS Feed Preview:")
    lines = rss_xml.split('\n')
    for i, line in enumerate(lines[:20]):
        print(f"   {line}")
    if len(lines) > 20:
        print(f"   ... ({len(lines) - 20} more lines)")
    
    print(f"\n🚀 Ready to copy {output_file} to Vercel for testing!")

if __name__ == "__main__":
    main()
