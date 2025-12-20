#!/usr/bin/env python3
"""
Migrate transcript files to database.
This script reads transcript files from data/transcripts/ and updates the database with the content.
"""

import logging
import sys
from pathlib import Path
from typing import List, Tuple

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.database.models import get_episode_repo

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def find_transcript_files() -> List[Path]:
    """Find all transcript files in data/transcripts/ directory."""
    transcript_dir = Path('data/transcripts')
    if not transcript_dir.exists():
        logger.warning(f"Transcript directory {transcript_dir} does not exist")
        return []

    transcript_files = []
    # Find all .txt files including in subdirectories
    for txt_file in transcript_dir.rglob("*.txt"):
        transcript_files.append(txt_file)

    logger.info(f"Found {len(transcript_files)} transcript files")
    return transcript_files

def extract_guid_from_filename(filename: str) -> str:
    """Extract episode GUID from transcript filename."""
    # Remove .txt extension and any prefix
    base_name = filename.replace('.txt', '')

    # Handle various filename patterns:
    # the-14677f.txt -> 14677f (remove prefix)
    # podcast-a2b7b9.txt -> a2b7b9
    # episode_guid.txt -> episode_guid

    if '-' in base_name:
        parts = base_name.split('-')
        # Take the last part as it's likely the GUID portion
        guid_part = parts[-1]
    else:
        guid_part = base_name

    return guid_part

def find_episode_by_guid_fragment(episode_repo, guid_fragment: str):
    """Find episode by GUID fragment since filenames are truncated."""
    # Search through episodes with different statuses to find the GUID fragment
    status_groups = [
        ['transcribed', 'scored', 'digested'],  # Primary statuses
        ['discovered', 'downloaded', 'failed'],  # Other statuses
    ]

    for statuses in status_groups:
        try:
            episodes = episode_repo.get_by_status_list(statuses)
            for episode in episodes:
                if guid_fragment.lower() in episode.guid.lower():
                    return episode
        except Exception as e:
            logger.debug(f"Error searching episodes with statuses {statuses}: {e}")
            continue

    return None

def migrate_transcripts() -> Tuple[int, int]:
    """Migrate transcript files to database.

    Returns:
        Tuple of (migrated_count, failed_count)
    """
    episode_repo = get_episode_repo()
    transcript_files = find_transcript_files()

    if not transcript_files:
        logger.info("No transcript files found to migrate")
        return 0, 0

    migrated = 0
    failed = 0

    for transcript_file in transcript_files:
        try:
            logger.info(f"Processing: {transcript_file}")

            # Extract GUID fragment from filename
            guid_fragment = extract_guid_from_filename(transcript_file.name)
            logger.debug(f"Extracted GUID fragment: {guid_fragment}")

            # Find episode by GUID fragment
            episode = find_episode_by_guid_fragment(episode_repo, guid_fragment)
            if not episode:
                logger.warning(f"No episode found for GUID fragment: {guid_fragment} (file: {transcript_file.name})")
                failed += 1
                continue

            # Read transcript content
            try:
                with open(transcript_file, 'r', encoding='utf-8') as f:
                    transcript_content = f.read().strip()
            except Exception as e:
                logger.error(f"Failed to read {transcript_file}: {e}")
                failed += 1
                continue

            if not transcript_content:
                logger.warning(f"Empty transcript file: {transcript_file}")
                failed += 1
                continue

            # Check if episode already has transcript content in database
            if episode.transcript_content and episode.transcript_content.strip():
                logger.info(f"Episode {episode.title[:50]} already has transcript in database - skipping")
                continue

            # Update episode with transcript content
            episode_repo.update_transcript_content(episode.id, transcript_content)
            logger.info(f"✅ Migrated transcript for: {episode.title[:50]} ({len(transcript_content)} chars)")
            migrated += 1

        except Exception as e:
            logger.error(f"Failed to process {transcript_file}: {e}")
            failed += 1

    return migrated, failed

def main():
    """Main migration function."""
    logger.info("Starting transcript migration to database...")

    try:
        migrated, failed = migrate_transcripts()

        logger.info("=" * 60)
        logger.info("TRANSCRIPT MIGRATION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"✅ Successfully migrated: {migrated} transcripts")
        logger.info(f"❌ Failed to migrate: {failed} transcripts")

        if failed > 0:
            logger.warning("Some transcripts failed to migrate. Check logs above for details.")
            return 1
        else:
            logger.info("All transcripts migrated successfully!")
            return 0

    except Exception as e:
        logger.error(f"Migration failed with error: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)