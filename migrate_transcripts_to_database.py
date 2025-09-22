#!/usr/bin/env python3
"""
Data Migration Script: Populate transcript_content from existing transcript files

This script reads all existing transcript files from data/transcripts/ and
data/transcripts/digested/ directories and populates the transcript_content
column in the database for episodes that have transcript_path but no transcript_content.

Usage:
    python3 migrate_transcripts_to_database.py [--dry-run] [--limit N] [--verbose]
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from typing import List, Tuple, Optional

# Add src to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

# Set up environment
from dotenv import load_dotenv
load_dotenv()

from src.config.env import require_database_url
from src.database.models import get_episode_repo

def setup_logging(verbose: bool = False) -> logging.Logger:
    """Set up logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)

def find_all_transcript_files() -> List[Path]:
    """Find all transcript files in data/transcripts/ and data/transcripts/digested/"""
    transcript_files = []

    # Search in data/transcripts/
    transcripts_dir = Path("data/transcripts")
    if transcripts_dir.exists():
        for file_path in transcripts_dir.glob("*.txt"):
            if file_path.is_file():
                transcript_files.append(file_path)

    # Search in data/transcripts/digested/
    digested_dir = Path("data/transcripts/digested")
    if digested_dir.exists():
        for file_path in digested_dir.glob("*.txt"):
            if file_path.is_file():
                transcript_files.append(file_path)

    return transcript_files

def read_transcript_content(file_path: Path) -> Optional[str]:
    """Read transcript content from file, handling encoding issues"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except Exception as e:
        logging.error(f"Failed to read {file_path}: {e}")
        return None

def extract_metadata_from_transcript(content: str) -> Tuple[Optional[str], int, int]:
    """Extract GUID, word count, and character count from transcript content"""
    guid = None
    words = 0
    chars = len(content)

    lines = content.split('\n')
    for line in lines:
        if line.startswith('# GUID: '):
            guid = line.replace('# GUID: ', '').strip()
        elif line.startswith('# Words: '):
            try:
                words = int(line.replace('# Words: ', '').strip().replace(',', ''))
            except (ValueError, AttributeError):
                pass

    # Fallback: count words in content
    if words == 0:
        # Remove header lines and count words in actual content
        content_lines = [line for line in lines if not line.startswith('#')]
        content_text = '\n'.join(content_lines).strip()
        if content_text:
            words = len(content_text.split())

    return guid, words, chars

def migrate_transcript_to_database(episode_repo, episode_guid: str, transcript_content: str,
                                 word_count: int, dry_run: bool = False) -> bool:
    """Migrate transcript content to database for a specific episode"""
    try:
        if dry_run:
            logging.info(f"DRY RUN: Would update episode {episode_guid} with {word_count:,} words")
            return True

        # Get existing episode
        episode = episode_repo.get_by_episode_guid(episode_guid)
        if not episode:
            logging.warning(f"Episode {episode_guid} not found in database")
            return False

        # Check if transcript_content is already populated
        if episode.transcript_content:
            logging.debug(f"Episode {episode_guid} already has transcript_content, skipping")
            return True

        # Update only the transcript_content field (keep existing transcript_path)
        episode_repo.update_transcript(
            episode_guid=episode_guid,
            transcript_path=episode.transcript_path,  # Keep existing path
            word_count=episode.transcript_word_count or word_count,  # Keep existing or use calculated
            transcript_content=transcript_content  # Add the content
        )

        logging.info(f"✓ Updated episode {episode_guid} with {word_count:,} words of transcript content")
        return True

    except Exception as e:
        logging.error(f"Failed to update episode {episode_guid}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Migrate transcript files to database')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be migrated without making changes')
    parser.add_argument('--limit', type=int, help='Limit number of files to process')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')

    args = parser.parse_args()

    logger = setup_logging(args.verbose)

    try:
        # Validate database connection
        require_database_url()
        logger.info("✓ Database connection validated")

        # Initialize repository
        episode_repo = get_episode_repo()
        logger.info("✓ Episode repository initialized")

        # Find all transcript files
        transcript_files = find_all_transcript_files()
        logger.info(f"Found {len(transcript_files)} transcript files")

        if not transcript_files:
            logger.warning("No transcript files found in data/transcripts/ or data/transcripts/digested/")
            return 0

        # Apply limit if specified
        if args.limit:
            transcript_files = transcript_files[:args.limit]
            logger.info(f"Limited to {len(transcript_files)} files")

        # Process each file
        processed = 0
        failed = 0
        skipped = 0

        for i, file_path in enumerate(transcript_files, 1):
            logger.info(f"\n[{i}/{len(transcript_files)}] Processing: {file_path}")

            # Read transcript content
            content = read_transcript_content(file_path)
            if not content:
                failed += 1
                continue

            # Extract metadata
            guid, word_count, char_count = extract_metadata_from_transcript(content)

            if not guid:
                logger.warning(f"No GUID found in {file_path}, skipping")
                skipped += 1
                continue

            logger.info(f"  GUID: {guid}")
            logger.info(f"  Words: {word_count:,}")
            logger.info(f"  Characters: {char_count:,}")

            # Migrate to database
            success = migrate_transcript_to_database(
                episode_repo, guid, content, word_count, args.dry_run
            )

            if success:
                processed += 1
            else:
                failed += 1

        # Summary
        logger.info(f"\n" + "="*60)
        logger.info(f"Migration Summary:")
        logger.info(f"  Total files found: {len(transcript_files)}")
        logger.info(f"  Successfully processed: {processed}")
        logger.info(f"  Failed: {failed}")
        logger.info(f"  Skipped: {skipped}")

        if args.dry_run:
            logger.info(f"  DRY RUN: No changes made to database")
        else:
            logger.info(f"  ✅ Migration completed successfully")

        return 0 if failed == 0 else 1

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())