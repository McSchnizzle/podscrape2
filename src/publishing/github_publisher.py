#!/usr/bin/env python3
"""
GitHub Publisher for RSS Podcast Digest System
Handles uploading MP3 files to GitHub releases and managing release lifecycle
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List
import requests
from dataclasses import dataclass

from ..utils.error_handling import retry_with_backoff, PodcastError
from ..utils.logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class GitHubRelease:
    """Represents a GitHub release"""
    id: str
    tag_name: str
    name: str
    body: str
    created_at: datetime
    published_at: datetime
    assets: List[Dict[str, Any]]

@dataclass
class GitHubAsset:
    """Represents a GitHub release asset"""
    id: str
    name: str
    download_url: str
    size: int
    created_at: datetime

class GitHubPublisher:
    """
    Manages uploading MP3 files to GitHub releases
    """
    
    def __init__(self, github_token: str = None, repository: str = None):
        """
        Initialize GitHub publisher
        
        Args:
            github_token: GitHub personal access token (if not provided, uses GITHUB_TOKEN env var)
            repository: Repository name in format "owner/repo" (if not provided, uses GITHUB_REPOSITORY env var)
        """
        self.github_token = github_token or os.getenv('GITHUB_TOKEN')
        self.repository = repository or os.getenv('GITHUB_REPOSITORY')
        
        if not self.github_token:
            raise PodcastError("GitHub token not provided and GITHUB_TOKEN env var not set")
        
        if not self.repository:
            raise PodcastError("Repository not provided and GITHUB_REPOSITORY env var not set")
        
        self.api_base = "https://api.github.com"
        self.headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'RSS-Podcast-Digest-System/1.0'
        }
        
        logger.info(f"GitHub Publisher initialized for repository: {self.repository}")
    
    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Make authenticated GitHub API request"""
        try:
            response = requests.request(method, url, headers=self.headers, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"GitHub API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response body: {e.response.text}")
            raise PodcastError(f"GitHub API request failed: {e}")
    
    @retry_with_backoff(max_retries=3, backoff_factor=2.0)
    def create_daily_release(self, release_date: date, mp3_files: List[str]) -> GitHubRelease:
        """
        Create a daily release for podcast episodes
        
        Args:
            release_date: Date for the release
            mp3_files: List of MP3 file paths to upload
            
        Returns:
            GitHubRelease object with release information
        """
        tag_name = f"daily-{release_date.strftime('%Y-%m-%d')}"
        release_name = f"Daily Digest - {release_date.strftime('%B %d, %Y')}"
        
        logger.info(f"Creating GitHub release: {release_name}")
        
        # Check if release already exists
        existing_release = self.get_release_by_tag(tag_name)
        if existing_release:
            logger.info(f"Release already exists: {tag_name}")
            return existing_release
        
        # Create release body
        release_body = self._generate_release_body(release_date, mp3_files)
        
        # Create the release
        url = f"{self.api_base}/repos/{self.repository}/releases"
        data = {
            "tag_name": tag_name,
            "name": release_name,
            "body": release_body,
            "draft": False,
            "prerelease": False
        }
        
        try:
            response = self._make_request('POST', url, json=data)
            release_data = response.json()
            
            # Upload MP3 files as assets
            for mp3_file in mp3_files:
                self._upload_asset(release_data['id'], mp3_file)
            
            # Convert to GitHubRelease object
            github_release = self._parse_release_data(release_data)
            
            logger.info(f"Created GitHub release: {github_release.id} ({github_release.name})")
            return github_release
            
        except Exception as e:
            logger.error(f"Failed to create GitHub release: {e}")
            raise PodcastError(f"Failed to create GitHub release: {e}")
    
    def get_release_by_tag(self, tag_name: str) -> Optional[GitHubRelease]:
        """Get release by tag name"""
        try:
            url = f"{self.api_base}/repos/{self.repository}/releases/tags/{tag_name}"
            response = self._make_request('GET', url)
            
            if response.status_code == 404:
                return None
            
            return self._parse_release_data(response.json())
            
        except Exception as e:
            if "404" in str(e):
                return None
            logger.error(f"Failed to get release by tag {tag_name}: {e}")
            raise PodcastError(f"Failed to get release: {e}")
    
    @retry_with_backoff(max_retries=2, backoff_factor=1.5)
    def _upload_asset(self, release_id: str, file_path: str):
        """Upload file as release asset"""
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise PodcastError(f"File not found: {file_path}")
        
        logger.info(f"Uploading asset: {file_path.name}")
        
        # Get upload URL from release
        url = f"{self.api_base}/repos/{self.repository}/releases/{release_id}"
        response = self._make_request('GET', url)
        release_data = response.json()
        
        upload_url_template = release_data['upload_url']
        # Remove the template part {?name,label}
        upload_url = upload_url_template.replace('{?name,label}', '')
        
        # Upload the file
        upload_headers = self.headers.copy()
        upload_headers['Content-Type'] = 'application/octet-stream'
        
        with open(file_path, 'rb') as f:
            params = {'name': file_path.name}
            upload_response = requests.post(
                upload_url,
                headers=upload_headers,
                params=params,
                data=f
            )
            upload_response.raise_for_status()
        
        logger.info(f"Successfully uploaded: {file_path.name}")
    
    def _generate_release_body(self, release_date: date, mp3_files: List[str]) -> str:
        """Generate release description"""
        file_list = "\n".join([f"- {Path(f).name}" for f in mp3_files])
        
        return f"""# Daily Podcast Digest - {release_date.strftime('%B %d, %Y')}

Automated daily digest of podcast episodes, processed and generated using AI.

## Files Included

{file_list}

## About

These audio files are generated from podcast transcripts that scored above our relevance threshold for their respective topics. Each digest combines multiple episodes into a coherent narrative.

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}  
**System**: RSS Podcast Transcript Digest System  
**AI Models**: GPT-5 (script generation), ElevenLabs (text-to-speech)

---

*This release was automatically generated. Visit [podcast.paulrbrown.org](https://podcast.paulrbrown.org) for RSS feed access.*"""
    
    def _parse_release_data(self, data: Dict[str, Any]) -> GitHubRelease:
        """Parse GitHub API release data into GitHubRelease object"""
        return GitHubRelease(
            id=str(data['id']),
            tag_name=data['tag_name'],
            name=data['name'],
            body=data['body'],
            created_at=datetime.fromisoformat(data['created_at'].replace('Z', '+00:00')),
            published_at=datetime.fromisoformat(data['published_at'].replace('Z', '+00:00')),
            assets=[{
                'id': asset['id'],
                'name': asset['name'],
                'download_url': asset['browser_download_url'],
                'size': asset['size'],
                'created_at': asset['created_at']
            } for asset in data.get('assets', [])]
        )
    
    def list_releases(self, limit: int = 30) -> List[GitHubRelease]:
        """List recent releases"""
        try:
            url = f"{self.api_base}/repos/{self.repository}/releases"
            params = {'per_page': limit}
            response = self._make_request('GET', url, params=params)
            
            releases = []
            for release_data in response.json():
                releases.append(self._parse_release_data(release_data))
            
            logger.info(f"Found {len(releases)} releases")
            return releases
            
        except Exception as e:
            logger.error(f"Failed to list releases: {e}")
            raise PodcastError(f"Failed to list releases: {e}")
    
    def delete_release(self, release_id: str):
        """Delete a release and its assets"""
        try:
            url = f"{self.api_base}/repos/{self.repository}/releases/{release_id}"
            self._make_request('DELETE', url)
            logger.info(f"Deleted release: {release_id}")
            
        except Exception as e:
            logger.error(f"Failed to delete release {release_id}: {e}")
            raise PodcastError(f"Failed to delete release: {e}")
    
    def cleanup_old_releases(self, keep_days: int = 14):
        """
        Clean up releases older than keep_days
        
        Args:
            keep_days: Number of days to keep releases (default: 14)
        """
        logger.info(f"Cleaning up releases older than {keep_days} days")
        
        try:
            releases = self.list_releases()
            cutoff_date = datetime.now().replace(tzinfo=None) - timedelta(days=keep_days)
            
            deleted_count = 0
            for release in releases:
                # Remove timezone info for comparison
                release_date = release.published_at.replace(tzinfo=None)
                
                if release_date < cutoff_date:
                    logger.info(f"Deleting old release: {release.name} ({release_date.date()})")
                    self.delete_release(release.id)
                    deleted_count += 1
            
            logger.info(f"Cleanup complete: deleted {deleted_count} old releases")
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            raise PodcastError(f"Release cleanup failed: {e}")


