"""
YouTube Video Discovery System.
Discovers new videos from channels with filtering and health monitoring.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import yt_dlp
from dataclasses import dataclass

from ..database.models import Channel, Episode
from .channel_resolver import validate_channel_id

logger = logging.getLogger(__name__)

@dataclass
class VideoInfo:
    """Contains discovered video information"""
    video_id: str
    title: str
    description: str
    published_date: datetime
    duration_seconds: int
    channel_id: str
    channel_name: str
    thumbnail_url: Optional[str] = None
    view_count: Optional[int] = None

class VideoDiscovery:
    """
    Discovers videos from YouTube channels with filtering capabilities.
    Filters out videos shorter than minimum duration (excludes YouTube shorts).
    """
    
    def __init__(self, min_duration_seconds: int = 180):  # 3 minutes default
        self.min_duration_seconds = min_duration_seconds
        
        # Configure yt-dlp for video discovery - optimized for speed
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': 'in_playlist',  # Faster, get basic info then fetch details as needed
            'skip_download': True,
            'ignoreerrors': True,
            'writesubtitles': False,
            'writeautomaticsub': False,
            'socket_timeout': 30,  # 30 second timeout
            'playlist_items': '1-20',  # Limit to first 20 videos for speed
        }
    
    def discover_recent_videos(self, channel: Channel, days_back: int = 1) -> List[VideoInfo]:
        """
        Discover recent videos from a channel within the specified time window.
        
        Args:
            channel: Channel object to discover videos from
            days_back: Number of days to look back for new videos
            
        Returns:
            List of VideoInfo objects for videos meeting criteria
        """
        if not channel.active:
            logger.warning(f"Skipping inactive channel: {channel.channel_name}")
            return []
        
        # Validate channel still exists
        if not validate_channel_id(channel.channel_id):
            logger.error(f"Channel {channel.channel_id} ({channel.channel_name}) is no longer accessible")
            return []
        
        try:
            channel_url = f"https://www.youtube.com/channel/{channel.channel_id}/videos"
            cutoff_date = datetime.now() - timedelta(days=days_back)
            
            logger.info(f"Discovering videos for {channel.channel_name} since {cutoff_date.strftime('%Y-%m-%d %H:%M')}")
            
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                # Extract playlist info (recent videos)
                playlist_info = ydl.extract_info(channel_url, download=False)
                
                if not playlist_info or 'entries' not in playlist_info:
                    logger.warning(f"No entries found for channel: {channel.channel_name}")
                    return []
                
                videos = []
                processed_count = 0
                
                for entry in playlist_info['entries']:
                    if not entry:
                        continue
                    
                    processed_count += 1
                    
                    # Extract video information
                    video_info = self._extract_video_info(entry, channel)
                    if not video_info:
                        continue
                    
                    # Check if video is within time window
                    if video_info.published_date < cutoff_date:
                        logger.debug(f"Video {video_info.video_id} is older than cutoff date, stopping discovery")
                        break
                    
                    # Apply duration filter (exclude shorts)
                    if video_info.duration_seconds < self.min_duration_seconds:
                        logger.debug(f"Skipping short video {video_info.video_id} ({video_info.duration_seconds}s < {self.min_duration_seconds}s)")
                        continue
                    
                    videos.append(video_info)
                    logger.debug(f"Discovered video: {video_info.title} ({video_info.duration_seconds}s)")
                    
                    # Safety limit to prevent excessive API calls
                    if processed_count >= 50:
                        logger.warning(f"Processed {processed_count} videos for {channel.channel_name}, stopping to prevent rate limits")
                        break
                
                logger.info(f"Discovered {len(videos)} qualifying videos for {channel.channel_name}")
                return videos
                
        except Exception as e:
            logger.error(f"Failed to discover videos for channel {channel.channel_name}: {e}")
            return []
    
    def _extract_video_info(self, entry: Dict[str, Any], channel: Channel) -> Optional[VideoInfo]:
        """Extract video information from yt-dlp entry"""
        try:
            video_id = entry.get('id')
            if not video_id:
                return None
            
            # If we have flat extraction, we need to fetch full details for duration
            if entry.get('_type') == 'url' or not entry.get('duration'):
                video_info = self._fetch_video_details(video_id)
                if not video_info:
                    logger.debug(f"Could not fetch details for video {video_id}")
                    return None
                entry.update(video_info)
            
            title = entry.get('title', 'Unknown Title')
            description = entry.get('description', '')
            duration = entry.get('duration')
            
            # Parse upload date
            upload_date = entry.get('upload_date')
            if upload_date:
                try:
                    published_date = datetime.strptime(upload_date, '%Y%m%d')
                except ValueError:
                    # Try timestamp format
                    timestamp = entry.get('timestamp')
                    if timestamp:
                        published_date = datetime.fromtimestamp(timestamp)
                    else:
                        logger.warning(f"Could not parse upload date for video {video_id}")
                        return None
            else:
                logger.warning(f"No upload date found for video {video_id}")
                return None
            
            # Duration is required for filtering
            if duration is None:
                logger.debug(f"No duration found for video {video_id}, skipping")
                return None
            
            return VideoInfo(
                video_id=video_id,
                title=title,
                description=description or '',
                published_date=published_date,
                duration_seconds=duration,
                channel_id=channel.channel_id,
                channel_name=channel.channel_name,
                thumbnail_url=entry.get('thumbnail'),
                view_count=entry.get('view_count')
            )
            
        except Exception as e:
            logger.error(f"Failed to extract video info from entry: {e}")
            return None
    
    def _fetch_video_details(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Fetch full video details when needed"""
        try:
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                return info
        except Exception as e:
            logger.debug(f"Failed to fetch video details for {video_id}: {e}")
            return None
    
    def check_video_exists(self, video_id: str) -> bool:
        """Check if a video exists and is accessible"""
        try:
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                return info is not None and info.get('id') == video_id
        except Exception:
            return False
    
    def get_video_details(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information for a specific video"""
        try:
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                return info
        except Exception as e:
            logger.error(f"Failed to get video details for {video_id}: {e}")
            return None

class ChannelHealthMonitor:
    """
    Monitors channel health and tracks failures.
    Flags channels with consecutive failures for review.
    """
    
    def __init__(self, failure_threshold: int = 3):
        self.failure_threshold = failure_threshold
    
    def record_success(self, channel_repo, channel_id: str):
        """Record successful video discovery for a channel"""
        try:
            channel_repo.reset_failures(channel_id)
            channel_repo.update_last_checked(channel_id)
            logger.debug(f"Recorded success for channel {channel_id}")
        except Exception as e:
            logger.error(f"Failed to record success for channel {channel_id}: {e}")
    
    def record_failure(self, channel_repo, channel_id: str, failure_reason: str):
        """Record failed video discovery for a channel"""
        try:
            channel_repo.increment_failures(channel_id, failure_reason)
            channel_repo.update_last_checked(channel_id)
            
            # Check if channel should be flagged
            channel = channel_repo.get_by_id(channel_id)
            if channel and channel.consecutive_failures >= self.failure_threshold:
                logger.warning(f"Channel {channel.channel_name} has {channel.consecutive_failures} consecutive failures - flagging for review")
                # Could add notification or email alert here
                
        except Exception as e:
            logger.error(f"Failed to record failure for channel {channel_id}: {e}")
    
    def get_unhealthy_channels(self, channel_repo) -> List[Channel]:
        """Get channels that need attention due to repeated failures"""
        try:
            return channel_repo.get_unhealthy_channels(self.failure_threshold)
        except Exception as e:
            logger.error(f"Failed to get unhealthy channels: {e}")
            return []
    
    def should_check_channel(self, channel: Channel, min_check_interval_hours: int = 1) -> bool:
        """
        Determine if a channel should be checked based on last check time and health.
        
        Args:
            channel: Channel to evaluate
            min_check_interval_hours: Minimum hours between checks
            
        Returns:
            True if channel should be checked
        """
        if not channel.active:
            return False
        
        # Always check if never checked before
        if not channel.last_checked:
            return True
        
        # Check time-based interval
        time_since_check = datetime.now() - channel.last_checked
        min_interval = timedelta(hours=min_check_interval_hours)
        
        if time_since_check < min_interval:
            return False
        
        # Skip channels with too many consecutive failures (but log it)
        if channel.consecutive_failures >= self.failure_threshold:
            logger.debug(f"Skipping unhealthy channel {channel.channel_name} ({channel.consecutive_failures} failures)")
            return False
        
        return True

def discover_videos_for_channel(channel: Channel, days_back: int = 1, 
                              min_duration_seconds: int = 180) -> List[VideoInfo]:
    """
    Convenience function to discover videos for a single channel.
    
    Args:
        channel: Channel to discover videos from
        days_back: Number of days to look back
        min_duration_seconds: Minimum video duration in seconds
        
    Returns:
        List of VideoInfo objects
    """
    discovery = VideoDiscovery(min_duration_seconds)
    return discovery.discover_recent_videos(channel, days_back)