#!/usr/bin/env python3
"""
Sync MP3 Files with Digest Database Records
Creates digest records for MP3 files that don't have database entries,
and updates existing records with timestamps from MP3 filenames.
"""

import sys
import os
import re
import logging
from pathlib import Path
from datetime import datetime, date, UTC
from typing import Dict, List, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.database.models import get_digest_repo, Digest, DatabaseManager

logger = logging.getLogger(__name__)

def parse_mp3_filename(filename: str) -> Optional[Dict[str, str]]:
    """
    Parse MP3 filename to extract topic and timestamp.
    Expected format: Topic_Name_YYYYMMDD_HHMMSS.mp3
    """
    # Remove .mp3 extension
    name = filename.replace('.mp3', '')

    # Match pattern: topic_name_YYYYMMDD_HHMMSS
    pattern = r'^(.+)_(\d{8})_(\d{6})$'
    match = re.match(pattern, name)

    if match:
        topic_part, date_part, time_part = match.groups()

        # Convert underscores back to spaces in topic name
        topic = topic_part.replace('_', ' ')

        # Parse date and time
        try:
            date_obj = datetime.strptime(date_part, '%Y%m%d').date()
            time_obj = datetime.strptime(time_part, '%H%M%S').time()
            timestamp = datetime.combine(date_obj, time_obj, tzinfo=UTC)

            return {
                'topic': topic,
                'date': date_obj,
                'timestamp': timestamp,
                'original_filename': filename
            }
        except ValueError as e:
            logger.warning(f"Failed to parse date/time from {filename}: {e}")
            return None
    else:
        logger.warning(f"Filename {filename} doesn't match expected pattern")
        return None

def find_mp3_files(mp3_dir: Path) -> List[Path]:
    """Find all MP3 files in the completed TTS directory"""
    mp3_files = []

    if mp3_dir.exists():
        # Look in current directory and subdirectories
        for mp3_file in mp3_dir.rglob('*.mp3'):
            mp3_files.append(mp3_file)

    return mp3_files

def sync_digests_with_mp3s():
    """Sync digest database records with MP3 files"""
    logger.info("Starting MP3-digest synchronization...")

    # Initialize repositories
    digest_repo = get_digest_repo()

    # Find all MP3 files
    mp3_dir = Path('data/completed-tts')
    mp3_files = find_mp3_files(mp3_dir)

    logger.info(f"Found {len(mp3_files)} MP3 files in {mp3_dir}")

    parsed_files = []
    for mp3_file in mp3_files:
        parsed = parse_mp3_filename(mp3_file.name)
        if parsed:
            parsed['file_path'] = str(mp3_file)
            parsed_files.append(parsed)
        else:
            logger.warning(f"Skipping unparseable file: {mp3_file}")

    logger.info(f"Successfully parsed {len(parsed_files)} MP3 filenames")

    # Get all existing digests
    all_digests = {}
    try:
        # Get recent digests (last 30 days)
        from datetime import timedelta
        start_date = date.today() - timedelta(days=30)

        db_manager = DatabaseManager()
        with db_manager.get_session() as session:
            from src.database.sqlalchemy_models import Digest as DigestModel

            digest_models = session.query(DigestModel)\
                .filter(DigestModel.digest_date >= start_date)\
                .all()

            for model in digest_models:
                key = f"{model.topic}_{model.digest_date}_{model.digest_timestamp}"
                all_digests[key] = digest_repo._model_to_digest(model)

    except Exception as e:
        logger.error(f"Failed to load existing digests: {e}")
        return

    logger.info(f"Found {len(all_digests)} existing digest records")

    # Process each MP3 file
    created_count = 0
    updated_count = 0

    for file_info in parsed_files:
        topic = file_info['topic']
        digest_date = file_info['date']
        timestamp = file_info['timestamp']
        file_path = file_info['file_path']

        # Check if a digest record already exists for this exact MP3
        digest_key = f"{topic}_{digest_date}_{timestamp}"

        if digest_key in all_digests:
            # Update existing record if needed
            existing = all_digests[digest_key]
            if existing.mp3_path != file_path:
                try:
                    digest_repo.update_digest(existing.id, {'mp3_path': file_path})
                    updated_count += 1
                    logger.info(f"Updated digest {existing.id} with MP3 path: {file_path}")
                except Exception as e:
                    logger.error(f"Failed to update digest {existing.id}: {e}")
        else:
            # Create new digest record
            try:
                # Get MP3 metadata if possible
                duration_seconds = None
                try:
                    stat = os.stat(file_path)
                    file_size = stat.st_size
                    # Rough estimate: ~1 minute per MB for typical speech MP3
                    duration_seconds = max(60, int(file_size / (1024 * 1024) * 60))
                except:
                    duration_seconds = None

                new_digest = Digest(
                    topic=topic,
                    digest_date=digest_date,
                    digest_timestamp=timestamp,
                    mp3_path=file_path,
                    mp3_duration_seconds=duration_seconds,
                    mp3_title=f"{topic} Daily Digest - {digest_date.strftime('%B %d, %Y')}",
                    mp3_summary=f"Daily digest for {topic} from podcast episodes.",
                    episode_count=0,  # We don't know this for historical records
                    episode_ids=[],   # We don't know this for historical records
                    average_score=0.0  # We don't know this for historical records
                )

                digest_id = digest_repo.create(new_digest)
                created_count += 1
                logger.info(f"Created digest {digest_id} for MP3: {file_path}")

            except Exception as e:
                logger.error(f"Failed to create digest for {file_path}: {e}")

    logger.info(f"Synchronization complete!")
    logger.info(f"  Created: {created_count} new digest records")
    logger.info(f"  Updated: {updated_count} existing records")
    logger.info(f"  Total MP3 files processed: {len(parsed_files)}")

def main():
    """Main function"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    logger.info("MP3-Digest Synchronization Tool")

    try:
        sync_digests_with_mp3s()
        logger.info("✅ Synchronization completed successfully!")

    except Exception as e:
        logger.error(f"❌ Synchronization failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()