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
import shutil
import threading

from ..utils.error_handling import retry_with_backoff, PodcastError
from ..utils.logging_config import get_logger

logger = get_logger(__name__)

# Global lock for thread-safe chunk directory creation
_chunk_dir_lock = threading.Lock()


def _validate_external_tools():
    """Validate that required external tools are available.

    FAIL FAST: Raises PodcastError immediately if required tools are missing.
    """
    # Check for ffmpeg
    if not shutil.which('ffmpeg'):
        raise PodcastError(
            "CRITICAL: ffmpeg is required for audio processing but not found in PATH. "
            "Install ffmpeg:\n"
            "  macOS: brew install ffmpeg\n"
            "  Ubuntu: sudo apt update && sudo apt install ffmpeg\n"
            "  Windows: Download from https://ffmpeg.org/download.html"
        )

    # Test ffmpeg is working (ffmpeg uses -version, not --version)
    try:
        result = subprocess.run(['ffmpeg', '-version'],
                               capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            raise PodcastError(
                f"CRITICAL: ffmpeg command failed with exit code {result.returncode}. "
                f"Output: {result.stdout[:100] if result.stdout else 'no stdout'} "
                f"Error: {result.stderr[:100] if result.stderr else 'no stderr'}"
            )
    except FileNotFoundError:
        raise PodcastError("CRITICAL: ffmpeg not found in PATH. Install ffmpeg or check PATH")
    except subprocess.TimeoutExpired:
        raise PodcastError("CRITICAL: ffmpeg command timed out - check ffmpeg installation")
    except Exception as e:
        raise PodcastError(f"CRITICAL: Failed to validate ffmpeg: {str(e)}")

class AudioProcessor:
    """
    Handles audio file downloading, validation, and chunking for podcast episodes.
    
    Supports context manager protocol for proper resource cleanup:
        with AudioProcessor() as processor:
            processor.download_audio(...)
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

        Raises:
            PodcastError: If required external tools (ffmpeg) are not available
        """
        # FAIL FAST: Validate external tools before proceeding
        _validate_external_tools()

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
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure resources are cleaned up"""
        self.close()
        return False  # Don't suppress exceptions
    
    def close(self):
        """Explicitly close resources"""
        if hasattr(self, 'session') and self.session:
            try:
                self.session.close()
                logger.debug("AudioProcessor session closed")
            except Exception as e:
                logger.warning(f"Error closing session: {e}")
            finally:
                self.session = None
    
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
            
            # Check HTTP status first
            if response.status_code == 404:
                raise PodcastError(f"Audio file not found (404): {audio_url}")
            elif response.status_code >= 400:
                raise PodcastError(f"HTTP error {response.status_code} downloading audio: {audio_url}")
            
            response.raise_for_status()
            
            # Check content type - fail fast on non-audio content
            content_type = response.headers.get('content-type', '').lower()
            if 'audio' not in content_type and 'mpeg' not in content_type and 'octet-stream' not in content_type:
                # Check if it's HTML (likely an error page)
                if 'text/html' in content_type:
                    raise PodcastError(f"Received HTML instead of audio (likely error page): {audio_url}")
                logger.warning(f"Unexpected content type: {content_type}, will attempt to process anyway")
            
            # Download with progress tracking
            total_size = int(response.headers.get('content-length', 0))
            total_size_mb = total_size / (1024 * 1024) if total_size > 0 else 0

            if expected_size and abs(total_size - expected_size) > expected_size * 0.1:
                logger.warning(f"Size mismatch: expected {expected_size}, got {total_size}")

            logger.info(f"📥 Starting download: {total_size_mb:.1f}MB")

            downloaded_size = 0
            last_log_mb = 0
            download_start = datetime.now()

            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:  # Filter out keep-alive chunks
                        f.write(chunk)
                        downloaded_size += len(chunk)

                        # Log progress every 5MB or at completion
                        downloaded_mb = downloaded_size / (1024 * 1024)
                        if (downloaded_mb - last_log_mb >= 5.0) or (total_size > 0 and downloaded_size >= total_size):
                            if total_size > 0:
                                progress = (downloaded_size / total_size) * 100
                                logger.info(f"📥 Download progress: {downloaded_mb:.1f}MB / {total_size_mb:.1f}MB ({progress:.1f}%)")
                            else:
                                logger.info(f"📥 Download progress: {downloaded_mb:.1f}MB")
                            last_log_mb = downloaded_mb

            download_duration = (datetime.now() - download_start).total_seconds()
            download_speed_mbps = (downloaded_size / (1024 * 1024)) / max(download_duration, 1)
            logger.info(f"📥 Download completed: {downloaded_size / (1024 * 1024):.1f}MB in {download_duration:.1f}s ({download_speed_mbps:.1f} MB/s)")
            
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
            List of paths to audio chunks (only valid chunks)

        Raises:
            PodcastError: If chunking fails or all chunks are invalid
        """
        audio_path = Path(audio_file_path)
        if not audio_path.exists():
            raise PodcastError(f"Audio file not found: {audio_file_path}")

        # Validate audio file before chunking to prevent segfaults
        if not self._validate_audio_file(audio_path):
            raise PodcastError(f"Audio file failed validation (corrupt or invalid): {audio_file_path}")
        
        # Create episode chunk directory using same naming convention
        # CRITICAL: Use lock to prevent race conditions when multiple workers create same directory
        episode_id = episode_guid.replace('-', '')[:6]
        chunk_episode_dir = self.chunk_dir / episode_id

        with _chunk_dir_lock:
            chunk_episode_dir.mkdir(exist_ok=True, parents=True)
        
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

            # Resource monitoring - track file descriptors to detect leaks
            initial_fds = 0
            if os.path.exists('/proc/self/fd'):
                initial_fds = len(os.listdir('/proc/self/fd'))
                logger.info(f"🔍 Starting chunking with {initial_fds} open file descriptors")

            for chunk_num in range(num_chunks):
                start_time = chunk_num * self.chunk_duration_seconds
                chunk_filename = f"{episode_id}_chunk_{chunk_num+1:03d}.mp3"
                chunk_path = chunk_episode_dir / chunk_filename

                logger.info(f"🔧 Processing chunk {chunk_num+1}/{num_chunks} (start: {start_time}s)")

                # FFmpeg command to extract chunk
                # CRITICAL: -ss BEFORE -i enables fast seeking, avoiding slow decode to seek point
                cmd = [
                    'ffmpeg', '-y',  # -y to overwrite existing files
                    '-ss', str(start_time),  # MOVED: Fast seek to start time
                    '-i', str(audio_path),
                    '-t', str(self.chunk_duration_seconds),
                    '-acodec', 'libmp3lame',
                    '-ar', '16000',  # 16kHz sample rate for ASR
                    '-ac', '1',      # Mono for ASR
                    '-q:a', '2',     # High quality
                    str(chunk_path)
                ]

                logger.debug(f"Running FFmpeg: {' '.join(cmd)}")

                chunk_start_time = datetime.now()

                try:
                    # Remove timeout and fix output buffering to prevent deadlock
                    # FFmpeg is very verbose - capturing all output can fill OS pipe buffer
                    result = subprocess.run(
                        cmd,
                        stdout=subprocess.DEVNULL,  # Don't capture verbose output
                        stderr=subprocess.PIPE,     # Keep stderr for error messages
                        text=True
                        # NO timeout - let FFmpeg run as long as needed for large files
                    )
                    chunk_duration = (datetime.now() - chunk_start_time).total_seconds()

                    if result.returncode != 0:
                        error_msg = f"FFmpeg failed for chunk {chunk_num+1}: exit code {result.returncode}"
                        if result.stderr:
                            error_msg += f"\nSTDERR: {result.stderr[:500]}"
                        logger.error(error_msg)
                        raise PodcastError(error_msg)

                except FileNotFoundError:
                    raise PodcastError("CRITICAL: ffmpeg not found in PATH. Install ffmpeg or check PATH")
                except subprocess.CalledProcessError as e:
                    error_msg = f"FFmpeg subprocess error for chunk {chunk_num+1}: {e}"
                    logger.error(error_msg)
                    raise PodcastError(error_msg)

                if not chunk_path.exists() or chunk_path.stat().st_size == 0:
                    logger.warning(f"Empty or missing chunk: {chunk_path}")
                    continue

                # CRITICAL: Validate chunk audio properties to prevent Whisper failures
                if not self._validate_chunk_audio(str(chunk_path)):
                    logger.warning(f"🚨 Invalid chunk detected (corrupt or silent), skipping: {chunk_path}")
                    try:
                        chunk_path.unlink()  # Delete corrupt chunk
                    except Exception:
                        pass
                    continue

                chunk_size_mb = chunk_path.stat().st_size / (1024 * 1024)
                chunk_paths.append(str(chunk_path))

                # Monitor resource usage after each chunk
                current_fds = 0
                if os.path.exists('/proc/self/fd'):
                    current_fds = len(os.listdir('/proc/self/fd'))
                    fd_delta = current_fds - initial_fds
                    logger.info(f"✅ Chunk {chunk_num+1}/{num_chunks} completed: {chunk_size_mb:.1f}MB, {chunk_duration:.1f}s processing time, FDs={current_fds} (Δ{fd_delta:+d})")
                else:
                    logger.info(f"✅ Chunk {chunk_num+1}/{num_chunks} completed: {chunk_size_mb:.1f}MB, {chunk_duration:.1f}s processing time")
            
            # CRITICAL: Validate minimum chunk threshold for partial transcription
            # Accept episodes with ≥70% valid chunks (or at least 1 chunk if total < 3)
            if not chunk_paths:
                raise PodcastError(
                    f"No valid audio chunks created for {episode_guid} - "
                    f"all chunks failed validation (likely corrupt or silent audio)"
                )

            # Calculate success rate
            success_rate = len(chunk_paths) / num_chunks if num_chunks > 0 else 0
            failed_chunks = num_chunks - len(chunk_paths)

            # Partial transcription threshold: 70% valid OR at least 1 chunk for short episodes
            min_threshold = 0.70
            if num_chunks < 3:
                # For very short episodes (1-2 chunks), accept if we got any chunks
                if len(chunk_paths) == 0:
                    raise PodcastError(
                        f"No valid audio chunks for short episode {episode_guid} ({num_chunks} expected)"
                    )
            elif success_rate < min_threshold:
                raise PodcastError(
                    f"Insufficient valid chunks for {episode_guid}: {len(chunk_paths)}/{num_chunks} "
                    f"({success_rate:.1%} < {min_threshold:.0%} threshold). "
                    f"Too many corrupt chunks to produce reliable transcript."
                )

            if failed_chunks > 0:
                logger.warning(
                    f"⚠️ Partial transcription: {len(chunk_paths)}/{num_chunks} valid chunks "
                    f"({failed_chunks} corrupt/skipped) - transcript will have gaps"
                )
                logger.info(f"✓ Proceeding with {len(chunk_paths)} valid chunks ({success_rate:.1%} success rate)")
            else:
                logger.info(f"✓ Successfully created {len(chunk_paths)} valid audio chunks for {episode_guid}")

            return chunk_paths

        except subprocess.CalledProcessError as e:
            error_msg = f"FFmpeg chunking subprocess error for {episode_guid}: {e}"
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

            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True
                # Removed timeout - ffprobe should be fast but shouldn't fail on large files
            )
            if result.returncode != 0:
                logger.warning(f"FFprobe failed for {audio_file_path}: exit code {result.returncode}")
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
        except FileNotFoundError:
            logger.warning(f"ffprobe not found in PATH. Install ffmpeg or check PATH")
            return {}
        except subprocess.CalledProcessError as e:
            logger.warning(f"FFprobe subprocess error for {audio_file_path}: {e}")
            return {}
        except Exception as e:
            logger.warning(f"Could not get audio info for {audio_file_path}: {e}")
            return {}
    
    def _validate_chunk_audio(self, chunk_path: str) -> bool:
        """Validate audio chunk properties to prevent Whisper failures.

        Checks for:
        - Valid audio format and codec
        - Non-zero duration (> 0.5 seconds)
        - Proper sample rate and channels
        - Audio stream presence

        Args:
            chunk_path: Path to audio chunk file

        Returns:
            True if chunk is valid, False if corrupt/silent/invalid
        """
        try:
            # Get detailed audio info using ffprobe
            info = self.get_audio_info(chunk_path)

            if not info:
                logger.warning(f"Could not get audio info for chunk: {chunk_path}")
                return False

            # Check duration - must be at least 0.5 seconds to have meaningful content
            duration = info.get('duration', 0)
            if duration < 0.5:
                logger.warning(f"Chunk too short ({duration}s): {chunk_path}")
                return False

            # Check for valid sample rate (should be 16000 after conversion)
            sample_rate = info.get('sample_rate', 0)
            if sample_rate == 0:
                logger.warning(f"Invalid sample rate ({sample_rate}): {chunk_path}")
                return False

            # Check for valid codec
            codec = info.get('codec', '')
            if not codec or codec == 'unknown':
                logger.warning(f"Unknown codec: {chunk_path}")
                return False

            # Check file size is reasonable (at least 10KB for 16kHz mono)
            file_size = Path(chunk_path).stat().st_size
            if file_size < 10240:  # 10KB minimum
                logger.warning(f"Chunk file too small ({file_size} bytes): {chunk_path}")
                return False

            # CRITICAL: Test actual audio decoding to catch corrupt PCM data
            # ffprobe only checks container/metadata, not actual audio samples
            try:
                import subprocess
                # Try to decode first 5 seconds to verify audio is actually decodable
                test_result = subprocess.run(
                    ['ffmpeg', '-v', 'error', '-i', chunk_path, '-t', '5',
                     '-f', 'null', '-'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if test_result.returncode != 0:
                    logger.warning(f"Audio decode test failed for {chunk_path}: {test_result.stderr[:200]}")
                    return False
            except subprocess.TimeoutExpired:
                logger.warning(f"Audio decode test timed out for {chunk_path}")
                return False
            except Exception as e:
                logger.warning(f"Audio decode test error for {chunk_path}: {e}")
                return False

            logger.debug(f"✓ Chunk validated: {duration:.1f}s, {sample_rate}Hz, {codec}, {file_size} bytes")
            return True

        except Exception as e:
            logger.warning(f"Chunk validation error for {chunk_path}: {e}")
            return False

    def _validate_audio_file(self, file_path: Path, expected_size: Optional[int] = None) -> bool:
        """Validate downloaded audio file"""
        try:
            # Check file exists and has content
            if not file_path.exists():
                logger.warning(f"Audio file does not exist: {file_path}")
                return False
            
            actual_size = file_path.stat().st_size
            
            # Check minimum file size (1KB) - catch empty/corrupt files
            if actual_size < 1024:
                logger.warning(f"Audio file too small ({actual_size} bytes), likely corrupt: {file_path}")
                return False
            
            # Check size if expected
            if expected_size and abs(actual_size - expected_size) > expected_size * 0.1:
                logger.warning(f"Size validation failed: expected ~{expected_size}, got {actual_size}")
                # Don't fail validation just on size mismatch, continue to format check
            
            # Quick format validation - try to get duration
            duration = self._get_audio_duration(str(file_path))
            if duration <= 0:
                logger.warning(f"Audio file appears to have no duration: {file_path}")
                return False
            
            # Sanity check: duration should be reasonable (> 1 second, < 24 hours)
            if duration < 1.0:
                logger.warning(f"Audio file duration too short ({duration}s): {file_path}")
                return False
            if duration > 86400:
                logger.warning(f"Audio file duration suspiciously long ({duration}s / {duration/3600:.1f}h): {file_path}")
                # Don't fail on long files, just warn
            
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

            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True
                # Removed timeout - ffprobe should be fast but shouldn't fail on large files
            )
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
            
            return 0.0

        except FileNotFoundError:
            logger.warning(f"ffprobe not found in PATH. Install ffmpeg or check PATH")
            return 0.0
        except subprocess.CalledProcessError as e:
            logger.warning(f"FFprobe duration check subprocess error for {audio_file_path}: {e}")
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
        """Cleanup resources on deletion"""
        self.close()


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