#!/usr/bin/env python3
"""
Phase 7 Database Migration
Adds publishing-related columns to the digests table
"""

import sys
import logging
from pathlib import Path

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from database.models import get_database_manager

def migrate_database(db_path: str = None):
    """
    Apply Phase 7 database migrations
    Adds github_release_id and rss_published_at columns to digests table
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Get database manager
        db_manager = get_database_manager(db_path)
        
        logger.info(f"Applying Phase 7 migrations to: {db_manager.db_path}")
        
        with db_manager.get_connection() as conn:
            # Check if columns already exist
            cursor = conn.execute("PRAGMA table_info(digests)")
            columns = [row[1] for row in cursor.fetchall()]
            
            migrations_needed = []
            
            if 'github_release_id' not in columns:
                migrations_needed.append("ALTER TABLE digests ADD COLUMN github_release_id TEXT")
                logger.info("Will add github_release_id column")
            
            if 'rss_published_at' not in columns:
                migrations_needed.append("ALTER TABLE digests ADD COLUMN rss_published_at DATETIME")
                logger.info("Will add rss_published_at column")
            
            if not migrations_needed:
                logger.info("No migrations needed - database already up to date")
                return True
            
            # Apply migrations
            for migration in migrations_needed:
                logger.info(f"Executing: {migration}")
                conn.execute(migration)
            
            # Update schema version
            conn.execute(
                "INSERT OR REPLACE INTO system_metadata (key, value) VALUES (?, ?)",
                ('schema_version', '1.1')
            )
            conn.execute(
                "INSERT OR REPLACE INTO system_metadata (key, value) VALUES (?, ?)",
                ('last_migration', 'phase7')
            )
            
            conn.commit()
            logger.info("✅ Phase 7 migrations applied successfully!")
            return True
            
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Apply Phase 7 Database Migrations")
    parser.add_argument("--db-path", help="Custom database path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run migration
    if migrate_database(args.db_path):
        print("✅ Database migration completed successfully!")
    else:
        print("❌ Database migration failed!")
        sys.exit(1)