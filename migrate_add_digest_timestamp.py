#!/usr/bin/env python3
"""
Database migration to add digest_timestamp column to digests table.
This allows multiple digests per topic per day with unique timestamps.
"""

import sys
import logging
from pathlib import Path
from datetime import datetime, UTC

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.config.env import require_database_url
from src.database.models import DatabaseManager
from sqlalchemy import text

logger = logging.getLogger(__name__)

def main():
    """Run the migration to add digest_timestamp column"""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    logger.info("Starting digest_timestamp migration...")

    try:
        # Get database manager
        db_manager = DatabaseManager()

        with db_manager.get_session() as session:
            try:
                # Check if column already exists
                result = session.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'digests' AND column_name = 'digest_timestamp'
                """))

                if result.fetchone():
                    logger.info("digest_timestamp column already exists, skipping migration")
                    return

                # Add the new column
                logger.info("Adding digest_timestamp column...")
                session.execute(text("""
                    ALTER TABLE digests
                    ADD COLUMN digest_timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
                """))

                # Drop the old unique constraint
                logger.info("Dropping old unique constraint...")
                session.execute(text("""
                    ALTER TABLE digests
                    DROP CONSTRAINT IF EXISTS uq_digests_topic_date
                """))

                # Add the new unique constraint with timestamp
                logger.info("Adding new unique constraint with timestamp...")
                session.execute(text("""
                    ALTER TABLE digests
                    ADD CONSTRAINT uq_digests_topic_date_timestamp
                    UNIQUE (topic, digest_date, digest_timestamp)
                """))

                # Add index for timestamp queries
                logger.info("Adding index for digest_timestamp...")
                session.execute(text("""
                    CREATE INDEX IF NOT EXISTS ix_digests_timestamp
                    ON digests (digest_timestamp)
                """))

                # Update existing records to have unique timestamps
                logger.info("Updating existing records with unique timestamps...")
                result = session.execute(text("""
                    SELECT id, topic, digest_date, generated_at
                    FROM digests
                    ORDER BY id
                """))

                records = result.fetchall()
                for i, record in enumerate(records):
                    # Use generated_at if available, otherwise create incremental timestamp
                    if record.generated_at:
                        timestamp = record.generated_at
                    else:
                        # Create unique timestamps by adding seconds to current time
                        timestamp = datetime.now(UTC).replace(second=i % 60, microsecond=i * 1000)

                    session.execute(text("""
                        UPDATE digests
                        SET digest_timestamp = :timestamp
                        WHERE id = :id
                    """), {"timestamp": timestamp, "id": record.id})

                session.commit()
                logger.info(f"Successfully migrated {len(records)} digest records")
                logger.info("Migration completed successfully!")

            except Exception as e:
                session.rollback()
                logger.error(f"Migration failed: {e}")
                raise

    except Exception as e:
        logger.error(f"Migration error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()