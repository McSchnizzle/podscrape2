#!/usr/bin/env python3
"""
Discovery Phase Script - RSS Feed Discovery
Independent script for Phase 1: Find unprocessed episodes from RSS feeds
Outputs JSON summary for consumption by orchestrator or manual review.
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
import argparse

# Add src to path - handle both direct execution and orchestrator calls
script_dir = Path(__file__).parent
project_root = script_dir.parent
src_dir = project_root / 'src'

# Add both src and project root to path to handle different import scenarios
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Set up environment
from dotenv import load_dotenv
load_dotenv()

# Try different import approaches
try:
    from src.config.env import require_database_url
except ImportError:
    from config.env import require_database_url

require_database_url()

# Import database models with fallback
try:
    from src.database.models import get_episode_repo, get_feed_repo, Episode
except ImportError:
    from database.models import get_episode_repo, get_feed_repo, Episode

import feedparser
import requests

# Import centralized logging
try:
    from src.utils.logging_config import setup_phase_logging
except ImportError:
    from utils.logging_config import setup_phase_logging

class DiscoveryRunner:
    """RSS feed discovery phase"""

    def __init__(self, dry_run: bool = False, limit: int = None, days_back: int = 7,
                 episode_guid: str = None, verbose: bool = False):
        # Set up phase-specific logging
        self.pipeline_logger = setup_phase_logging("discovery", verbose=verbose, console_output=True)
        self.logger = self.pipeline_logger.get_logger()

        self.dry_run = dry_run
        self.episode_guid = episode_guid
        self.verbose = verbose

        # Load web settings for defaults if not explicitly provided
        try:
            from src.config.web_config import WebConfigManager
            web_config = WebConfigManager()

            # Apply web settings if no explicit CLI values provided
            if limit is None:
                limit = int(web_config.get_setting('pipeline', 'max_episodes_per_run', 3))
            if days_back == 7:  # Default value, check web config
                days_back = int(web_config.get_setting('pipeline', 'discovery_lookback_days', 7))

        except Exception as e:
            self.logger.warning(f"Could not load web config, using defaults: {e}")
            if limit is None:
                limit = 3
            if days_back is None:
                days_back = 7

        self.limit = limit
        self.days_back = days_back

        # Initialize repositories
        self.episode_repo = get_episode_repo()
        self.feed_repo = get_feed_repo()

        # Load feeds from database
        self.rss_feeds = self._load_feeds_from_database()

        self.logger.info(f"Discovery initialized with {len(self.rss_feeds)} RSS feeds")

    def _load_feeds_from_database(self):
        """Load active RSS feeds from database"""
        try:
            feeds = self.feed_repo.get_active_feeds()

            feed_list = []
            for feed in feeds:
                # Skip YouTube channels and other problematic feeds
                if isinstance(feed.feed_url, str):
                    if ('youtube.com' in feed.feed_url or
                        'youtu.be' in feed.feed_url or
                        feed.feed_url.startswith('https://www.youtube.com/@')):
                        self.logger.info(f"SKIP: {feed.title} (YouTube feed not supported)")
                        continue

                    # Skip feeds with known issues
                    problematic_patterns = [
                        'shows.acast.com/the-hopeful-majority',    # SSL/404 errors
                        'feeds.megaphone.fm/thegrayarea',          # 404 errors
                        'psychedelic-wayfinder',                   # Malformed XML
                        'rss.com/podcasts/psychedelic-wayfinder'   # Malformed XML
                    ]

                    if any(pattern in feed.feed_url for pattern in problematic_patterns):
                        self.logger.info(f"SKIP: {feed.title} (feed has known issues)")
                        continue
                feed_list.append({
                    'id': feed.id,
                    'url': feed.feed_url,
                    'name': feed.title
                })

            return feed_list
        except Exception as e:
            self.logger.error(f"Failed to load feeds from database: {e}")
            return []

    def discover_episodes(self):
        """Find unprocessed episodes"""

        # Handle specific episode GUID
        if self.episode_guid:
            self.logger.info(f"Looking for specific episode: {self.episode_guid}")
            episode = self.episode_repo.get_by_episode_guid(self.episode_guid)
            if episode:
                self.logger.info(f"Found episode: {episode.title}")
                return {
                    'success': True,
                    'episodes_found': 1,
                    'episodes': [{
                        'guid': episode.episode_guid,
                        'title': episode.title,
                        'feed_name': 'Unknown',  # We don't have feed name in episode record
                        'status': episode.status,
                        'published_date': episode.published_date.isoformat() if episode.published_date else None,
                        'audio_url': episode.audio_url,
                        'mode': 'resume'
                    }]
                }
            else:
                return {
                    'success': False,
                    'error': f"Episode with GUID {self.episode_guid} not found",
                    'episodes_found': 0,
                    'episodes': []
                }

        # Standard discovery
        max_episodes = self.limit or 3
        discovered_episodes = []

        self.logger.info(f"Scanning feeds for new episodes (max {max_episodes}, {self.days_back} days back)")

        headers = {
            'User-Agent': 'PodcastDigest/1.0 (+https://github.com/McSchnizzle/podscrape2)'
        }

        for feed_info in self.rss_feeds:
            # Stop if we have enough episodes
            if len(discovered_episodes) >= max_episodes:
                break

            feed_url = feed_info['url']
            feed_name = feed_info['name']

            self.logger.info(f"Checking {feed_name}: {feed_url}")

            # Mark feed as checked
            try:
                if feed_info.get('id'):
                    self.feed_repo.update_last_checked(int(feed_info['id']), datetime.now())
            except Exception as e:
                self.logger.warning(f"Failed to update last_checked for feed {feed_info['id']}: {e}")

            try:
                # Fetch feed with requests first, fallback to direct parse
                feed = None
                try:
                    resp = requests.get(feed_url, timeout=12, headers=headers)
                    resp.raise_for_status()
                    feed = feedparser.parse(resp.content)
                except Exception as e:
                    self.logger.warning(f"Fetch via requests failed ({e}); trying direct parse")
                    feed = feedparser.parse(feed_url)

                # Check for parser issues
                if getattr(feed, 'bozo', 0):
                    self.logger.warning(f"Parser flagged feed as bozo: {getattr(feed, 'bozo_exception', None)}")

                if not getattr(feed, 'entries', None):
                    self.logger.warning(f"No entries found in {feed_name}")
                    continue

                self.logger.info(f"Found {len(feed.entries)} episodes in feed")

                # Check recent episodes
                cutoff_date = datetime.now() - timedelta(days=self.days_back)

                for i, entry in enumerate(feed.entries[:10]):
                    # Get episode GUID
                    episode_guid = entry.get('id') or entry.get('guid') or getattr(entry, 'link', f"episode_{i}_{feed_name}")
                    title = entry.get('title', 'Untitled')

                    # Parse published date
                    published_date = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        published_date = datetime(*entry.published_parsed[:6])
                    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                        published_date = datetime(*entry.updated_parsed[:6])
                    else:
                        published_date = datetime.now()

                    # Skip old episodes
                    if published_date < cutoff_date:
                        self.logger.info(f"SKIP: {title[:50]}... (older than {self.days_back} days)")
                        continue

                    # Check if already processed
                    existing = self.episode_repo.get_by_episode_guid(episode_guid)
                    if existing and existing.status in ['transcribed', 'scored', 'digested', 'not_relevant']:
                        self.logger.info(f"SKIP: {title[:60]}... (already processed)")
                        continue
                    elif existing and existing.status in ['pending', 'failed', 'downloading']:
                        self.logger.info(f"RESUME: {title[:60]}... ({existing.status})")
                        discovered_episodes.append({
                            'guid': episode_guid,
                            'title': title,
                            'feed_name': feed_name,
                            'feed_id': feed_info.get('id'),
                            'status': existing.status,
                            'published_date': published_date.isoformat(),
                            'audio_url': existing.audio_url,
                            'mode': 'resume'
                        })
                        break  # One per feed

                    # Find audio URL for new episodes
                    audio_url = None
                    for link in entry.get('links', []):
                        if link.get('type', '').startswith('audio/'):
                            audio_url = link['href']
                            break

                    if not audio_url and hasattr(entry, 'enclosures'):
                        for enclosure in entry.enclosures:
                            if enclosure.type.startswith('audio/'):
                                audio_url = enclosure.href
                                break

                    if not audio_url:
                        self.logger.info(f"SKIP: {title[:60]}... (no audio URL)")
                        continue

                    # Found new episode
                    self.logger.info(f"NEW: {title}")
                    discovered_episodes.append({
                        'guid': episode_guid,
                        'title': title,
                        'description': entry.get('summary', '')[:500],
                        'audio_url': audio_url,
                        'published_date': published_date.isoformat(),
                        'duration_seconds': None,
                        'feed_name': feed_name,
                        'feed_id': feed_info.get('id'),
                        'mode': 'new'
                    })
                    break  # One per feed

            except Exception as e:
                self.logger.error(f"Error parsing {feed_name}: {e}")
                continue

        return {
            'success': True,
            'episodes_found': len(discovered_episodes),
            'episodes': discovered_episodes
        }

def main():
    parser = argparse.ArgumentParser(description='RSS Episode Discovery Phase')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be processed')
    parser.add_argument('--limit', type=int, help='Limit number of episodes', default=None)
    parser.add_argument('--days-back', type=int, help='Days back to search', default=7)
    parser.add_argument('--episode-guid', help='Process specific episode by GUID')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    parser.add_argument('--output', help='Output JSON file (default: stdout)')

    args = parser.parse_args()

    try:
        runner = DiscoveryRunner(
            dry_run=args.dry_run,
            limit=args.limit,
            days_back=args.days_back,
            episode_guid=args.episode_guid,
            verbose=args.verbose
        )

        result = runner.discover_episodes()

        # Output JSON
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(result, f, indent=2)
        else:
            # Output JSON on single line for orchestrator compatibility
            print(json.dumps(result))
            sys.stdout.flush()  # Ensure JSON output is flushed

        # Exit code
        sys.exit(0 if result['success'] else 1)

    except Exception as e:
        error_result = {
            'success': False,
            'error': str(e),
            'episodes_found': 0,
            'episodes': []
        }

        if args.output:
            with open(args.output, 'w') as f:
                json.dump(error_result, f, indent=2)
        else:
            # Output JSON on single line for orchestrator compatibility
            print(json.dumps(error_result))
            sys.stdout.flush()  # Ensure JSON output is flushed

        sys.exit(1)

if __name__ == '__main__':
    main()
