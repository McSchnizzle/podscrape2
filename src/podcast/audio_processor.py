#!/usr/bin/env python3
"""
Audio Processor for Podcast Episodes
Handles downloading, validation, and chunking audio files for transcription.
"""

import os
import hashlib
import logging
from pathlib import Path
from typing import List, Optional, Tuple
import requests
from datetime import datetime
import subprocess
import tempfile

from ..utils.error_handling import retry_with_backoff, PodcastError
from ..utils.logging_config import get_logger

logger = get_logger(__name__)

class AudioProcessor:
    """
    Handles audio file downloading, validation, and chunking for podcast episodes
    """
    
    def __init__(self, 
                 audio_cache_dir: str = "audio_cache",
                 chunk_dir: str = "audio_chunks",
                 chunk_duration_minutes: int = 3):
        """
        Initialize audio processor
        
        Args:
            audio_cache_dir: Directory to cache downloaded audio files
            chunk_dir: Directory for audio chunks
            chunk_duration_minutes: Duration of each audio chunk in minutes
        """
        self.audio_cache_dir = Path(audio_cache_dir)
        self.chunk_dir = Path(chunk_dir)
        self.chunk_duration_seconds = chunk_duration_minutes * 60
        
        # Create directories if they don't exist
        self.audio_cache_dir.mkdir(parents=True, exist_ok=True)
        self.chunk_dir.mkdir(parents=True, exist_ok=True)
        
        # Request session for efficient connection reuse
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'RSS Podcast Digest Bot 1.0 (Audio Processor)'
        })
        
        logger.info(f"AudioProcessor initialized - cache: {self.audio_cache_dir}, chunks: {self.chunk_dir}")
    
    @retry_with_backoff(max_retries=3, backoff_factor=2.0)
    def download_audio(self, audio_url: str, episode_guid: str, 
                      expected_size: Optional[int] = None, 
                      feed_title: Optional[str] = None) -> str:
        """
        Download audio file from URL and save to cache
        
        Args:
            audio_url: URL of audio file to download
            episode_guid: Unique episode identifier for filename
            expected_size: Expected file size in bytes (optional)
            feed_title: RSS feed title for filename (optional)
            
        Returns:
            Path to downloaded audio file
            
        Raises:
            PodcastError: If download fails
        """
        # Generate clean filename with feed keyword + 6-char ID
        if feed_title:
            feed_keyword = self._extract_feed_keyword(feed_title)
        else:
            feed_keyword = "podcast"
        
        # Use first 6 characters of episode GUID as ID
        episode_id = episode_guid.replace('-', '')[:6]
        filename = f"{feed_keyword}-{episode_id}.mp3"
        file_path = self.audio_cache_dir / filename
        
        # Check if file already exists and is valid
        if file_path.exists():
            if self._validate_audio_file(file_path, expected_size):
                logger.info(f"Audio file already exists: {file_path}")
                return str(file_path)
            else:
                logger.warning(f"Existing audio file invalid, re-downloading: {file_path}")
                file_path.unlink()
        
        logger.info(f"Downloading audio: {audio_url} -> {filename}")
        
        try:
            # Stream download for large files
            response = self.session.get(audio_url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if 'audio' not in content_type and 'mpeg' not in content_type:
                logger.warning(f"Unexpected content type: {content_type}")
            
            # Download with progress tracking
            total_size = int(response.headers.get('content-length', 0))
            if expected_size and abs(total_size - expected_size) > expected_size * 0.1:
                logger.warning(f"Size mismatch: expected {expected_size}, got {total_size}")
            
            downloaded_size = 0
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:  # Filter out keep-alive chunks
                        f.write(chunk)
                        downloaded_size += len(chunk)
            
            # Validate downloaded file
            if not self._validate_audio_file(file_path, expected_size):
                file_path.unlink()
                raise PodcastError(f"Downloaded audio file failed validation: {file_path}")
            
            logger.info(f"Successfully downloaded {downloaded_size} bytes to {file_path}")
            return str(file_path)
            
        except requests.RequestException as e:
            error_msg = f"Failed to download audio from {audio_url}: {e}"
            logger.error(error_msg)
            if file_path.exists():
                file_path.unlink()
            raise PodcastError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error downloading {audio_url}: {e}"
            logger.error(error_msg)
            if file_path.exists():
                file_path.unlink()
            raise PodcastError(error_msg) from e
    
    def chunk_audio(self, audio_file_path: str, episode_guid: str) -> List[str]:
        """
        Split audio file into chunks for processing
        
        Args:
            audio_file_path: Path to source audio file
            episode_guid: Episode identifier for chunk naming
            
        Returns:
            List of paths to audio chunks
            
        Raises:
            PodcastError: If chunking fails
        """
        audio_path = Path(audio_file_path)
        if not audio_path.exists():
            raise PodcastError(f"Audio file not found: {audio_file_path}")
        
        # Create episode chunk directory using same naming convention
        episode_id = episode_guid.replace('-', '')[:6]
        chunk_episode_dir = self.chunk_dir / episode_id
        chunk_episode_dir.mkdir(exist_ok=True)
        
        logger.info(f"Chunking audio file: {audio_file_path}")
        
        try:
            # Get audio duration first
            duration = self._get_audio_duration(audio_file_path)
            if duration <= self.chunk_duration_seconds:
                # File is shorter than chunk size, just copy it
                chunk_path = chunk_episode_dir / f"{episode_id}_chunk_001.mp3"
                self._copy_file(audio_file_path, str(chunk_path))
                logger.info(f"Audio shorter than chunk size, copied as single chunk: {chunk_path}")
                return [str(chunk_path)]
            
            # Split into chunks using FFmpeg
            chunk_paths = []
            num_chunks = int((duration + self.chunk_duration_seconds - 1) // self.chunk_duration_seconds)
            
            for chunk_num in range(num_chunks):
                start_time = chunk_num * self.chunk_duration_seconds
                chunk_filename = f"{episode_id}_chunk_{chunk_num+1:03d}.mp3"
                chunk_path = chunk_episode_dir / chunk_filename
                
                # FFmpeg command to extract chunk
                cmd = [
                    'ffmpeg', '-y',  # -y to overwrite existing files
                    '-i', str(audio_path),
                    '-ss', str(start_time),
                    '-t', str(self.chunk_duration_seconds),
                    '-acodec', 'libmp3lame',
                    '-ar', '16000',  # 16kHz sample rate for ASR
                    '-ac', '1',      # Mono for ASR
                    '-q:a', '2',     # High quality
                    str(chunk_path)
                ]
                
                logger.debug(f"Running FFmpeg: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    error_msg = f"FFmpeg failed for chunk {chunk_num+1}: {result.stderr}"
                    logger.error(error_msg)
                    raise PodcastError(error_msg)
                
                if not chunk_path.exists() or chunk_path.stat().st_size == 0:
                    logger.warning(f"Empty or missing chunk: {chunk_path}")
                    continue
                
                chunk_paths.append(str(chunk_path))
                logger.debug(f"Created chunk {chunk_num+1}/{num_chunks}: {chunk_path}")
            
            logger.info(f"Successfully created {len(chunk_paths)} audio chunks for {episode_guid}")
            return chunk_paths
            
        except subprocess.CalledProcessError as e:
            error_msg = f"Audio chunking failed for {episode_guid}: {e}"
            logger.error(error_msg)
            raise PodcastError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error chunking audio {episode_guid}: {e}"
            logger.error(error_msg)
            raise PodcastError(error_msg) from e
    
    def cleanup_episode_files(self, episode_guid: str, keep_original: bool = True):
        """
        Clean up audio files for an episode
        
        Args:
            episode_guid: Episode identifier
            keep_original: Whether to keep the original downloaded file
        """
        episode_id = episode_guid.replace('-', '')[:6]
        
        # Clean up chunks
        chunk_episode_dir = self.chunk_dir / episode_id
        if chunk_episode_dir.exists():
            for chunk_file in chunk_episode_dir.glob("*.mp3"):
                chunk_file.unlink()
                logger.debug(f"Deleted chunk: {chunk_file}")
            
            # Remove empty directory
            try:
                chunk_episode_dir.rmdir()
                logger.debug(f"Removed chunk directory: {chunk_episode_dir}")
            except OSError:
                logger.warning(f"Could not remove chunk directory (not empty?): {chunk_episode_dir}")
        
        # Optionally clean up original file
        if not keep_original:
            for audio_file in self.audio_cache_dir.glob(f"*-{episode_id}.mp3"):
                audio_file.unlink()
                logger.debug(f"Deleted original audio: {audio_file}")
    
    def get_audio_info(self, audio_file_path: str) -> dict:
        """
        Get information about audio file using FFprobe
        
        Args:
            audio_file_path: Path to audio file
            
        Returns:
            Dict with audio information
        """
        try:
            cmd = [
                'ffprobe', '-v', 'quiet',
                '-print_format', 'json',
                '-show_format', '-show_streams',
                audio_file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.warning(f"FFprobe failed for {audio_file_path}: {result.stderr}")
                return {}
            
            import json
            probe_data = json.loads(result.stdout)
            
            # Extract relevant info
            format_info = probe_data.get('format', {})
            audio_streams = [s for s in probe_data.get('streams', []) if s.get('codec_type') == 'audio']
            
            if not audio_streams:
                return {}
            
            stream = audio_streams[0]
            
            return {
                'duration': float(format_info.get('duration', 0)),
                'size': int(format_info.get('size', 0)),
                'bitrate': int(format_info.get('bit_rate', 0)),
                'sample_rate': int(stream.get('sample_rate', 0)),
                'channels': int(stream.get('channels', 0)),
                'codec': stream.get('codec_name', 'unknown')
            }
        except Exception as e:
            logger.warning(f"Could not get audio info for {audio_file_path}: {e}")
            return {}
    
    def _validate_audio_file(self, file_path: Path, expected_size: Optional[int] = None) -> bool:
        """Validate downloaded audio file"""
        try:
            # Check file exists and has content
            if not file_path.exists() or file_path.stat().st_size == 0:
                return False
            
            # Check size if expected
            actual_size = file_path.stat().st_size
            if expected_size and abs(actual_size - expected_size) > expected_size * 0.1:
                logger.warning(f"Size validation failed: expected ~{expected_size}, got {actual_size}")
                # Don't fail validation just on size mismatch, continue to format check
            
            # Quick format validation - try to get duration
            duration = self._get_audio_duration(str(file_path))
            if duration <= 0:
                logger.warning(f"Audio file appears to have no duration: {file_path}")
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"Audio validation failed for {file_path}: {e}")
            return False
    
    def _get_audio_duration(self, audio_file_path: str) -> float:
        """Get audio duration in seconds using FFprobe"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'csv=p=0',
                audio_file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
            
            return 0.0
            
        except Exception as e:
            logger.warning(f"Could not get audio duration for {audio_file_path}: {e}")
            return 0.0
    
    def _copy_file(self, source: str, destination: str):
        """Copy file efficiently"""
        import shutil
        shutil.copy2(source, destination)
    
    def _extract_feed_keyword(self, feed_title: str) -> str:
        """Extract keyword from feed title for filename"""
        import re
        # Extract meaningful keywords from feed title
        title_lower = feed_title.lower()
        
        # Common podcast feed patterns
        keywords = {
            'bridge': 'bridge',
            'mansbridge': 'bridge', 
            'simplification': 'simple',
            'movement': 'movement',
            'memos': 'memos',
            'kultural': 'kultural',
            'anchor': 'anchor'
        }
        
        # Check for known keywords
        for key, short in keywords.items():
            if key in title_lower:
                return short
        
        # Fallback: use first meaningful word (not "the", "with", etc.)
        words = re.findall(r'\b[a-z]+\b', title_lower)
        stop_words = {'the', 'with', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of'}
        for word in words:
            if word not in stop_words and len(word) > 2:
                return word[:8]  # Max 8 chars
        
        return "podcast"  # Ultimate fallback
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for filesystem safety"""
        # Remove or replace unsafe characters
        import re
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
        sanitized = re.sub(r'[^\w\-_.]', '_', sanitized)
        # Limit length
        return sanitized[:100]
    
    def __del__(self):
        """Cleanup resources"""
        if hasattr(self, 'session'):
            self.session.close()


def create_audio_processor(audio_cache_dir: str = "audio_cache", 
                          chunk_dir: str = "audio_chunks",
                          chunk_duration_minutes: int = 3) -> AudioProcessor:
    """Factory function to create audio processor"""
    return AudioProcessor(audio_cache_dir, chunk_dir, chunk_duration_minutes)


# CLI testing function
if __name__ == "__main__":
    import sys
    import tempfile
    
    if len(sys.argv) != 3:
        print("Usage: python audio_processor.py <audio_url> <episode_guid>")
        sys.exit(1)
    
    audio_url = sys.argv[1]
    episode_guid = sys.argv[2]
    
    # Use temporary directories for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        cache_dir = os.path.join(temp_dir, "cache")
        chunk_dir = os.path.join(temp_dir, "chunks")
        
        processor = create_audio_processor(cache_dir, chunk_dir, chunk_duration_minutes=2)
        
        try:
            # Download audio
            audio_path = processor.download_audio(audio_url, episode_guid)
            print(f"Downloaded: {audio_path}")
            
            # Get info
            info = processor.get_audio_info(audio_path)
            print(f"Duration: {info.get('duration', 0):.1f}s")
            
            # Chunk audio
            chunks = processor.chunk_audio(audio_path, episode_guid)
            print(f"Created {len(chunks)} chunks:")
            for i, chunk in enumerate(chunks, 1):
                print(f"  Chunk {i}: {chunk}")
                
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)