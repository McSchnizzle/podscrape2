"""
Test Data Cache Management

Provides cached test data options while maintaining real feed testing philosophy.
Implements optional caching for performance without compromising test authenticity.
"""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
import hashlib

import feedparser
import requests


class TestDataCache:
    """
    Test data caching system that maintains real RSS feed testing philosophy.

    Core Principles:
    1. Real Data First: Always prefer real RSS feeds over mock data
    2. Optional Caching: Cache is performance optimization, not replacement
    3. Freshness Control: Cache expires to ensure data relevance
    4. Fail Gracefully: Fall back to real feeds if cache fails
    """

    def __init__(self, cache_dir: Optional[str] = None, cache_ttl_hours: int = 6):
        self.cache_dir = Path(cache_dir or "tests/cache")
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Real RSS feeds for testing (from CLAUDE.md)
        self.real_feeds = {
            "bridge": "https://feeds.simplecast.com/imTmqqal",
            "anchor": "https://anchor.fm/s/e8e55a68/podcast/rss",
            "simplification": "https://thegreatsimplification.libsyn.com/rss",
            "movement": "https://feeds.megaphone.fm/movementmemos",
            "kultural": "https://feed.podbean.com/kultural/feed.xml"
        }

    def get_feed_data(self, feed_name: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Get RSS feed data with optional caching.

        Args:
            feed_name: Name from real_feeds dict or direct URL
            use_cache: Whether to use cached data if available

        Returns:
            Parsed feed data

        Raises:
            ValueError: If feed_name not found and not a URL
            RuntimeError: If both cache and real feed fail
        """
        # Determine feed URL
        if feed_name in self.real_feeds:
            feed_url = self.real_feeds[feed_name]
        elif feed_name.startswith(('http://', 'https://')):
            feed_url = feed_name
        else:
            raise ValueError(f"Unknown feed name: {feed_name}. Use one of {list(self.real_feeds.keys())} or provide URL")

        # Check cache if enabled
        if use_cache:
            cached_data = self._get_cached_feed(feed_url)
            if cached_data:
                print(f"✅ Using cached data for {feed_name} (age: {cached_data['age_hours']:.1f}h)")
                return cached_data['data']

        # Fetch real data
        try:
            print(f"🌐 Fetching real RSS data for {feed_name}")
            feed_data = self._fetch_real_feed(feed_url)

            # Cache the result if caching enabled
            if use_cache:
                self._cache_feed_data(feed_url, feed_data)

            return feed_data

        except Exception as e:
            # Last resort: try cache even if expired
            cached_data = self._get_cached_feed(feed_url, ignore_ttl=True)
            if cached_data:
                print(f"⚠️  Using expired cache for {feed_name} due to fetch error: {e}")
                return cached_data['data']
            raise RuntimeError(f"Failed to fetch {feed_name} and no cache available: {e}")

    def get_sample_episodes(self, feed_name: str, count: int = 5, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        Get sample episodes from a real RSS feed.

        Args:
            feed_name: Feed name or URL
            count: Number of episodes to return
            use_cache: Whether to use cached data

        Returns:
            List of episode data dictionaries
        """
        feed_data = self.get_feed_data(feed_name, use_cache)
        episodes = []

        for entry in feed_data.get('entries', [])[:count]:
            # Extract audio URL
            audio_url = None
            for enclosure in entry.get('enclosures', []):
                if enclosure.get('type', '').startswith('audio/'):
                    audio_url = enclosure.get('href')
                    break

            episodes.append({
                'guid': entry.get('id', entry.get('guid', '')),
                'title': entry.get('title', ''),
                'description': entry.get('summary', entry.get('description', '')),
                'published_date': entry.get('published_parsed'),
                'audio_url': audio_url,
                'duration': self._parse_duration(entry.get('itunes_duration')),
                'feed_title': feed_data.get('feed', {}).get('title', '')
            })

        return episodes

    def clear_cache(self, feed_name: Optional[str] = None):
        """Clear cached data for specific feed or all feeds."""
        if feed_name:
            cache_file = self._get_cache_file_path(self.real_feeds.get(feed_name, feed_name))
            if cache_file.exists():
                cache_file.unlink()
                print(f"🗑️  Cleared cache for {feed_name}")
        else:
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
            print("🗑️  Cleared all test data cache")

    def cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats = {
            'cache_dir': str(self.cache_dir),
            'ttl_hours': self.cache_ttl.total_seconds() / 3600,
            'files': [],
            'total_size_kb': 0
        }

        for cache_file in self.cache_dir.glob("*.json"):
            stat = cache_file.stat()
            age_hours = (time.time() - stat.st_mtime) / 3600
            size_kb = stat.st_size / 1024

            stats['files'].append({
                'file': cache_file.name,
                'age_hours': age_hours,
                'size_kb': size_kb,
                'expired': age_hours > self.cache_ttl.total_seconds() / 3600
            })
            stats['total_size_kb'] += size_kb

        return stats

    def _fetch_real_feed(self, feed_url: str) -> Dict[str, Any]:
        """Fetch real RSS feed data."""
        # First check if URL is reachable
        response = requests.get(feed_url, timeout=10)
        response.raise_for_status()

        # Parse RSS feed
        parsed = feedparser.parse(feed_url)
        if parsed.bozo:
            print(f"⚠️  RSS feed has warnings: {parsed.bozo_exception}")

        return {
            'feed': dict(parsed.feed),
            'entries': [dict(entry) for entry in parsed.entries],
            'version': parsed.version,
            'bozo': parsed.bozo,
            'status': getattr(parsed, 'status', None),
            'fetched_at': datetime.now().isoformat()
        }

    def _get_cached_feed(self, feed_url: str, ignore_ttl: bool = False) -> Optional[Dict[str, Any]]:
        """Get cached feed data if valid."""
        cache_file = self._get_cache_file_path(feed_url)

        if not cache_file.exists():
            return None

        try:
            with cache_file.open() as f:
                cached = json.load(f)

            # Check age
            cached_time = datetime.fromisoformat(cached['cached_at'])
            age = datetime.now() - cached_time

            if not ignore_ttl and age > self.cache_ttl:
                return None

            return {
                'data': cached['data'],
                'age_hours': age.total_seconds() / 3600
            }

        except Exception as e:
            print(f"⚠️  Failed to read cache for {feed_url}: {e}")
            return None

    def _cache_feed_data(self, feed_url: str, feed_data: Dict[str, Any]):
        """Cache feed data to disk."""
        try:
            cache_file = self._get_cache_file_path(feed_url)

            cached_data = {
                'feed_url': feed_url,
                'cached_at': datetime.now().isoformat(),
                'data': feed_data
            }

            with cache_file.open('w') as f:
                json.dump(cached_data, f, indent=2, default=str)

        except Exception as e:
            print(f"⚠️  Failed to cache data for {feed_url}: {e}")

    def _get_cache_file_path(self, feed_url: str) -> Path:
        """Get cache file path for feed URL."""
        # Create hash of URL for filename
        url_hash = hashlib.md5(feed_url.encode()).hexdigest()[:12]
        return self.cache_dir / f"feed_{url_hash}.json"

    def _parse_duration(self, duration_str: Optional[str]) -> Optional[int]:
        """Parse iTunes duration to seconds."""
        if not duration_str:
            return None

        try:
            # Handle formats like "1:23:45" or "23:45" or "45"
            parts = str(duration_str).split(':')
            if len(parts) == 3:  # H:M:S
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            elif len(parts) == 2:  # M:S
                return int(parts[0]) * 60 + int(parts[1])
            else:  # Just seconds
                return int(parts[0])
        except (ValueError, IndexError):
            return None


# Global cache instance for test use
test_cache = TestDataCache()


def get_real_feed_data(feed_name: str = "bridge", use_cache: bool = True) -> Dict[str, Any]:
    """
    Convenience function to get real RSS feed data for tests.

    Args:
        feed_name: One of bridge, anchor, simplification, movement, kultural
        use_cache: Whether to use cached data for performance

    Returns:
        Real RSS feed data (cached or fresh)
    """
    return test_cache.get_feed_data(feed_name, use_cache)


def get_real_episode_data(feed_name: str = "bridge", count: int = 3, use_cache: bool = True) -> List[Dict[str, Any]]:
    """
    Convenience function to get real episode data for tests.

    Args:
        feed_name: Feed name to use
        count: Number of episodes to return
        use_cache: Whether to use cached data

    Returns:
        List of real episode data
    """
    return test_cache.get_sample_episodes(feed_name, count, use_cache)