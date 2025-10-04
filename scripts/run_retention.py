#!/usr/bin/env python3
"""
Phase 6: Retention Management

Dedicated retention phase that runs after publishing to clean up old files,
database records, and GitHub releases based on configured retention policies.

This phase is intentionally separate from Discovery and Publishing to provide
a single source of truth for all retention and cleanup operations.

Retention policies are configured via web UI (web_settings table):
- local_mp3_days: How long to keep local MP3 files (default: 14 days)
- audio_cache_days: How long to keep audio cache files (default: 3 days)
- logs_days: How long to keep log files (default: 3 days)
- github_release_days: How long to keep GitHub releases (default: 14 days)
- episode_retention_days: How long to keep episode database records (default: 14 days)
- digest_retention_days: How long to keep digest database records (default: 14 days)
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.publishing.retention_manager import create_retention_manager
from src.config.web_config import WebConfigManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_retention_phase() -> dict:
    """
    Run retention management phase.

    Returns:
        dict: Phase results with cleanup statistics
    """
    start_time = datetime.now()

    try:
        logger.info("=" * 80)
        logger.info("Phase 6: Retention Management")
        logger.info("=" * 80)

        # Initialize retention manager using factory function
        # Factory function automatically reads retention settings from WebConfig
        logger.info("Initializing RetentionManager...")
        retention_manager = create_retention_manager()

        # Run cleanup
        logger.info("Running retention cleanup...")
        cleanup_stats = retention_manager.run_cleanup()
        has_errors = bool(cleanup_stats.errors)

        # Calculate totals with graceful fallback for legacy CleanupStats structure
        total_files = getattr(cleanup_stats, "total_files", cleanup_stats.files_deleted)
        total_bytes = getattr(cleanup_stats, "total_bytes", cleanup_stats.bytes_freed)
        total_mb = total_bytes / (1024 * 1024) if total_bytes else 0

        logger.info("=" * 80)
        logger.info("Retention Cleanup Results:")
        logger.info(f"  Files deleted: {cleanup_stats.files_deleted}")
        logger.info(f"  Directories deleted: {cleanup_stats.directories_deleted}")
        logger.info(f"  Database episodes deleted: {cleanup_stats.episodes_deleted}")
        logger.info(f"  Database digests deleted: {cleanup_stats.digests_deleted}")
        logger.info(f"  GitHub releases deleted: {cleanup_stats.github_releases_deleted}")
        logger.info(f"  Space freed: {total_mb:.2f} MB")
        logger.info("=" * 80)

        if has_errors:
            logger.warning(f"Retention cleanup completed with {len(cleanup_stats.errors)} error(s)")
            for err in cleanup_stats.errors:
                logger.warning(f"  - {err}")

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Build result
        result = {
            "success": not has_errors,
            "status": "success" if not has_errors else "warning",
            "phase": "retention",
            "cleanup_stats": {
                "files_deleted": cleanup_stats.files_deleted,
                "directories_deleted": cleanup_stats.directories_deleted,
                "bytes_freed": cleanup_stats.bytes_freed,
                "episodes_deleted": cleanup_stats.episodes_deleted,
                "digests_deleted": cleanup_stats.digests_deleted,
                "github_releases_deleted": cleanup_stats.github_releases_deleted,
                "total_files": total_files,
                "total_bytes": total_bytes,
                "total_mb": round(total_mb, 2),
                "errors": cleanup_stats.errors,
            },
            "duration_seconds": round(duration, 2),
            "started_at": start_time.isoformat(),
            "completed_at": end_time.isoformat()
        }

        if has_errors:
            result["error"] = f"Retention encountered {len(cleanup_stats.errors)} error(s)"

        return result

    except Exception as e:
        logger.error(f"Retention phase failed: {e}", exc_info=True)
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        return {
            "success": False,
            "status": "error",
            "phase": "retention",
            "error": str(e),
            "duration_seconds": round(duration, 2),
            "started_at": start_time.isoformat(),
            "completed_at": end_time.isoformat()
        }


def main():
    """Main entry point for retention phase."""
    result = run_retention_phase()

    # Output JSON for orchestrator
    print("\n" + "=" * 80)
    print("RETENTION_PHASE_RESULT_JSON")
    print(json.dumps(result, indent=2))
    print("=" * 80)

    # Exit with appropriate code
    if result["status"] == "error":
        sys.exit(1)
    elif result["status"] == "skipped":
        sys.exit(0)  # Not an error, just skipped
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
