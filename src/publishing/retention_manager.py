#!/usr/bin/env python3
"""
File Retention Manager for RSS Podcast Digest System

Manages automated cleanup of local files and GitHub releases based on retention policies.

Local MP3 Cleanup Strategy:
- Publishing pipeline deletes local MP3s immediately after successful GitHub upload
- Retention manager serves as safety net for orphaned files (failed uploads, detection issues)
- Retention days configured via web_settings table (retention.local_mp3_days, default: 14)
"""

import os
import shutil
import logging
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from ..utils.logging_config import get_logger
from ..utils.error_handling import PodcastError
from .github_publisher import GitHubPublisher, create_github_publisher
from ..database.models import DatabaseManager
from ..database.sqlalchemy_models import Episode as EpisodeModel, Digest as DigestModel
from ..config.web_config import SettingsKeys
from ..scoring.harold_rnd import HAROLD_RND_SCORE_KEY, HAROLD_RND_RETENTION_THRESHOLD_DEFAULT

logger = get_logger(__name__)

@dataclass
class RetentionPolicy:
    """Retention policy configuration"""
    name: str
    path_pattern: str
    retention_days: int
    file_pattern: str = "*"
    dry_run: bool = False

@dataclass
class CleanupStats:
    """Statistics from cleanup operations"""
    files_deleted: int = 0
    directories_deleted: int = 0
    bytes_freed: int = 0
    github_releases_deleted: int = 0
    episodes_deleted: int = 0
    digests_deleted: int = 0
    story_arcs_deleted: int = 0
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

