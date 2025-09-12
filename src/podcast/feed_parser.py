#!/usr/bin/env python3
"""
RSS Podcast Feed Parser
Handles parsing RSS feeds to discover episodes and metadata.
"""

import feedparser
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse
import re

from ..utils.error_handling import retry_with_backoff, PodcastError
from email.utils import parsedate_to_datetime
from ..utils.logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class PodcastEpisode:
    """Represents a single podcast episode from RSS feed"""
    guid: str
    title: str
    description: str
    published_date: datetime
    duration_seconds: Optional[int]
    audio_url: str
    audio_type: str
    audio_size: Optional[int]
    episode_url: Optional[str] = None

@dataclass
class PodcastFeed:
    """Represents a podcast feed with metadata"""
    url: str
    title: str
    description: str
    language: Optional[str]
    author: Optional[str]
    image_url: Optional[str]
    episodes: List[PodcastEpisode]

class FeedParser:
    """RSS podcast feed parser with error handling and validation"""
    
    def __init__(self, user_agent: str = "RSS Podcast Digest Bot 1.0"):
        self.user_agent = user_agent
        # Configure feedparser
        feedparser.USER_AGENT = user_agent
    
    @retry_with_backoff(max_retries=3, backoff_factor=2.0)
    def parse_feed(self, feed_url: str) -> PodcastFeed:
        """
        Parse RSS feed and extract podcast metadata and episodes
        
        Args:
            feed_url: RSS feed URL to parse
            
        Returns:
            PodcastFeed object with metadata and episodes
            
        Raises:
            PodcastError: If feed parsing fails
        """
        logger.info(f"Parsing RSS feed: {feed_url}")
        
        try:
            # Parse the feed
            feed = feedparser.parse(feed_url)
            
            # Check for feed errors
            if hasattr(feed, 'bozo') and feed.bozo:
                if hasattr(feed, 'bozo_exception'):
                    logger.warning(f"Feed parsing warning for {feed_url}: {feed.bozo_exception}")
            
            if not feed.feed:
                raise PodcastError(f"No feed data found at {feed_url}")
            
            # Extract feed metadata
            feed_title = feed.feed.get('title', 'Unknown Podcast')
            feed_description = feed.feed.get('description', feed.feed.get('subtitle', ''))
            feed_language = feed.feed.get('language')
            feed_author = feed.feed.get('author', feed.feed.get('itunes_author'))
            feed_image = self._extract_image_url(feed.feed)
            
            # Parse episodes
            episodes = []
            for entry in feed.entries[:5]:  # Limit to recent 5 episodes
                try:
                    episode = self._parse_episode(entry)
                    if episode:
                        episodes.append(episode)
                except Exception as e:
                    logger.warning(f"Failed to parse episode '{entry.get('title', 'Unknown')}': {e}")
                    continue
            
            logger.info(f"Successfully parsed feed '{feed_title}' with {len(episodes)} episodes")
            
            return PodcastFeed(
                url=feed_url,
                title=feed_title,
                description=feed_description,
                language=feed_language,
                author=feed_author,
                image_url=feed_image,
                episodes=episodes
            )
            
        except Exception as e:
            error_msg = f"Failed to parse RSS feed {feed_url}: {e}"
            logger.error(error_msg)
            raise PodcastError(error_msg) from e
    
    def _parse_episode(self, entry: Dict) -> Optional[PodcastEpisode]:
        """Parse a single RSS episode entry"""
        
        # Extract basic metadata
        guid = entry.get('id') or entry.get('guid') or entry.get('link')
        if not guid:
            logger.warning("Episode missing GUID/ID, skipping")
            return None
        
        title = entry.get('title', 'Untitled Episode')
        description = entry.get('description', entry.get('summary', ''))
        
        # Parse published date
        published_date = self._parse_date(entry)
        if not published_date:
            logger.warning(f"Episode '{title}' missing valid published date, skipping")
            return None
        
        # Find audio enclosure
        audio_info = self._find_audio_enclosure(entry)
        if not audio_info:
            logger.warning(f"Episode '{title}' missing audio enclosure, skipping")
            return None
        
        audio_url, audio_type, audio_size = audio_info
        
        # Parse duration
        duration_seconds = self._parse_duration(entry)
        
        # Get episode URL
        episode_url = entry.get('link')
        
        return PodcastEpisode(
            guid=str(guid),
            title=title,
            description=description,
            published_date=published_date,
            duration_seconds=duration_seconds,
            audio_url=audio_url,
            audio_type=audio_type,
            audio_size=audio_size,
            episode_url=episode_url
        )
    
    def _parse_date(self, entry: Dict) -> Optional[datetime]:
        """Parse published date from episode entry"""
        date_fields = ['published_parsed', 'updated_parsed']
        
        for field in date_fields:
            if field in entry and entry[field]:
                try:
                    time_struct = entry[field]
                    return datetime(*time_struct[:6], tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    continue
        
        # Try string parsing as fallback using public stdlib
        date_strings = [entry.get('published'), entry.get('updated')]
        for date_str in date_strings:
            if date_str:
                try:
                    dt = parsedate_to_datetime(date_str)
                    if dt is not None:
                        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
                except Exception:
                    continue
        
        return None
    
    def _find_audio_enclosure(self, entry: Dict) -> Optional[Tuple[str, str, Optional[int]]]:
        """Find audio enclosure in episode entry"""
        
        # Check enclosures first
        if hasattr(entry, 'enclosures') and entry.enclosures:
            for enclosure in entry.enclosures:
                enc_type = enclosure.get('type', '').lower()
                if enc_type and 'audio' in enc_type:
                    url = enclosure.get('url') or enclosure.get('href')
                    size = enclosure.get('length')
                    if size:
                        try:
                            size = int(size)
                        except (ValueError, TypeError):
                            size = None
                    
                    if url:
                        return url, enc_type, size
        
        # Check links as fallback
        if hasattr(entry, 'links'):
            for link in entry.links:
                link_type = link.get('type', '').lower()
                if link_type and 'audio' in link_type:
                    url = link.get('href')
                    if url:
                        return url, link_type, None
        
        return None
    
    def _parse_duration(self, entry: Dict) -> Optional[int]:
        """Parse episode duration in seconds"""
        
        # Check iTunes duration first
        itunes_duration = entry.get('itunes_duration')
        if itunes_duration:
            try:
                return self._parse_duration_string(itunes_duration)
            except:
                pass
        
        # Check other duration fields
        duration_fields = ['duration', 'length']
        for field in duration_fields:
            if field in entry:
                try:
                    duration = entry[field]
                    if isinstance(duration, (int, float)):
                        return int(duration)
                    elif isinstance(duration, str):
                        return self._parse_duration_string(duration)
                except:
                    continue
        
        return None
    
    def _parse_duration_string(self, duration_str: str) -> int:
        """Parse duration string to seconds"""
        duration_str = str(duration_str).strip()
        
        # Format: HH:MM:SS or MM:SS or just seconds
        if ':' in duration_str:
            parts = duration_str.split(':')
            if len(parts) == 3:  # HH:MM:SS
                hours, minutes, seconds = map(int, parts)
                return hours * 3600 + minutes * 60 + seconds
            elif len(parts) == 2:  # MM:SS
                minutes, seconds = map(int, parts)
                return minutes * 60 + seconds
        else:
            # Just seconds
            return int(float(duration_str))
        
        raise ValueError(f"Invalid duration format: {duration_str}")
    
    def _extract_image_url(self, feed_data: Dict) -> Optional[str]:
        """Extract podcast image URL from feed"""
        
        # Check iTunes image first
        itunes_image = feed_data.get('itunes_image')
        if itunes_image:
            if isinstance(itunes_image, dict):
                return itunes_image.get('href')
            elif isinstance(itunes_image, str):
                return itunes_image
        
        # Check standard image
        image = feed_data.get('image')
        if image:
            if isinstance(image, dict):
                return image.get('url') or image.get('href')
            elif isinstance(image, str):
                return image
        
        return None
    
    def validate_feed_url(self, url: str) -> bool:
        """Validate that URL looks like a valid RSS feed URL"""
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False
            
            # Should be http/https
            if parsed.scheme not in ['http', 'https']:
                return False
            
            return True
        except:
            return False


def create_feed_parser() -> FeedParser:
    """Factory function to create feed parser"""
    return FeedParser()


# CLI testing function
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python feed_parser.py <rss_url>")
        sys.exit(1)
    
    feed_url = sys.argv[1]
    parser = create_feed_parser()
    
    try:
        feed = parser.parse_feed(feed_url)
        print(f"Feed: {feed.title}")
        print(f"Episodes: {len(feed.episodes)}")
        
        if feed.episodes:
            latest = feed.episodes[0]
            print(f"Latest: '{latest.title}' ({latest.duration_seconds}s)")
            print(f"Audio: {latest.audio_url}")
    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
