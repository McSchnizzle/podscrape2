#!/usr/bin/env python3
"""
Database initialization script for YouTube Transcript Digest System.
Creates the database schema and performs initial setup.
"""

import sys
import logging
from pathlib import Path

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from database.models import get_database_manager, get_digest_repo
from podcast/rss_models import get_feed_repo, get_podcast_episode_repo

def init_database(db_path: str = None, force: bool = False):
    """
    Initialize the database with schema and verify functionality.
    
    Args:
        db_path: Optional custom database path
        force: If True, recreate database even if it exists
    """
    try:
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        logger = logging.getLogger(__name__)
        
        # Get database manager (this will create the database if needed)
        db_manager = get_database_manager(db_path)
        
        logger.info(f"Initializing database at: {db_manager.db_path}")
        
        # Test database connectivity and schema
        with db_manager.get_connection() as conn:
            # Verify tables exist
            tables_query = "SELECT name FROM sqlite_master WHERE type='table'"
            tables = [row[0] for row in conn.execute(tables_query).fetchall()]
            
            # RSS-first schema: feeds, episodes, digests, system metadata
            required_tables = ['feeds', 'episodes', 'digests', 'system_metadata']
            missing_tables = [table for table in required_tables if table not in tables]
            
            if missing_tables:
                logger.error(f"Missing required tables: {missing_tables}")
                return False
            
            logger.info(f"Found tables: {tables}")
            
            # Verify indexes exist
            indexes_query = "SELECT name FROM sqlite_master WHERE type='index'"
            indexes = [row[0] for row in conn.execute(indexes_query).fetchall()]
            logger.info(f"Found indexes: {len(indexes)} indexes created")
            
            # Verify views exist
            views_query = "SELECT name FROM sqlite_master WHERE type='view'"
            views = [row[0] for row in conn.execute(views_query).fetchall()]
            logger.info(f"Found views: {views}")
            
            # Test schema metadata
            metadata_query = "SELECT key, value FROM system_metadata"
            metadata = dict(conn.execute(metadata_query).fetchall())
            logger.info(f"Schema version: {metadata.get('schema_version', 'Unknown')}")
            logger.info(f"Database created: {metadata.get('created_at', 'Unknown')}")
        
        # Test repository functionality
        logger.info("Testing repository functionality...")
        
        # Test repositories can be created (RSS-first)
        feed_repo = get_feed_repo(db_manager)
        episode_repo = get_podcast_episode_repo(db_manager)
        digest_repo = get_digest_repo(db_manager)
        
        # Test basic queries
        active_feeds = feed_repo.get_all_active()
        logger.info(f"Active feeds: {len(active_feeds)}")
        
        pending_episodes = episode_repo.get_by_status('pending')
        logger.info(f"Pending episodes: {len(pending_episodes)}")
        
        recent_digests = digest_repo.get_recent_digests()
        logger.info(f"Recent digests: {len(recent_digests)}")
        
        logger.info("✅ Database initialization successful!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        return False

def reset_database(db_path: str = None):
    """
    Reset database by deleting and recreating it.
    WARNING: This will delete all data!
    """
    logger = logging.getLogger(__name__)
    
    if db_path is None:
        project_root = Path(__file__).parent.parent.parent
        db_path = project_root / 'data' / 'database' / 'digest.db'
    else:
        db_path = Path(db_path)
    
    if db_path.exists():
        logger.warning(f"Deleting existing database: {db_path}")
        db_path.unlink()
    
    logger.info("Creating fresh database...")
    return init_database(str(db_path))

def get_database_stats(db_path: str = None):
    """Get database statistics for monitoring"""
    db_manager = get_database_manager(db_path)
    
    with db_manager.get_connection() as conn:
        stats = {}
        
        # Table counts
        stats['channels_total'] = conn.execute("SELECT COUNT(*) FROM channels").fetchone()[0]
        stats['channels_active'] = conn.execute("SELECT COUNT(*) FROM channels WHERE active = 1").fetchone()[0]
        stats['episodes_total'] = conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
        stats['episodes_pending'] = conn.execute("SELECT COUNT(*) FROM episodes WHERE status = 'pending'").fetchone()[0]
        stats['episodes_scored'] = conn.execute("SELECT COUNT(*) FROM episodes WHERE status = 'scored'").fetchone()[0]
        stats['episodes_failed'] = conn.execute("SELECT COUNT(*) FROM episodes WHERE status = 'failed'").fetchone()[0]
        stats['digests_total'] = conn.execute("SELECT COUNT(*) FROM digests").fetchone()[0]
        
        # Recent activity
        stats['episodes_last_7_days'] = conn.execute(
            "SELECT COUNT(*) FROM episodes WHERE published_date > date('now', '-7 days')"
        ).fetchone()[0]
        
        stats['digests_last_7_days'] = conn.execute(
            "SELECT COUNT(*) FROM digests WHERE digest_date > date('now', '-7 days')"
        ).fetchone()[0]
        
        # Database size
        stats['database_size_mb'] = round(Path(db_manager.db_path).stat().st_size / 1024 / 1024, 2)
        
    return stats

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Initialize YouTube Digest Database")
    parser.add_argument("--db-path", help="Custom database path")
    parser.add_argument("--reset", action="store_true", help="Reset database (deletes all data)")
    parser.add_argument("--stats", action="store_true", help="Show database statistics")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    # Configure logging level
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if args.stats:
        # Show database statistics
        try:
            stats = get_database_stats(args.db_path)
            print("\n📊 Database Statistics:")
            print("-" * 40)
            for key, value in stats.items():
                print(f"{key.replace('_', ' ').title()}: {value}")
        except Exception as e:
            print(f"❌ Failed to get stats: {e}")
            sys.exit(1)
    
    elif args.reset:
        # Reset database
        print("⚠️  WARNING: This will delete all data!")
        confirm = input("Type 'yes' to confirm database reset: ")
        if confirm.lower() == 'yes':
            if reset_database(args.db_path):
                print("✅ Database reset successful!")
            else:
                print("❌ Database reset failed!")
                sys.exit(1)
        else:
            print("Database reset cancelled.")
    
    else:
        # Initialize database
        if init_database(args.db_path):
            print("✅ Database initialization completed successfully!")
        else:
            print("❌ Database initialization failed!")
            sys.exit(1)