class RetentionManager:
    """
    Manages file retention and cleanup across local filesystem and GitHub
    """
    
    def __init__(self, retention_policies: List[RetentionPolicy] = None,
                 github_publisher: GitHubPublisher = None,
                 github_release_days: int = None,
                 database_manager: DatabaseManager = None):
        """
        Initialize retention manager

        Args:
            retention_policies: List of retention policies to apply
            github_publisher: GitHub publisher for release cleanup (optional)
            database_manager: Database manager for episode/digest cleanup (optional)
        """
        self.retention_policies = retention_policies or self._get_default_policies()

        # Initialize GitHub publisher with graceful degradation
        if github_publisher:
            self.github_publisher = github_publisher
        else:
            try:
                self.github_publisher = create_github_publisher()
                logger.info("GitHub publisher initialized for release cleanup")
            except Exception as e:
                logger.warning(f"GitHub publisher not available: {e}. GitHub release cleanup will be skipped.")
                self.github_publisher = None

        # Load GitHub release retention from web_settings
        if github_release_days is None:
            try:
                from ..config.web_config import WebConfigManager
                wc = WebConfigManager()
                self.github_release_retention_days = int(wc.get_setting(SettingsKeys.Retention.CATEGORY, SettingsKeys.Retention.GITHUB_RELEASES_DAYS, 14))
                logger.info(f"GitHub release retention: {self.github_release_retention_days} days (from web_settings)")
            except Exception as e:
                logger.warning(f"Could not load GitHub release retention from web_settings, using default: {e}")
                self.github_release_retention_days = 14
        else:
            self.github_release_retention_days = github_release_days

        self.database_manager = database_manager

        logger.info(f"Retention Manager initialized with {len(self.retention_policies)} policies")
    
    def _get_default_policies(self) -> List[RetentionPolicy]:
        """Get default retention policies for the project, loading retention days from WebConfig"""
        project_root = Path(__file__).parent.parent.parent
        
        # Load retention settings from WebConfig
        try:
            from ..config.web_config import WebConfigManager
            wc = WebConfigManager()
            local_mp3_days = int(wc.get_setting(SettingsKeys.Retention.CATEGORY, SettingsKeys.Retention.LOCAL_MP3_DAYS, 14))
            audio_cache_days = int(wc.get_setting(SettingsKeys.Retention.CATEGORY, SettingsKeys.Retention.AUDIO_CACHE_DAYS, 3))
            audio_chunks_days = int(wc.get_setting(SettingsKeys.Retention.CATEGORY, SettingsKeys.Retention.AUDIO_CHUNKS_DAYS, 3))
            logs_days = int(wc.get_setting(SettingsKeys.Retention.CATEGORY, SettingsKeys.Retention.LOGS_DAYS, 3))
        except Exception as e:
            logger.warning(f"Could not load retention settings from WebConfig, using defaults: {e}")
            local_mp3_days = 14
            audio_cache_days = 3
            audio_chunks_days = 3
            logs_days = 3

        return [
            RetentionPolicy(
                name="Local MP3 Files",
                path_pattern=str(project_root / "data" / "completed-tts"),
                retention_days=local_mp3_days,
                file_pattern="*.mp3"
                # NOTE: Publishing pipeline deletes MP3s immediately after GitHub upload
                # This policy is a safety net for orphaned files (failed uploads, etc.)
            ),
            RetentionPolicy(
                name="Audio Cache",
                path_pattern=str(project_root / "audio_cache"),
                retention_days=audio_cache_days,
                file_pattern="*"
            ),
            RetentionPolicy(
                name="Audio Chunks",
                path_pattern=str(project_root / "audio_chunks"),
                retention_days=audio_chunks_days,
                file_pattern="*"
            ),
            RetentionPolicy(
                name="Old Logs",
                path_pattern=str(project_root / "logs"),
                retention_days=logs_days,
                file_pattern="*.log"
            ),
            RetentionPolicy(
                name="Legacy Transcript Files",
                path_pattern=str(project_root / "data" / "transcripts"),
                retention_days=1,
                file_pattern="*.txt"
            )
        ]
    
    def run_cleanup(self, dry_run: bool = False) -> CleanupStats:
        """
        Run complete cleanup based on all retention policies
        
        Args:
            dry_run: If True, only show what would be deleted without actually deleting
            
        Returns:
            CleanupStats with cleanup results
        """
        logger.info(f"Starting cleanup (dry_run={dry_run})")
        stats = CleanupStats()
        
        try:
            # Run database cleanup first (episodes and digests)
            database_stats = self._cleanup_database_records(dry_run)
            self._merge_stats(stats, database_stats)

            # Run local file cleanup
            for policy in self.retention_policies:
                policy_stats = self._cleanup_local_files(policy, dry_run)
                self._merge_stats(stats, policy_stats)

            # Run GitHub cleanup
            if self.github_publisher:
                github_stats = self._cleanup_github_releases(dry_run, retention_days=self.github_release_retention_days)
                self._merge_stats(stats, github_stats)
            
            # Summary
            if dry_run:
                logger.info(f"Dry run complete - would delete {stats.files_deleted} files, "
                           f"{stats.episodes_deleted} episodes, {stats.digests_deleted} digests, "
                           f"{stats.story_arcs_deleted} story arcs, "
                           f"free {self._format_bytes(stats.bytes_freed)}")
            else:
                logger.info(f"Cleanup complete - deleted {stats.files_deleted} files, "
                           f"{stats.episodes_deleted} episodes, {stats.digests_deleted} digests, "
                           f"{stats.story_arcs_deleted} story arcs, "
                           f"freed {self._format_bytes(stats.bytes_freed)}")
            
            return stats
            
        except Exception as e:
            error_msg = f"Cleanup failed: {e}"
            logger.error(error_msg)
            stats.errors.append(error_msg)
            return stats

    def _cleanup_database_records(self, dry_run: bool = False) -> CleanupStats:
        """Clean up old episodes and digests from database"""
        stats = CleanupStats()

        if not self.database_manager:
            # Try to create database manager if not provided
            try:
                self.database_manager = DatabaseManager()
            except Exception as e:
                logger.warning(f"No database manager available for cleanup: {e}")
                return stats

        try:
            # Get retention settings from WebConfig
            from ..config.web_config import WebConfigManager
            wc = WebConfigManager()
            episode_retention_days = int(wc.get_setting(SettingsKeys.Retention.CATEGORY, SettingsKeys.Retention.EPISODE_RETENTION_DAYS, 14))
            digest_retention_days = int(wc.get_setting(SettingsKeys.Retention.CATEGORY, SettingsKeys.Retention.DIGEST_RETENTION_DAYS, 14))
            harold_rnd_threshold = float(wc.get_setting(
                SettingsKeys.Retention.CATEGORY, SettingsKeys.Retention.HAROLD_RND_RETENTION_THRESHOLD,
                HAROLD_RND_RETENTION_THRESHOLD_DEFAULT
            ))
        except Exception as e:
            logger.warning(f"Could not load retention settings, using defaults: {e}")
            episode_retention_days = 14
            digest_retention_days = 14
            harold_rnd_threshold = HAROLD_RND_RETENTION_THRESHOLD_DEFAULT

        episode_cutoff = datetime.now() - timedelta(days=episode_retention_days)
        digest_cutoff = datetime.now() - timedelta(days=digest_retention_days)

        logger.info(f"Cleaning up database records - episodes older than {episode_retention_days} days, "
                   f"digests older than {digest_retention_days} days")

        try:
            with self.database_manager.get_session() as session:
                try:
                    # Candidate episodes to be deleted (based on published_date, not
                    # updated_at). Episodes with a high Harold R&D-applicability
                    # rating (kanban #2855) are exempt from age-based deletion --
                    # same pattern as `is_favorite` digests below -- even when the
                    # episode was marked not_relevant for the podcast itself, so
                    # the weekly R&D miner can still read their transcript_content.
                    # Filtering is done in Python (not a JSON SQL predicate) to
                    # stay database-agnostic, matching
                    # EpisodeRepository.get_scored_episodes_for_topic's convention.
                    # Projects only id + scores -- deciding exempt-vs-delete
                    # needs neither transcript_content nor any other column,
                    # and transcript_content is exactly the large field this
                    # whole exemption exists to protect, so hydrating it here
                    # for every expiring episode just to throw it away would
                    # be the retention sweep's biggest avoidable cost.
                    candidate_rows = session.query(
                        EpisodeModel.id, EpisodeModel.scores
                    ).filter(
                        EpisodeModel.published_date < episode_cutoff
                    ).all()

                    exempt_ids = []
                    delete_ids = []
                    for episode_id, scores in candidate_rows:
                        rnd_score = (scores or {}).get(HAROLD_RND_SCORE_KEY)
                        if isinstance(rnd_score, (int, float)) and rnd_score >= harold_rnd_threshold:
                            exempt_ids.append(episode_id)
                        else:
                            delete_ids.append(episode_id)

                    episodes_count = len(delete_ids)
                    if exempt_ids:
                        logger.info(
                            f"Retention: exempting {len(exempt_ids)} episode(s) from age-based "
                            f"deletion (harold_applicability >= {harold_rnd_threshold})"
                        )

                    # Count digests to be deleted (based on digest_date, not generated_at).
                    # Favorites are exempt from age-based deletion.
                    digests_query = session.query(DigestModel).filter(
                        DigestModel.digest_date < digest_cutoff.date(),
                        DigestModel.is_favorite.is_(False),
                    )
                    digests_count = digests_query.count()

                    # Count orphaned 0-episode draft digests
                    orphan_digests_query = session.query(DigestModel).filter(
                        DigestModel.episode_count == 0,
                        DigestModel.mp3_path.is_(None),
                        DigestModel.status == 'draft'
                    )
                    orphan_count = orphan_digests_query.count()

                    if dry_run:
                        logger.info(f"Would delete {episodes_count} episodes, {digests_count} digests, {orphan_count} orphaned 0-episode drafts")
                        stats.episodes_deleted = episodes_count
                        stats.digests_deleted = digests_count + orphan_count
                    else:
                        # Delete episodes (excluding the harold_rnd-exempt set)
                        if episodes_count > 0:
                            episodes_deleted = session.query(EpisodeModel).filter(
                                EpisodeModel.id.in_(delete_ids)
                            ).delete(synchronize_session=False)
                            stats.episodes_deleted = episodes_deleted
                            logger.info(f"Deleted {episodes_deleted} old episodes")

                        # Delete digests
                        if digests_count > 0:
                            digests_deleted = digests_query.delete()
                            stats.digests_deleted = digests_deleted
                            logger.info(f"Deleted {digests_deleted} old digests")

                        # Delete orphaned 0-episode draft digests (no content, never will have MP3)
                        # These are created when topics have no qualifying episodes but the system
                        # still creates a draft digest entry
                        orphan_digests_query = session.query(DigestModel).filter(
                            DigestModel.episode_count == 0,
                            DigestModel.mp3_path.is_(None),
                            DigestModel.status == 'draft'
                        )
                        orphan_count = orphan_digests_query.count()
                        if orphan_count > 0:
                            orphan_deleted = orphan_digests_query.delete()
                            stats.digests_deleted += orphan_deleted
                            logger.info(f"Deleted {orphan_deleted} orphaned 0-episode draft digests")

                        # Commit the transaction
                        session.commit()

                    # Clean up story arcs (separate transaction)
                    try:
                        story_arc_retention_days = int(wc.get_setting(
                            SettingsKeys.Retention.CATEGORY, 'story_arc_retention_days', 14
                        ))
                        story_arc_inactivity_days = int(wc.get_setting(
                            SettingsKeys.Retention.CATEGORY, 'story_arc_inactivity_days', 7
                        ))

                        from ..database.story_arc_repo import get_story_arc_repo
                        story_arc_repo = get_story_arc_repo()

                        if dry_run:
                            logger.info(f"Would clean up story arcs (max_age={story_arc_retention_days}d, inactivity={story_arc_inactivity_days}d)")
                        else:
                            arcs_deleted = story_arc_repo.cleanup_old_story_arcs(
                                max_age_days=story_arc_retention_days,
                                inactivity_days=story_arc_inactivity_days
                            )
                            stats.story_arcs_deleted = arcs_deleted
                            if arcs_deleted > 0:
                                logger.info(f"Deleted {arcs_deleted} old story arcs")
                    except Exception as e:
                        logger.warning(f"Story arc cleanup failed: {e}")

                    return stats

                except Exception as e:
                    session.rollback()
                    error_msg = f"Database cleanup failed: {e}"
                    logger.error(error_msg)
                    stats.errors.append(error_msg)
                    return stats

        except Exception as e:
            error_msg = f"Failed to connect to database: {e}"
            logger.error(error_msg)
            stats.errors.append(error_msg)
            return stats

    def _cleanup_local_files(self, policy: RetentionPolicy, dry_run: bool) -> CleanupStats:
        """Clean up local files based on retention policy"""
        stats = CleanupStats()
        
        try:
            base_path = Path(policy.path_pattern)
            if not base_path.exists():
                logger.debug(f"Path does not exist: {base_path}")
                return stats
            
            cutoff_date = datetime.now() - timedelta(days=policy.retention_days)
            logger.info(f"Cleaning up {policy.name} (older than {policy.retention_days} days)")
            
            # Find files matching pattern and age
            files_to_delete = []
            for file_path in base_path.rglob(policy.file_pattern):
                if file_path.is_file():
                    # Get file modification time
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if mtime < cutoff_date:
                        files_to_delete.append(file_path)
            
            # Delete files
            for file_path in files_to_delete:
                try:
                    file_size = file_path.stat().st_size
                    
                    if dry_run:
                        logger.debug(f"Would delete: {file_path}")
                    else:
                        file_path.unlink()
                        logger.debug(f"Deleted: {file_path}")
                    
                    stats.files_deleted += 1
                    stats.bytes_freed += file_size
                    
                except Exception as e:
                    error_msg = f"Failed to delete {file_path}: {e}"
                    logger.error(error_msg)
                    stats.errors.append(error_msg)
            
            # Clean up empty directories
            self._cleanup_empty_dirs(base_path, dry_run, stats)
            
            if stats.files_deleted > 0:
                logger.info(f"{policy.name}: {'would delete' if dry_run else 'deleted'} "
                           f"{stats.files_deleted} files ({self._format_bytes(stats.bytes_freed)})")
            
            return stats
            
        except Exception as e:
            error_msg = f"Failed to cleanup {policy.name}: {e}"
            logger.error(error_msg)
            stats.errors.append(error_msg)
            return stats
    
    def _cleanup_empty_dirs(self, base_path: Path, dry_run: bool, stats: CleanupStats):
        """Remove empty directories"""
        try:
            # Walk directories bottom-up to handle nested empty directories
            for dir_path in sorted(base_path.rglob("*"), key=lambda x: len(str(x)), reverse=True):
                if dir_path.is_dir() and dir_path != base_path:
                    try:
                        # Check if directory is empty
                        if not any(dir_path.iterdir()):
                            if dry_run:
                                logger.debug(f"Would remove empty directory: {dir_path}")
                            else:
                                dir_path.rmdir()
                                logger.debug(f"Removed empty directory: {dir_path}")
                            
                            stats.directories_deleted += 1
                    
                    except OSError as e:
                        # Directory not empty or permission/disk error - log but continue
                        logger.debug(f"Could not remove directory {dir_path}: {e}")
                    except Exception as e:
                        error_msg = f"Failed to remove directory {dir_path}: {e}"
                        logger.error(error_msg)
                        stats.errors.append(error_msg)
        
        except Exception as e:
            error_msg = f"Failed to cleanup empty directories: {e}"
            logger.error(error_msg)
            stats.errors.append(error_msg)
    
    def _cleanup_github_releases(self, dry_run: bool, retention_days: int = 14) -> CleanupStats:
        """Clean up old GitHub releases. Favorited digests' release tags are skipped."""
        stats = CleanupStats()

        try:
            if not self.github_publisher:
                logger.debug("No GitHub publisher available for cleanup")
                return stats

            logger.info(f"Cleaning up GitHub releases (older than {retention_days} days)")

            # Build set of release tags referenced by favorite digests — those are skipped.
            from ..database.sqlalchemy_models import Digest as DigestModel
            favorite_urls: set[str] = set()
            try:
                with self.database_manager.get_session() as session:
                    rows = session.query(DigestModel.github_url).filter(
                        DigestModel.is_favorite.is_(True),
                        DigestModel.github_url.isnot(None),
                    ).all()
                    favorite_urls = {r[0] for r in rows}
            except Exception as e:
                logger.warning(f"Could not load favorite digest URLs; no releases will be shielded: {e}")

            # Get releases
            releases = self.github_publisher.list_releases()
            cutoff_date = datetime.now() - timedelta(days=retention_days)

            # Find releases to delete
            releases_to_delete = []
            for release in releases:
                release_date = release.published_at.replace(tzinfo=None)
                if release_date >= cutoff_date:
                    continue
                # Skip if this release URL is referenced by a favorite digest
                release_url = getattr(release, 'html_url', '') or getattr(release, 'url', '')
                if any(release_url.endswith(fav_url.split('/')[-1]) for fav_url in favorite_urls if fav_url):
                    logger.info(f"Preserving GitHub release {release.name} — referenced by favorite digest")
                    continue
                releases_to_delete.append(release)
            
            # Delete releases
            for release in releases_to_delete:
                try:
                    if dry_run:
                        logger.debug(f"Would delete GitHub release: {release.name}")
                    else:
                        self.github_publisher.delete_release(release.id)
                        logger.debug(f"Deleted GitHub release: {release.name}")
                    
                    stats.github_releases_deleted += 1
                    
                except Exception as e:
                    error_msg = f"Failed to delete GitHub release {release.name}: {e}"
                    logger.error(error_msg)
                    stats.errors.append(error_msg)
            
            if stats.github_releases_deleted > 0:
                logger.info(f"GitHub: {'would delete' if dry_run else 'deleted'} "
                           f"{stats.github_releases_deleted} releases")
            
            return stats
            
        except Exception as e:
            error_msg = f"Failed to cleanup GitHub releases: {e}"
            logger.error(error_msg)
            stats.errors.append(error_msg)
            return stats
    
    def _merge_stats(self, main_stats: CleanupStats, additional_stats: CleanupStats):
        """Merge cleanup statistics"""
        main_stats.files_deleted += additional_stats.files_deleted
        main_stats.directories_deleted += additional_stats.directories_deleted
        main_stats.bytes_freed += additional_stats.bytes_freed
        main_stats.github_releases_deleted += additional_stats.github_releases_deleted
        main_stats.episodes_deleted += additional_stats.episodes_deleted
        main_stats.digests_deleted += additional_stats.digests_deleted
        main_stats.story_arcs_deleted += additional_stats.story_arcs_deleted
        main_stats.errors.extend(additional_stats.errors)
    
    def _format_bytes(self, bytes_count: int) -> str:
        """Format byte count in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_count < 1024.0:
                return f"{bytes_count:.1f} {unit}"
            bytes_count /= 1024.0
        return f"{bytes_count:.1f} TB"
    
    def get_disk_usage_stats(self) -> Dict[str, Any]:
        """Get disk usage statistics for monitored directories"""
        stats = {}
        
        for policy in self.retention_policies:
            path = Path(policy.path_pattern)
            if path.exists():
                total_size = 0
                file_count = 0
                
                for file_path in path.rglob(policy.file_pattern):
                    if file_path.is_file():
                        total_size += file_path.stat().st_size
                        file_count += 1
                
                stats[policy.name] = {
                    'path': str(path),
                    'file_count': file_count,
                    'total_size': total_size,
                    'total_size_formatted': self._format_bytes(total_size),
                    'retention_days': policy.retention_days
                }
        
        return stats

    # Backward-compatible alias used by orchestration scripts
    def cleanup_all(self, dry_run: bool = False) -> CleanupStats:
        """Alias for run_cleanup to match pipeline usage."""
        return self.run_cleanup(dry_run)
    
    def cleanup_specific_date(self, cleanup_date: date, dry_run: bool = False) -> CleanupStats:
        """
        Clean up files from a specific date regardless of retention policy
        Useful for manual cleanup or testing
        
        Args:
            cleanup_date: Date to clean up files from
            dry_run: If True, only show what would be deleted
            
        Returns:
            CleanupStats with cleanup results
        """
        logger.info(f"Cleaning up files from {cleanup_date} (dry_run={dry_run})")
        stats = CleanupStats()
        
        # Format date for filename matching
        date_str = cleanup_date.strftime('%Y%m%d')
        
        try:
            for policy in self.retention_policies:
                base_path = Path(policy.path_pattern)
                if not base_path.exists():
                    continue
                
                # Find files with date in filename
                files_to_delete = []
                for file_path in base_path.rglob(policy.file_pattern):
                    if file_path.is_file() and date_str in file_path.name:
                        files_to_delete.append(file_path)
                
                # Delete files
                for file_path in files_to_delete:
                    try:
                        file_size = file_path.stat().st_size
                        
                        if dry_run:
                            logger.debug(f"Would delete: {file_path}")
                        else:
                            file_path.unlink()
                            logger.debug(f"Deleted: {file_path}")
                        
                        stats.files_deleted += 1
                        stats.bytes_freed += file_size
                        
                    except Exception as e:
                        error_msg = f"Failed to delete {file_path}: {e}"
                        logger.error(error_msg)
                        stats.errors.append(error_msg)
            
            # Clean up GitHub release for that date
            if self.github_publisher:
                tag_name = f"daily-{cleanup_date.strftime('%Y-%m-%d')}"
                release = self.github_publisher.get_release_by_tag(tag_name)
                
                if release:
                    try:
                        if dry_run:
                            logger.info(f"Would delete GitHub release: {release.name}")
                        else:
                            self.github_publisher.delete_release(release.id)
                            logger.info(f"Deleted GitHub release: {release.name}")
                        
                        stats.github_releases_deleted += 1
                        
                    except Exception as e:
                        error_msg = f"Failed to delete GitHub release: {e}"
                        logger.error(error_msg)
                        stats.errors.append(error_msg)
            
            logger.info(f"Date cleanup complete: {'would delete' if dry_run else 'deleted'} "
                       f"{stats.files_deleted} files, {stats.github_releases_deleted} releases")
            
            return stats
            
        except Exception as e:
            error_msg = f"Date cleanup failed: {e}"
            logger.error(error_msg)
            stats.errors.append(error_msg)
            return stats


def create_retention_manager(retention_policies: List[RetentionPolicy] = None,
                           github_publisher: GitHubPublisher = None,
                           database_manager: DatabaseManager = None) -> RetentionManager:
    """Factory function to create retention manager with WebConfig overrides if available"""
    # Try to pull retention days from WebConfig
    github_days = 14
    try:
        from ..config.web_config import WebConfigManager
        wc = WebConfigManager()
        github_days = int(wc.get_setting(SettingsKeys.Retention.CATEGORY, SettingsKeys.Retention.GITHUB_RELEASES_DAYS, 14))
        # Override local policies if none provided
        if retention_policies is None:
            rm = RetentionManager(None, github_publisher, github_days, database_manager)
            # Update default policies' days from web settings
            # Map policy names to SettingsKeys constants
            policy_key_map = {
                'Local MP3 Files': SettingsKeys.Retention.LOCAL_MP3_DAYS,
                'Audio Cache': SettingsKeys.Retention.AUDIO_CACHE_DAYS,
                'Audio Chunks': SettingsKeys.Retention.AUDIO_CHUNKS_DAYS,
                'Old Logs': SettingsKeys.Retention.LOGS_DAYS,
            }
            for p in rm.retention_policies:
                key = policy_key_map.get(p.name)
                if key:
                    try:
                        p.retention_days = int(wc.get_setting(SettingsKeys.Retention.CATEGORY, key, p.retention_days))
                    except Exception as e:
                        logger.warning(f"Could not load retention setting for {p.name}, using default ({p.retention_days} days): {e}")
            return rm
    except Exception as e:
        logger.warning(f"Could not load retention settings from WebConfig, using defaults: {e}")
    return RetentionManager(retention_policies, github_publisher, github_days, database_manager)


# CLI testing functionality
if __name__ == "__main__":
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description='Retention Manager CLI')
    parser.add_argument('--cleanup', action='store_true', help='Run cleanup based on retention policies')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be cleaned up without actually doing it')
    parser.add_argument('--stats', action='store_true', help='Show disk usage statistics')
    parser.add_argument('--cleanup-date', help='Clean up files from specific date (YYYY-MM-DD)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        retention_manager = create_retention_manager()
        
        if args.stats:
            stats = retention_manager.get_disk_usage_stats()
            print("\n📊 Disk Usage Statistics:")
            print("-" * 60)
            total_size = 0
            total_files = 0
            
            for policy_name, policy_stats in stats.items():
                print(f"• {policy_name}")
                print(f"  Path: {policy_stats['path']}")
                print(f"  Files: {policy_stats['file_count']}")
                print(f"  Size: {policy_stats['total_size_formatted']}")
                print(f"  Retention: {policy_stats['retention_days']} days")
                print()
                
                total_size += policy_stats['total_size']
                total_files += policy_stats['file_count']
            
            print(f"Total: {total_files} files, {retention_manager._format_bytes(total_size)}")
        
        elif args.cleanup_date:
            try:
                cleanup_date = datetime.strptime(args.cleanup_date, '%Y-%m-%d').date()
                stats = retention_manager.cleanup_specific_date(cleanup_date, args.dry_run)
                
                action = "Would delete" if args.dry_run else "Deleted"
                print(f"✅ {action} {stats.files_deleted} files, {stats.episodes_deleted} episodes, "
                      f"{stats.digests_deleted} digests, {stats.github_releases_deleted} GitHub releases")
                
                if stats.errors:
                    print(f"⚠️  Errors encountered: {len(stats.errors)}")
                    for error in stats.errors[:5]:  # Show first 5 errors
                        print(f"   {error}")
                
            except ValueError:
                print("❌ Invalid date format. Use YYYY-MM-DD")
                exit(1)
        
        elif args.cleanup:
            stats = retention_manager.run_cleanup(args.dry_run)
            
            action = "Would delete" if args.dry_run else "Deleted"
            print(f"✅ Cleanup complete:")
            print(f"   Files: {action.lower()} {stats.files_deleted}")
            print(f"   Directories: {action.lower()} {stats.directories_deleted}")
            print(f"   Episodes: {action.lower()} {stats.episodes_deleted}")
            print(f"   Digests: {action.lower()} {stats.digests_deleted}")
            print(f"   GitHub releases: {action.lower()} {stats.github_releases_deleted}")
            print(f"   Space freed: {retention_manager._format_bytes(stats.bytes_freed)}")
            
            if stats.errors:
                print(f"⚠️  Errors encountered: {len(stats.errors)}")
                for error in stats.errors[:5]:  # Show first 5 errors
                    print(f"   {error}")
        
        else:
            print("Use --help for available commands")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        exit(1)
