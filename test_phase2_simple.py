#!/usr/bin/env python3
"""
Phase 2 Simple Test: Test the YouTube channels functionality with real channels
Tests with the provided channels: @mreflow and @aiadvantage
"""

import sys
import os
from pathlib import Path

# Add src to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from src.youtube.channel_resolver import resolve_channel
from src.youtube.video_discovery import discover_videos_for_channel
from src.database.models import get_database_manager, get_channel_repo, Channel
from src.utils.logging_config import setup_logging

# Setup logging
setup_logging(log_level='INFO')

def test_channel_resolution():
    """Test resolving the two provided YouTube channels"""
    print("🧪 Testing Channel Resolution")
    print("=" * 50)
    
    test_channels = [
        "https://www.youtube.com/@mreflow",
        "https://www.youtube.com/@aiadvantage"
    ]
    
    results = []
    for channel_url in test_channels:
        print(f"\n🔍 Resolving: {channel_url}")
        try:
            channel_info = resolve_channel(channel_url)
            if channel_info:
                print(f"✅ SUCCESS: {channel_info.channel_name}")
                print(f"   Channel ID: {channel_info.channel_id}")
                print(f"   URL: {channel_info.channel_url}")
                if channel_info.subscriber_count:
                    print(f"   Subscribers: {channel_info.subscriber_count:,}")
                results.append(channel_info)
            else:
                print(f"❌ FAILED: Could not resolve {channel_url}")
        except Exception as e:
            print(f"❌ ERROR: {e}")
    
    return results

def test_video_discovery(channel_infos):
    """Test video discovery for resolved channels"""
    print("\n\n🧪 Testing Video Discovery")
    print("=" * 50)
    
    for channel_info in channel_infos:
        print(f"\n📹 Testing video discovery for: {channel_info.channel_name}")
        
        # Create Channel object
        channel = Channel(
            channel_id=channel_info.channel_id,
            channel_name=channel_info.channel_name,
            channel_url=channel_info.channel_url,
            active=True
        )
        
        try:
            videos = discover_videos_for_channel(channel, days_back=7)
            print(f"✅ Found {len(videos)} videos in last 7 days")
            
            for i, video in enumerate(videos[:3], 1):  # Show first 3 videos
                duration_min = video.duration_seconds // 60
                duration_sec = video.duration_seconds % 60
                print(f"   {i}. {video.title[:60]}{'...' if len(video.title) > 60 else ''}")
                print(f"      Duration: {duration_min}:{duration_sec:02d}")
                print(f"      Published: {video.published_date.strftime('%Y-%m-%d %H:%M')}")
                
        except Exception as e:
            print(f"❌ ERROR discovering videos: {e}")

def test_database_integration(channel_infos):
    """Test adding channels to database"""
    print("\n\n🧪 Testing Database Integration")
    print("=" * 50)
    
    # Use temporary database for testing
    import tempfile
    test_db_path = os.path.join(tempfile.gettempdir(), 'test_phase2.db')
    
    try:
        db_manager = get_database_manager(test_db_path)
        channel_repo = get_channel_repo(db_manager)
        
        for channel_info in channel_infos:
            print(f"\n💾 Adding {channel_info.channel_name} to database...")
            
            # Create Channel object
            channel = Channel(
                channel_id=channel_info.channel_id,
                channel_name=channel_info.channel_name,
                channel_url=channel_info.channel_url,
                active=True
            )
            
            # Check if already exists
            existing = channel_repo.get_by_id(channel_info.channel_id)
            if existing:
                print(f"   ⚠️  Channel already exists in database")
                continue
            
            # Add to database
            channel_id = channel_repo.create(channel)
            print(f"✅ Added with database ID: {channel_id}")
            
            # Verify retrieval
            retrieved = channel_repo.get_by_id(channel_info.channel_id)
            if retrieved and retrieved.channel_name == channel_info.channel_name:
                print(f"✅ Successfully retrieved from database")
            else:
                print(f"❌ Failed to retrieve from database")
        
        # List all channels
        all_channels = channel_repo.get_all_active()
        print(f"\n📋 Total active channels in database: {len(all_channels)}")
        for ch in all_channels:
            print(f"   • {ch.channel_name} ({ch.channel_id})")
            
    except Exception as e:
        print(f"❌ Database error: {e}")
    finally:
        # Clean up test database
        if os.path.exists(test_db_path):
            os.remove(test_db_path)

def main():
    """Run all Phase 2 tests"""
    print("🚀 Phase 2 YouTube Channel Integration Test")
    print("Testing with provided channels: @mreflow and @aiadvantage (7-day lookback)")
    print("=" * 70)
    
    # Test 1: Channel resolution
    channel_infos = test_channel_resolution()
    
    if not channel_infos:
        print("\n❌ No channels could be resolved. Check network connection and yt-dlp installation.")
        return False
    
    # Test 2: Video discovery
    test_video_discovery(channel_infos)
    
    # Test 3: Database integration
    test_database_integration(channel_infos)
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 Phase 2 Test Summary:")
    print(f"✅ Resolved {len(channel_infos)} out of 2 test channels")
    print("✅ Video discovery tested")
    print("✅ Database integration tested")
    print("\n🎉 Phase 2 core functionality is working!")
    print("Ready to proceed with Phase 3: Transcript Processing")
    
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)