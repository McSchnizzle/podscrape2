#!/usr/bin/env python3
"""
Phase 2 Fast Test: Quick validation of core functionality
Tests channel resolution only to avoid timeouts
"""

import sys
import os
from pathlib import Path

# Add src to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from src.youtube.channel_resolver import resolve_channel
from src.database.models import get_database_manager, get_channel_repo, Channel
from src.utils.logging_config import setup_logging

# Setup quiet logging
setup_logging(log_level='WARNING')

def test_channel_resolution_fast():
    """Quick test of channel resolution only"""
    print("🧪 Phase 2 Fast Test: Channel Resolution")
    print("=" * 50)
    
    test_channels = [
        "https://www.youtube.com/@mreflow",
        "https://www.youtube.com/@aiadvantage"
    ]
    
    results = []
    for i, channel_url in enumerate(test_channels, 1):
        print(f"\n{i}. Testing: {channel_url}")
        try:
            channel_info = resolve_channel(channel_url)
            if channel_info:
                print(f"   ✅ SUCCESS: {channel_info.channel_name}")
                print(f"   📋 Channel ID: {channel_info.channel_id}")
                if channel_info.subscriber_count:
                    print(f"   👥 Subscribers: {channel_info.subscriber_count:,}")
                results.append(channel_info)
            else:
                print(f"   ❌ FAILED: Could not resolve")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
    
    return results

def test_database_basic():
    """Quick database test"""
    print("\n🧪 Database Integration Test")
    print("=" * 30)
    
    # Use temporary database
    import tempfile
    test_db_path = os.path.join(tempfile.gettempdir(), 'test_phase2_fast.db')
    
    try:
        db_manager = get_database_manager(test_db_path)
        channel_repo = get_channel_repo(db_manager)
        
        # Test adding a channel
        test_channel = Channel(
            channel_id='UC_test_123',
            channel_name='Test Channel',
            channel_url='https://www.youtube.com/channel/UC_test_123',
            active=True
        )
        
        channel_id = channel_repo.create(test_channel)
        print(f"✅ Added test channel with ID: {channel_id}")
        
        # Test retrieval
        retrieved = channel_repo.get_by_id('UC_test_123')
        if retrieved:
            print(f"✅ Retrieved channel: {retrieved.channel_name}")
        else:
            print("❌ Failed to retrieve channel")
        
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False
    finally:
        # Clean up test database
        if os.path.exists(test_db_path):
            os.remove(test_db_path)

def main():
    """Run fast Phase 2 tests"""
    print("🚀 Phase 2 Fast Test Suite")
    print("Testing core functionality without timeouts")
    print("=" * 50)
    
    # Test 1: Channel resolution (should be fast)
    channels = test_channel_resolution_fast()
    
    # Test 2: Basic database operations
    db_success = test_database_basic()
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Fast Test Results:")
    print(f"✅ Channel resolution: {len(channels)}/2 channels resolved")
    print(f"✅ Database operations: {'PASSED' if db_success else 'FAILED'}")
    
    if len(channels) >= 1 and db_success:
        print("\n🎉 Phase 2 core functionality is working!")
        print("Ready for comprehensive testing")
        return True
    else:
        print("\n⚠️ Some tests failed - need investigation")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)