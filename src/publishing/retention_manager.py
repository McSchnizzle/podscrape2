#!/usr/bin/env python3
"""
File Retention Manager for RSS Podcast Digest System
Manages automated cleanup of local files and GitHub releases based on retention policies
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
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []

class RetentionManager:
    """
    Manages file retention and cleanup across local filesystem and GitHub
    """
    
    def __init__(self, retention_policies: List[RetentionPolicy] = None,
                 github_publisher: GitHubPublisher = None):
        """
        Initialize retention manager
        
        Args:
            retention_policies: List of retention policies to apply
            github_publisher: GitHub publisher for release cleanup (optional)
        """
        self.retention_policies = retention_policies or self._get_default_policies()
        self.github_publisher = github_publisher or create_github_publisher()
        
        logger.info(f"Retention Manager initialized with {len(self.retention_policies)} policies")
    
    def _get_default_policies(self) -> List[RetentionPolicy]:
        """Get default retention policies for the project"""
        project_root = Path(__file__).parent.parent.parent
        
        return [
            RetentionPolicy(
                name="Local MP3 Files",
                path_pattern=str(project_root / "data" / "completed-tts"),
                retention_days=7,
                file_pattern="*.mp3"
            ),
            RetentionPolicy(
                name="Audio Cache",
                path_pattern=str(project_root / "data" / "audio_cache"),
                retention_days=3,
                file_pattern="*.mp3"
            ),
            RetentionPolicy(
                name="Audio Chunks",
                path_pattern=str(project_root / "data" / "audio_chunks"),
                retention_days=1,
                file_pattern="*.mp3"
            ),
            RetentionPolicy(
                name="Old Logs",
                path_pattern=str(project_root / "data" / "logs"),
                retention_days=30,
                file_pattern="*.log"
            ),
            RetentionPolicy(
                name="Old Scripts",
                path_pattern=str(project_root / "data" / "scripts"),
                retention_days=14,
                file_pattern="*.md"
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
            # Run local file cleanup
            for policy in self.retention_policies:
                policy_stats = self._cleanup_local_files(policy, dry_run)
                self._merge_stats(stats, policy_stats)
            
            # Run GitHub cleanup
            if self.github_publisher:
                github_stats = self._cleanup_github_releases(dry_run)
                self._merge_stats(stats, github_stats)
            
            # Summary
            if dry_run:
                logger.info(f"Dry run complete - would delete {stats.files_deleted} files, "
                           f"free {self._format_bytes(stats.bytes_freed)}")
            else:
                logger.info(f"Cleanup complete - deleted {stats.files_deleted} files, "
                           f"freed {self._format_bytes(stats.bytes_freed)}")
            
            return stats
            
        except Exception as e:
            error_msg = f"Cleanup failed: {e}"
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
                    
                    except OSError:
                        # Directory not empty or other error, skip
                        pass
                    except Exception as e:
                        error_msg = f"Failed to remove directory {dir_path}: {e}"
                        logger.error(error_msg)
                        stats.errors.append(error_msg)
        
        except Exception as e:
            error_msg = f"Failed to cleanup empty directories: {e}"
            logger.error(error_msg)
            stats.errors.append(error_msg)
    
    def _cleanup_github_releases(self, dry_run: bool, retention_days: int = 14) -> CleanupStats:
        """Clean up old GitHub releases"""
        stats = CleanupStats()
        
        try:
            if not self.github_publisher:
                logger.debug("No GitHub publisher available for cleanup")
                return stats
            
            logger.info(f"Cleaning up GitHub releases (older than {retention_days} days)")
            
            # Get releases
            releases = self.github_publisher.list_releases()
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            
            # Find releases to delete
            releases_to_delete = []
            for release in releases:
                # Remove timezone info for comparison
                release_date = release.published_at.replace(tzinfo=None)
                if release_date < cutoff_date:
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
                           github_publisher: GitHubPublisher = None) -> RetentionManager:
    """Factory function to create retention manager"""
    return RetentionManager(retention_policies, github_publisher)


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
                print(f"✅ {action} {stats.files_deleted} files, {stats.github_releases_deleted} GitHub releases")
                
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
