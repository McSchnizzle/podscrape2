"""
YouTube Transcript Processing System.
Fetches, processes, and stores video transcripts with retry logic and quality validation.
"""

import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
import json

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled, 
    NoTranscriptFound, 
    VideoUnavailable,
    YouTubeRequestFailed,
    CouldNotRetrieveTranscript
)
from youtube_transcript_api.proxies import WebshareProxyConfig

from ..database.models import Episode, EpisodeRepository
from ..utils.error_handling import retry_with_backoff

logger = logging.getLogger(__name__)

@dataclass
class TranscriptSegment:
    """Individual transcript segment with timing"""
    text: str
    start: float
    duration: float

@dataclass 
class TranscriptData:
    """Complete transcript data for a video"""
    video_id: str
    language: str
    segments: List[TranscriptSegment]
    total_duration: float
    word_count: int
    is_auto_generated: bool
    fetch_timestamp: datetime

class TranscriptProcessor:
    """
    Processes YouTube video transcripts with retry logic and quality validation.
    Handles various transcript availability scenarios and errors gracefully.
    """
    
    def __init__(self, transcript_dir: str = None, max_retries: int = 3, 
                 proxy_config: Dict[str, str] = None, request_delay: float = 1.0):
        """
        Initialize transcript processor.
        
        Args:
            transcript_dir: Directory to store transcript files (defaults to data/transcripts)
            max_retries: Maximum number of retry attempts for failed requests
            proxy_config: Optional proxy configuration (e.g., {'username': 'user', 'password': 'pass'})
            request_delay: Delay between requests in seconds to avoid rate limiting
        """
        if transcript_dir is None:
            # Default to data/transcripts relative to project root
            project_root = Path(__file__).parent.parent.parent
            transcript_dir = project_root / 'data' / 'transcripts'
        
        self.transcript_dir = Path(transcript_dir)
        self.transcript_dir.mkdir(parents=True, exist_ok=True)
        self.max_retries = max_retries
        self.request_delay = request_delay
        
        # Setup proxy configuration if provided
        self.proxy_config = None
        if proxy_config and proxy_config.get('username') and proxy_config.get('password'):
            self.proxy_config = WebshareProxyConfig(
                username=proxy_config['username'],
                password=proxy_config['password']
            )
            logger.info("Transcript processor initialized with proxy configuration")
        
        # Preferred language order (English first, then auto-generated)
        self.preferred_languages = ['en', 'en-US', 'en-GB', 'en-CA', 'en-AU']
        
        logger.info(f"Transcript processor initialized with directory: {self.transcript_dir}")
    
    def test_connectivity(self, test_video_id: str = "dQw4w9WgXcQ") -> Dict[str, Any]:
        """
        Test YouTube transcript API connectivity and IP status.
        
        Args:
            test_video_id: Video ID to test with (default: Rick Roll)
            
        Returns:
            Dictionary with connectivity test results
        """
        results = {
            'can_list_transcripts': False,
            'can_fetch_transcript': False,
            'ip_blocked': False,
            'error_message': None,
            'available_transcripts': 0
        }
        
        try:
            # Test listing transcripts (lighter operation)
            if self.proxy_config:
                api = YouTubeTranscriptApi(proxies=[self.proxy_config])
            else:
                api = YouTubeTranscriptApi()
                
            transcript_list = api.list(test_video_id)
            results['can_list_transcripts'] = True
            results['available_transcripts'] = len(list(transcript_list))
            
            # Test actual transcript fetching
            transcript_list = api.list(test_video_id)  # Re-get list
            if transcript_list:
                first_transcript = next(iter(transcript_list))
                data = first_transcript.fetch()
                results['can_fetch_transcript'] = True
                
        except (YouTubeRequestFailed, CouldNotRetrieveTranscript) as e:
            results['ip_blocked'] = True
            results['error_message'] = str(e)
        except Exception as e:
            results['error_message'] = str(e)
        
        return results
    
    def fetch_transcript(self, video_id: str) -> Optional[TranscriptData]:
        """
        Fetch transcript for a video with retry logic.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            TranscriptData if successful, None if failed after retries
        """
        logger.info(f"Fetching transcript for video: {video_id}")
        
        def _fetch_attempt():
            return self._fetch_transcript_attempt(video_id)
        
        try:
            return retry_with_backoff(
                _fetch_attempt,
                max_retries=self.max_retries,
                backoff_factor=2.0,
                exceptions=(YouTubeRequestFailed, CouldNotRetrieveTranscript)
            )
        except Exception as e:
            logger.error(f"Failed to fetch transcript for {video_id} after {self.max_retries} attempts: {e}")
            return None
    
    def _fetch_transcript_attempt(self, video_id: str) -> TranscriptData:
        """Single attempt to fetch transcript"""
        try:
            # Add delay to be respectful to YouTube
            if hasattr(self, '_last_request_time'):
                elapsed = time.time() - self._last_request_time
                if elapsed < self.request_delay:
                    time.sleep(self.request_delay - elapsed)
            
            # Create API instance with optional proxy configuration
            if self.proxy_config:
                api = YouTubeTranscriptApi(proxies=[self.proxy_config])
                logger.debug(f"Using proxy for transcript request: {video_id}")
            else:
                api = YouTubeTranscriptApi()
            
            # Get available transcript languages
            transcript_list = api.list(video_id)
            self._last_request_time = time.time()
            
            # Try to find preferred language transcript
            transcript = None
            selected_language = None
            is_auto_generated = False
            
            # First, try manually created transcripts in preferred languages
            for lang in self.preferred_languages:
                try:
                    transcript = transcript_list.find_manually_created_transcript([lang])
                    selected_language = lang
                    is_auto_generated = False
                    logger.debug(f"Found manual transcript in {lang} for {video_id}")
                    break
                except NoTranscriptFound:
                    continue
            
            # If no manual transcript found, try auto-generated
            if transcript is None:
                for lang in self.preferred_languages:
                    try:
                        transcript = transcript_list.find_generated_transcript([lang])
                        selected_language = lang
                        is_auto_generated = True
                        logger.debug(f"Found auto-generated transcript in {lang} for {video_id}")
                        break
                    except NoTranscriptFound:
                        continue
            
            # If still no transcript, try any available transcript
            if transcript is None:
                available_transcripts = list(transcript_list)
                if available_transcripts:
                    transcript = available_transcripts[0]
                    selected_language = transcript.language_code
                    is_auto_generated = transcript.is_generated
                    logger.warning(f"Using fallback transcript in {selected_language} for {video_id}")
                else:
                    raise NoTranscriptFound(video_id)
            
            # Fetch the transcript data
            transcript_data = transcript.fetch()
            
            # Process segments
            segments = []
            total_text = ""
            total_duration = 0.0
            
            for segment in transcript_data:
                text = segment.text.strip()
                start = float(segment.start)
                duration = float(segment.duration)
                
                if text:  # Skip empty segments
                    segments.append(TranscriptSegment(
                        text=text,
                        start=start,
                        duration=duration
                    ))
                    total_text += " " + text
                    total_duration = max(total_duration, start + duration)
            
            # Calculate word count
            word_count = len(total_text.split())
            
            transcript_obj = TranscriptData(
                video_id=video_id,
                language=selected_language,
                segments=segments,
                total_duration=total_duration,
                word_count=word_count,
                is_auto_generated=is_auto_generated,
                fetch_timestamp=datetime.now()
            )
            
            logger.info(f"Successfully fetched transcript for {video_id}: {word_count} words, {len(segments)} segments")
            return transcript_obj
            
        except TranscriptsDisabled:
            logger.warning(f"Transcripts are disabled for video {video_id}")
            raise
        except NoTranscriptFound:
            logger.warning(f"No transcript found for video {video_id}")
            raise
        except VideoUnavailable:
            logger.error(f"Video {video_id} is unavailable")
            raise
        except YouTubeRequestFailed:
            logger.warning(f"YouTube request failed while fetching transcript for {video_id}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching transcript for {video_id}: {e}")
            raise CouldNotRetrieveTranscript(video_id)
    
    def save_transcript(self, transcript_data: TranscriptData, save_txt: bool = True) -> str:
        """
        Save transcript data to file and return file path.
        
        Args:
            transcript_data: TranscriptData object to save
            save_txt: Whether to also save a plain text version
            
        Returns:
            Path to saved JSON transcript file
        """
        # Generate filename with timestamp
        timestamp = transcript_data.fetch_timestamp.strftime("%Y%m%d_%H%M%S")
        json_filename = f"{transcript_data.video_id}_{timestamp}.json"
        json_file_path = self.transcript_dir / json_filename
        
        # Prepare data for JSON serialization
        transcript_json = {
            'video_id': transcript_data.video_id,
            'language': transcript_data.language,
            'is_auto_generated': transcript_data.is_auto_generated,
            'total_duration': transcript_data.total_duration,
            'word_count': transcript_data.word_count,
            'fetch_timestamp': transcript_data.fetch_timestamp.isoformat(),
            'segments': [
                {
                    'text': segment.text,
                    'start': segment.start,
                    'duration': segment.duration
                }
                for segment in transcript_data.segments
            ]
        }
        
        # Save JSON file
        try:
            with open(json_file_path, 'w', encoding='utf-8') as f:
                json.dump(transcript_json, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved JSON transcript for {transcript_data.video_id} to {json_file_path}")
            
            # Optionally save plain text version
            if save_txt:
                txt_filename = f"{transcript_data.video_id}_{timestamp}.txt"
                txt_file_path = self.transcript_dir / txt_filename
                
                # Create clean text version
                full_text = self.get_transcript_text(transcript_data)
                
                with open(txt_file_path, 'w', encoding='utf-8') as f:
                    # Add header with metadata
                    f.write(f"# Transcript for YouTube Video: {transcript_data.video_id}\n")
                    f.write(f"# Language: {transcript_data.language}\n")
                    f.write(f"# Auto-generated: {transcript_data.is_auto_generated}\n")
                    f.write(f"# Duration: {transcript_data.total_duration:.1f} seconds\n")
                    f.write(f"# Word count: {transcript_data.word_count}\n")
                    f.write(f"# Fetched: {transcript_data.fetch_timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"#\n\n")
                    f.write(full_text)
                
                logger.info(f"Saved TXT transcript for {transcript_data.video_id} to {txt_file_path}")
            
            return str(json_file_path)
            
        except Exception as e:
            logger.error(f"Failed to save transcript for {transcript_data.video_id}: {e}")
            raise
    
    def load_transcript(self, file_path: str) -> Optional[TranscriptData]:
        """
        Load transcript data from file.
        
        Args:
            file_path: Path to transcript JSON file
            
        Returns:
            TranscriptData object if successful, None if failed
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            segments = [
                TranscriptSegment(
                    text=seg['text'],
                    start=seg['start'],
                    duration=seg['duration']
                )
                for seg in data['segments']
            ]
            
            return TranscriptData(
                video_id=data['video_id'],
                language=data['language'],
                segments=segments,
                total_duration=data['total_duration'],
                word_count=data['word_count'],
                is_auto_generated=data['is_auto_generated'],
                fetch_timestamp=datetime.fromisoformat(data['fetch_timestamp'])
            )
            
        except Exception as e:
            logger.error(f"Failed to load transcript from {file_path}: {e}")
            return None
    
    def validate_transcript_quality(self, transcript_data: TranscriptData) -> Tuple[bool, str]:
        """
        Validate transcript quality and return result with reason.
        
        Args:
            transcript_data: TranscriptData to validate
            
        Returns:
            Tuple of (is_valid, reason)
        """
        # Minimum word count (approximately 3 minutes of content)
        min_word_count = 300
        if transcript_data.word_count < min_word_count:
            return False, f"Word count too low: {transcript_data.word_count} < {min_word_count}"
        
        # Check for reasonable segment count (should have multiple segments)
        if len(transcript_data.segments) < 5:
            return False, f"Too few segments: {len(transcript_data.segments)} < 5"
        
        # Check for reasonable average segment length
        avg_segment_length = transcript_data.word_count / len(transcript_data.segments)
        if avg_segment_length < 2:  # Very short segments might indicate poor quality
            return False, f"Average segment length too short: {avg_segment_length:.1f} words"
        
        # Check for excessive repetition (simple heuristic)
        all_text = " ".join(segment.text for segment in transcript_data.segments)
        words = all_text.lower().split()
        unique_words = set(words)
        repetition_ratio = len(words) / len(unique_words) if unique_words else 0
        
        if repetition_ratio > 3.0:  # Too much repetition
            return False, f"Excessive repetition detected: ratio {repetition_ratio:.1f}"
        
        # Check total duration makes sense
        if transcript_data.total_duration < 180:  # Less than 3 minutes
            return False, f"Duration too short: {transcript_data.total_duration:.1f}s < 180s"
        
        return True, "Quality validation passed"
    
    def get_transcript_text(self, transcript_data: TranscriptData) -> str:
        """
        Extract plain text from transcript data.
        
        Args:
            transcript_data: TranscriptData object
            
        Returns:
            Plain text of the transcript
        """
        return " ".join(segment.text for segment in transcript_data.segments)

class TranscriptPipeline:
    """
    Complete pipeline for processing video transcripts.
    Handles fetching, storage, validation, and database updates.
    """
    
    def __init__(self, episode_repo: EpisodeRepository, transcript_processor: TranscriptProcessor):
        """
        Initialize transcript pipeline.
        
        Args:
            episode_repo: Episode repository for database operations
            transcript_processor: Transcript processor for fetching and saving
        """
        self.episode_repo = episode_repo
        self.transcript_processor = transcript_processor
    
    def process_episode(self, episode: Episode) -> bool:
        """
        Process transcript for a single episode.
        
        Args:
            episode: Episode object to process
            
        Returns:
            True if successful, False if failed
        """
        logger.info(f"Processing transcript for episode: {episode.video_id} - {episode.title}")
        
        try:
            # Fetch transcript
            transcript_data = self.transcript_processor.fetch_transcript(episode.video_id)
            if not transcript_data:
                self._mark_episode_failed(episode, "Failed to fetch transcript")
                return False
            
            # Validate quality
            is_valid, reason = self.transcript_processor.validate_transcript_quality(transcript_data)
            if not is_valid:
                logger.warning(f"Transcript quality validation failed for {episode.video_id}: {reason}")
                # Still save the transcript but mark with warning
            
            # Save transcript file
            file_path = self.transcript_processor.save_transcript(transcript_data)
            
            # Update episode in database
            self.episode_repo.update_transcript(
                episode.video_id,
                file_path,
                transcript_data.word_count
            )
            
            logger.info(f"Successfully processed transcript for {episode.video_id}")
            return True
            
        except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable) as e:
            self._mark_episode_failed(episode, str(e))
            return False
        except Exception as e:
            logger.error(f"Unexpected error processing episode {episode.video_id}: {e}")
            self._mark_episode_failed(episode, f"Unexpected error: {str(e)}")
            return False
    
    def process_pending_episodes(self, limit: int = None) -> Dict[str, int]:
        """
        Process all pending episodes.
        
        Args:
            limit: Maximum number of episodes to process (None for all)
            
        Returns:
            Dictionary with processing statistics
        """
        logger.info("Starting batch transcript processing for pending episodes")
        
        # Get pending episodes
        pending_episodes = self.episode_repo.get_by_status('pending')
        if limit:
            pending_episodes = pending_episodes[:limit]
        
        if not pending_episodes:
            logger.info("No pending episodes found for transcript processing")
            return {'total': 0, 'successful': 0, 'failed': 0}
        
        logger.info(f"Processing {len(pending_episodes)} pending episodes")
        
        stats = {'total': len(pending_episodes), 'successful': 0, 'failed': 0}
        
        for episode in pending_episodes:
            try:
                if self.process_episode(episode):
                    stats['successful'] += 1
                else:
                    stats['failed'] += 1
                    
                # Brief pause to be respectful to YouTube API
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error processing episode {episode.video_id}: {e}")
                stats['failed'] += 1
        
        logger.info(f"Batch processing complete: {stats['successful']} successful, {stats['failed']} failed")
        return stats
    
    def _mark_episode_failed(self, episode: Episode, reason: str):
        """Mark episode as failed with reason"""
        logger.error(f"Marking episode {episode.video_id} as failed: {reason}")
        self.episode_repo.mark_failure(episode.video_id, reason)

def create_transcript_pipeline(episode_repo: EpisodeRepository = None, 
                             transcript_dir: str = None) -> TranscriptPipeline:
    """
    Factory function to create a transcript pipeline with default dependencies.
    
    Args:
        episode_repo: Episode repository (creates default if None)
        transcript_dir: Transcript directory (uses default if None)
        
    Returns:
        Configured TranscriptPipeline
    """
    from ..database.models import get_episode_repo
    
    if episode_repo is None:
        episode_repo = get_episode_repo()
    
    transcript_processor = TranscriptProcessor(transcript_dir)
    return TranscriptPipeline(episode_repo, transcript_processor)