"""
YouTube Channel ID Resolution System.
Converts various YouTube channel URL formats and channel names to channel IDs using yt-dlp.
Supports multiple URL formats and provides robust error handling.
"""

import re
import logging
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlparse, parse_qs
import yt_dlp
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ChannelInfo:
    """Contains resolved channel information"""
    channel_id: str
    channel_name: str
    channel_url: str
    subscriber_count: Optional[int] = None
    description: Optional[str] = None
    upload_count: Optional[int] = None

class ChannelResolver:
    """
    Resolves YouTube channel IDs from various input formats:
    - Channel URLs (youtube.com/channel/UCxxx, youtube.com/c/name, youtube.com/@handle)
    - User URLs (youtube.com/user/username)
    - Custom URLs (youtube.com/customname)
    - Channel handles (@channelname)
    - Channel names (searches for exact match)
    """
    
    def __init__(self):
        # Configure yt-dlp to be quiet and efficient
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'skip_download': True,
            'ignoreerrors': True,
        }
    
    def resolve_channel_id(self, input_str: str) -> Optional[ChannelInfo]:
        """
        Main method to resolve any channel input to channel ID and info.
        
        Args:
            input_str: YouTube URL, handle, or channel name
            
        Returns:
            ChannelInfo object with resolved information, None if not found
        """
        if not input_str or not input_str.strip():
            logger.error("Empty input provided to channel resolver")
            return None
        
        input_str = input_str.strip()
        
        # Try different resolution strategies in order of reliability
        strategies = [
            self._resolve_from_channel_url,
            self._resolve_from_user_url, 
            self._resolve_from_custom_url,
            self._resolve_from_handle,
            self._resolve_from_search
        ]
        
        for strategy in strategies:
            try:
                result = strategy(input_str)
                if result:
                    logger.info(f"Successfully resolved '{input_str}' to channel ID: {result.channel_id}")
                    return result
            except Exception as e:
                logger.debug(f"Strategy {strategy.__name__} failed for '{input_str}': {e}")
                continue
        
        logger.error(f"Could not resolve channel ID for input: {input_str}")
        return None
    
    def _resolve_from_channel_url(self, input_str: str) -> Optional[ChannelInfo]:
        """Resolve from direct channel URLs"""
        channel_id = self._extract_channel_id_from_url(input_str)
        if channel_id:
            return self._get_channel_info(f"https://www.youtube.com/channel/{channel_id}")
        return None
    
    def _resolve_from_user_url(self, input_str: str) -> Optional[ChannelInfo]:
        """Resolve from user URLs (youtube.com/user/username)"""
        if 'youtube.com/user/' in input_str:
            return self._fetch_channel_info_ydl(input_str)
        return None
    
    def _resolve_from_custom_url(self, input_str: str) -> Optional[ChannelInfo]:
        """Resolve from custom URLs and @handles"""
        if any(pattern in input_str for pattern in ['youtube.com/c/', 'youtube.com/@', '@']):
            # Handle @username format
            if input_str.startswith('@') and 'youtube.com' not in input_str:
                input_str = f"https://www.youtube.com/@{input_str[1:]}"
            
            return self._fetch_channel_info_ydl(input_str)
        return None
    
    def _resolve_from_handle(self, input_str: str) -> Optional[ChannelInfo]:
        """Resolve from channel handles (@channelname)"""
        if input_str.startswith('@'):
            handle_url = f"https://www.youtube.com/@{input_str[1:]}"
            return self._fetch_channel_info_ydl(handle_url)
        return None
    
    def _resolve_from_search(self, input_str: str) -> Optional[ChannelInfo]:
        """Resolve by searching for channel name (last resort)"""
        # Only try search if input doesn't look like a URL
        if not any(pattern in input_str.lower() for pattern in ['youtube.com', 'youtu.be', 'http', '@']):
            search_url = f"ytsearch1:channel:{input_str}"
            return self._fetch_channel_info_ydl(search_url)
        return None
    
    def _extract_channel_id_from_url(self, url: str) -> Optional[str]:
        """Extract channel ID from various YouTube URL formats"""
        if not url:
            return None
            
        # Direct channel ID patterns
        patterns = [
            r'youtube\.com/channel/([a-zA-Z0-9_-]+)',
            r'youtube\.com/c/([a-zA-Z0-9_-]+)',
            r'youtube\.com/@([a-zA-Z0-9_-]+)',
            r'youtube\.com/user/([a-zA-Z0-9_-]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                channel_identifier = match.group(1)
                
                # If it's already a UC... channel ID, return it
                if channel_identifier.startswith('UC') and len(channel_identifier) == 24:
                    return channel_identifier
                
                # Otherwise, we need to resolve it via yt-dlp
                return None
        
        # Check for channel ID in URL parameters
        try:
            parsed = urlparse(url)
            if parsed.query:
                params = parse_qs(parsed.query)
                if 'channel' in params:
                    return params['channel'][0]
        except Exception:
            pass
        
        return None
    
    def _fetch_channel_info_ydl(self, url: str) -> Optional[ChannelInfo]:
        """Use yt-dlp to extract channel information"""
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                # Try to extract channel info
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    return None
                
                # Handle search results
                if 'entries' in info and info['entries']:
                    info = info['entries'][0]
                
                # Extract channel information
                channel_id = info.get('channel_id') or info.get('uploader_id')
                channel_name = info.get('channel') or info.get('uploader')
                channel_url = info.get('channel_url') or info.get('uploader_url')
                
                if not channel_id or not channel_name:
                    logger.warning(f"Incomplete channel info extracted from: {url}")
                    return None
                
                # Ensure channel_url is properly formatted
                if channel_url and not channel_url.startswith('http'):
                    channel_url = f"https://www.youtube.com/channel/{channel_id}"
                elif not channel_url:
                    channel_url = f"https://www.youtube.com/channel/{channel_id}"
                
                return ChannelInfo(
                    channel_id=channel_id,
                    channel_name=channel_name,
                    channel_url=channel_url,
                    subscriber_count=info.get('subscriber_count'),
                    description=info.get('description'),
                    upload_count=info.get('playlist_count')
                )
                
        except Exception as e:
            logger.debug(f"yt-dlp extraction failed for {url}: {e}")
            return None
    
    def _get_channel_info(self, channel_url: str) -> Optional[ChannelInfo]:
        """Get detailed channel information for a known channel URL"""
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(channel_url, download=False)
                
                if not info:
                    return None
                
                channel_id = info.get('id') or info.get('channel_id')
                channel_name = info.get('title') or info.get('channel')
                
                if not channel_id or not channel_name:
                    return None
                
                return ChannelInfo(
                    channel_id=channel_id,
                    channel_name=channel_name,
                    channel_url=channel_url,
                    subscriber_count=info.get('subscriber_count'),
                    description=info.get('description'),
                    upload_count=info.get('playlist_count')
                )
                
        except Exception as e:
            logger.debug(f"Failed to get channel info for {channel_url}: {e}")
            return None
    
    def validate_channel_exists(self, channel_id: str) -> bool:
        """Validate that a channel ID exists and is accessible"""
        if not channel_id:
            return False
        
        try:
            channel_url = f"https://www.youtube.com/channel/{channel_id}"
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(channel_url, download=False)
                return info is not None and info.get('id') == channel_id
        except Exception:
            return False

# Convenience module-level helpers for legacy callers/tests
def resolve_channel(input_str: str) -> Optional[ChannelInfo]:
    """Resolve a channel input (URL/handle/name) to ChannelInfo or None."""
    try:
        resolver = ChannelResolver()
        return resolver.resolve_channel_id(input_str)
    except Exception:
        return None

def validate_channel_id(channel_id: str) -> bool:
    """Lightweight check whether a channel ID appears valid/reachable."""
    try:
        resolver = ChannelResolver()
        return resolver.validate_channel_exists(channel_id)
    except Exception:
        return False

def resolve_channel(input_str: str) -> Optional[ChannelInfo]:
    """
    Convenience function to resolve a channel from any input format.
    
    Args:
        input_str: YouTube URL, handle, or channel name
        
    Returns:
        ChannelInfo object or None if not found
    """
    resolver = ChannelResolver()
    return resolver.resolve_channel_id(input_str)

def validate_channel_id(channel_id: str) -> bool:
    """
    Convenience function to validate a channel ID exists.
    
    Args:
        channel_id: YouTube channel ID (UC...)
        
    Returns:
        True if channel exists and is accessible
    """
    resolver = ChannelResolver()
    return resolver.validate_channel_exists(channel_id)
