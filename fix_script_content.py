#!/usr/bin/env python3
"""
Fix script_content in existing digests by reading from script files.
This is a one-time migration script to populate the script_content field
for digests that have script_path but missing script_content.
"""

from pathlib import Path
import sys

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.database.models import get_digest_repo

def main():
    digest_repo = get_digest_repo()
    
    # Get all digests pending TTS (these need script_content)
    pending_digests = digest_repo.get_digests_pending_tts()
    
    print(f"Found {len(pending_digests)} digests pending TTS")
    
    fixed_count = 0
    failed_count = 0
    
    for digest in pending_digests:
        if digest.script_content:
            print(f"Digest {digest.id} already has script_content, skipping")
            continue
            
        if not digest.script_path:
            print(f"Digest {digest.id} has no script_path, skipping")
            continue
            
        script_path = Path(digest.script_path)
        if not script_path.exists():
            print(f"Script file not found for digest {digest.id}: {script_path}")
            failed_count += 1
            continue
            
        try:
            # Read the script content from file
            with open(script_path, 'r', encoding='utf-8') as f:
                script_content = f.read()
            
            # Update the digest with script_content
            digest_repo.update_script(
                digest_id=digest.id,
                script_path=str(script_path),
                word_count=digest.script_word_count or len(script_content.split()),
                script_content=script_content
            )
            
            print(f"✅ Fixed digest {digest.id} ({digest.topic}): {len(script_content)} characters")
            fixed_count += 1
            
        except Exception as e:
            print(f"❌ Failed to fix digest {digest.id}: {e}")
            failed_count += 1
    
    print(f"\nSummary:")
    print(f"  Fixed: {fixed_count} digests")
    print(f"  Failed: {failed_count} digests")
    print(f"  Total: {len(pending_digests)} digests")

if __name__ == "__main__":
    main()