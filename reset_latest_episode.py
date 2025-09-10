#!/usr/bin/env python3
"""
Reset the status of the most recent episode to allow reprocessing
for testing the Turbo v2.5 model improvements.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Set up environment
from dotenv import load_dotenv
load_dotenv()

from src.database.models import get_episode_repo
import sqlite3

def reset_latest_episode():
    """Reset the most recent episode status to 'pending' for reprocessing"""
    
    db_path = "data/database/digest.db"
    
    try:
        # Get most recent episode
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Find most recent episode that was processed
            cursor.execute("""
                SELECT id, title, episode_guid, status, published_date 
                FROM episodes 
                WHERE status IN ('transcribed', 'scored')
                ORDER BY published_date DESC 
                LIMIT 1
            """)
            
            episode = cursor.fetchone()
            
            if not episode:
                print("No processed episodes found to reset")
                return
                
            episode_id, title, guid, status, pub_date = episode
            print(f"Found recent episode:")
            print(f"  ID: {episode_id}")
            print(f"  Title: {title[:60]}...")
            print(f"  Status: {status}")
            print(f"  Published: {pub_date}")
            
            # Reset status to pending
            cursor.execute("UPDATE episodes SET status = 'pending' WHERE id = ?", (episode_id,))
            conn.commit()
            
            print(f"\n✅ Reset episode {episode_id} status to 'pending'")
            print("You can now run the pipeline to reprocess this episode with Turbo v2.5!")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    reset_latest_episode()