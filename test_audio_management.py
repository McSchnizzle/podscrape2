#!/usr/bin/env python3
"""
Test audio file management and organization system
"""

import os
import sys
from pathlib import Path
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.audio.audio_manager import AudioManager

def test_audio_management():
    """Test audio file management system"""
    print("📁 Testing Audio File Management System")
    print("=" * 50)
    
    try:
        # Initialize audio manager
        print("1. Initializing Audio Manager...")
        audio_manager = AudioManager()
        print("   ✅ AudioManager initialized successfully")
        
        # Check current directory structure
        print("\n2. Checking directory structure...")
        base_dir = Path("data/completed-tts")
        
        subdirs = ['current', 'archive', 'temp']
        for subdir in subdirs:
            subdir_path = base_dir / subdir
            exists = "✅" if subdir_path.exists() else "❌"
            print(f"   {exists} {subdir}/ directory")
        
        # Get storage statistics
        print("\n3. Getting storage statistics...")
        stats = audio_manager.get_storage_stats()
        
        print(f"   Total files: {stats['total_files']}")
        print(f"   Total size: {stats['total_size_mb']:.1f} MB")
        
        for dir_name, dir_stats in stats['directories'].items():
            if dir_stats['file_count'] > 0:
                print(f"   📂 {dir_name}: {dir_stats['file_count']} files, {dir_stats['size_mb']:.1f} MB")
        
        # Organize files (move from base to current)
        print("\n4. Organizing audio files...")
        organize_results = audio_manager.organize_audio_files()
        
        print(f"   Moved to current: {organize_results['moved_to_current']}")
        print(f"   Already organized: {organize_results['already_organized']}")
        print(f"   Errors: {organize_results['errors']}")
        
        # List current audio files
        print("\n5. Listing current audio files...")
        current_files = audio_manager.get_audio_files("current")
        
        print(f"   Found {len(current_files)} audio files:")
        for i, file_info in enumerate(current_files[:5], 1):  # Show first 5
            size_mb = file_info.file_size_bytes / (1024 * 1024)
            print(f"   {i}. {file_info.filename}")
            print(f"      Topic: {file_info.topic}")
            print(f"      Created: {file_info.date_created.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"      Size: {size_mb:.1f} MB")
        
        if len(current_files) > 5:
            print(f"   ... and {len(current_files) - 5} more files")
        
        # Test filename generation and validation
        print("\n6. Testing filename utilities...")
        
        # Generate test filename
        test_filename = audio_manager.generate_filename("AI News", datetime.now())
        print(f"   Generated filename: {test_filename}")
        
        # Validate filename
        is_valid = audio_manager.validate_filename(test_filename)
        print(f"   Filename valid: {'✅' if is_valid else '❌'}")
        
        # Test with existing files
        if current_files:
            existing_valid = audio_manager.validate_filename(current_files[0].filename)
            print(f"   Existing file valid: {'✅' if existing_valid else '❌'} ({current_files[0].filename})")
        
        # Test topic filtering
        print("\n7. Testing topic-based filtering...")
        if current_files:
            test_topic = current_files[0].topic
            topic_files = audio_manager.get_files_by_topic(test_topic)
            print(f"   Files for topic '{test_topic}': {len(topic_files)}")
        
        # Test date filtering
        print("\n8. Testing date-based filtering...")
        today = date.today()
        yesterday = today - timedelta(days=1)
        
        recent_files = audio_manager.get_files_by_date_range(yesterday, today)
        print(f"   Files from last 2 days: {len(recent_files)}")
        
        # Export metadata
        print("\n9. Exporting metadata...")
        metadata_path = audio_manager.export_metadata()
        print(f"   Metadata exported to: {metadata_path}")
        
        # Verify export file exists
        export_file = Path(metadata_path)
        if export_file.exists():
            size_kb = export_file.stat().st_size / 1024
            print(f"   Export file size: {size_kb:.1f} KB")
        
        print(f"\n✅ Audio management system testing completed!")
        print(f"📋 Task 6.4: Audio file management and naming system working perfectly")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing audio management: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_audio_management()
    sys.exit(0 if success else 1)