def create_github_publisher(github_token: str = None, repository: str = None) -> GitHubPublisher:
    """Factory function to create GitHub publisher"""
    return GitHubPublisher(github_token, repository)


# CLI testing functionality
if __name__ == "__main__":
    import sys
    import argparse
    from datetime import timedelta
    
    parser = argparse.ArgumentParser(description='GitHub Publisher CLI')
    parser.add_argument('--list-releases', action='store_true', help='List recent releases')
    parser.add_argument('--cleanup', action='store_true', help='Clean up old releases')
    parser.add_argument('--keep-days', type=int, default=14, help='Days to keep releases (default: 14)')
    parser.add_argument('--test-upload', nargs='+', help='Test upload MP3 files')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        publisher = create_github_publisher()
        
        if args.list_releases:
            releases = publisher.list_releases()
            print(f"\n📋 Recent Releases ({len(releases)}):")
            print("-" * 60)
            for release in releases:
                asset_count = len(release.assets)
                print(f"• {release.name}")
                print(f"  Tag: {release.tag_name}")
                print(f"  Published: {release.published_at.date()}")
                print(f"  Assets: {asset_count} files")
                print()
        
        elif args.cleanup:
            publisher.cleanup_old_releases(args.keep_days)
            print(f"✅ Cleanup complete (kept {args.keep_days} days)")
        
        elif args.test_upload:
            # Test upload with today's date
            test_date = date.today()
            release = publisher.create_daily_release(test_date, args.test_upload)
            print(f"✅ Test upload complete: {release.name}")
            print(f"Release ID: {release.id}")
            print(f"Assets uploaded: {len(release.assets)}")
        
        else:
            print("Use --help for available commands")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)