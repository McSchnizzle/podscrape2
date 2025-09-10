#!/usr/bin/env python3
"""
RSS Podcast Transcription Script
Downloads and transcribes podcast episodes using Parakeet ASR.

Usage:
    python3 transcribe_episode.py --feed-url "https://feeds.simplecast.com/imTmqqal" --episode-limit 1
    python3 transcribe_episode.py --feed-url "https://anchor.fm/s/e8e55a68/podcast/rss" --episode-limit 1
"""

import argparse
import sys
import os
from pathlib import Path
from datetime import datetime
import logging

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.podcast.feed_parser import create_feed_parser
from src.podcast.audio_processor import create_audio_processor
from src.podcast.parakeet_mlx_transcriber import create_parakeet_mlx_transcriber
from src.podcast.rss_models import get_feed_repo, get_podcast_episode_repo, PodcastFeed, PodcastEpisode
from src.database.models import get_database_manager
from src.utils.logging_config import get_logger

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = get_logger(__name__)

class RSSTranscriptionPipeline:
    """Complete RSS podcast transcription pipeline"""
    
    def __init__(self):
        """Initialize pipeline components"""
        self.db = get_database_manager()
        self.feed_repo = get_feed_repo(self.db)
        self.episode_repo = get_podcast_episode_repo(self.db)
        
        # Initialize processors
        self.feed_parser = create_feed_parser()
        self.audio_processor = create_audio_processor()
        self.transcriber = create_parakeet_mlx_transcriber()
        
        # Create directories
        self.transcript_dir = Path("data/transcripts")
        self.transcript_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("RSS Transcription Pipeline initialized")
    
    def process_feed(self, feed_url: str, episode_limit: int = 1) -> list:
        """
        Process RSS feed and transcribe episodes
        
        Args:
            feed_url: RSS feed URL
            episode_limit: Number of episodes to process (1 for testing)
            
        Returns:
            List of processed episode results
        """
        logger.info(f"Processing RSS feed: {feed_url}")
        
        try:
            # Parse RSS feed
            logger.info("Parsing RSS feed...")
            parsed_feed = self.feed_parser.parse_feed(feed_url)
            logger.info(f"Found {len(parsed_feed.episodes)} episodes in feed '{parsed_feed.title}'")
            
            # Get or create feed in database
            db_feed = self._get_or_create_feed(parsed_feed, feed_url)
            
            # Process episodes (limit for testing)
            episodes_to_process = parsed_feed.episodes[:episode_limit]
            logger.info(f"Processing {len(episodes_to_process)} episode(s)")
            
            results = []
            for episode in episodes_to_process:
                try:
                    result = self._process_episode(episode, db_feed.id, parsed_feed.title)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Failed to process episode '{episode.title}': {e}")
                    results.append({
                        'episode_title': episode.title,
                        'status': 'failed',
                        'error': str(e)
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to process feed {feed_url}: {e}")
            raise
    
    def _get_or_create_feed(self, parsed_feed, feed_url: str) -> PodcastFeed:
        """Get existing feed or create new one"""
        # Check if feed exists
        existing_feed = self.feed_repo.get_by_url(feed_url)
        if existing_feed:
            logger.info(f"Using existing feed: {existing_feed.title}")
            return existing_feed
        
        # Create new feed
        new_feed = PodcastFeed(
            feed_url=feed_url,
            title=parsed_feed.title,
            description=parsed_feed.description
        )
        feed_id = self.feed_repo.create(new_feed)
        new_feed.id = feed_id
        
        logger.info(f"Created new feed: {new_feed.title} (ID: {feed_id})")
        return new_feed
    
    def _process_episode(self, episode, feed_id: int, feed_title: str = None) -> dict:
        """Process a single episode"""
        logger.info(f"Processing episode: '{episode.title}'")
        
        # Check if episode already exists
        existing_episode = self.episode_repo.get_by_guid(episode.guid)
        if existing_episode and existing_episode.status == 'transcribed':
            logger.info(f"Episode already transcribed: {episode.title}")
            return {
                'episode_title': episode.title,
                'status': 'already_transcribed',
                'transcript_path': existing_episode.transcript_path,
                'word_count': existing_episode.transcript_word_count
            }
        
        try:
            # Create episode in database
            db_episode = PodcastEpisode(
                episode_guid=episode.guid,
                feed_id=feed_id,
                title=episode.title,
                published_date=episode.published_date,
                duration_seconds=episode.duration_seconds,
                description=episode.description,
                audio_url=episode.audio_url
            )
            
            if not existing_episode:
                episode_id = self.episode_repo.create(db_episode)
                logger.info(f"Created episode in database: ID {episode_id}")
            
            # Download audio
            logger.info(f"Downloading audio: {episode.audio_url}")
            audio_path = self.audio_processor.download_audio(
                episode.audio_url, 
                episode.guid,
                episode.audio_size,
                feed_title
            )
            
            # Update episode with audio path
            self.episode_repo.update_audio_path(episode.guid, audio_path)
            logger.info(f"Audio downloaded: {audio_path}")
            
            # Chunk audio
            logger.info("Chunking audio for transcription...")
            audio_chunks = self.audio_processor.chunk_audio(audio_path, episode.guid)
            logger.info(f"Created {len(audio_chunks)} audio chunks")
            
            # Create in-progress transcript file based on audio filename
            audio_filename = Path(audio_path).stem  # Get filename without extension
            in_progress_path = f"{audio_filename}.txt"
            
            # Transcribe using Parakeet
            logger.info("Starting Parakeet transcription...")
            self.episode_repo.update_status(episode.guid, 'transcribing')
            
            transcription = self.transcriber.transcribe_episode(audio_chunks, episode.guid, in_progress_path)
            
            # Move in-progress file to final location (in-progress file already has complete transcript)
            final_transcript_path = str(self.transcript_dir / in_progress_path)
            Path(in_progress_path).rename(final_transcript_path)
            
            # Update database with final transcript path
            self.episode_repo.update_transcript(
                episode.guid,
                final_transcript_path,
                transcription.word_count,
                transcription.chunk_count
            )
            
            # Clean up audio chunks and original audio file (save disk space)
            self.audio_processor.cleanup_episode_files(episode.guid, keep_original=False)
            
            logger.info(f"Transcript saved to: {final_transcript_path}")
            
            logger.info(f"Episode transcription complete: {transcription.word_count} words")
            
            return {
                'episode_title': episode.title,
                'status': 'success',
                'transcript_path': final_transcript_path,
                'word_count': transcription.word_count,
                'duration_seconds': transcription.total_duration_seconds,
                'processing_time_seconds': transcription.total_processing_time_seconds,
                'chunks': transcription.chunk_count
            }
            
        except Exception as e:
            # Mark episode as failed
            self.episode_repo.mark_failure(episode.guid, str(e))
            raise


def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(description='Transcribe RSS podcast episodes using Parakeet ASR')
    parser.add_argument('--feed-url', required=True, help='RSS feed URL to process')
    parser.add_argument('--episode-limit', type=int, default=1, help='Number of episodes to process (default: 1)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Validate feed URL
        if not args.feed_url.startswith(('http://', 'https://')):
            print(f"Error: Invalid feed URL: {args.feed_url}")
            sys.exit(1)
        
        # Initialize pipeline
        print("Initializing RSS Transcription Pipeline...")
        pipeline = RSSTranscriptionPipeline()
        
        # Process feed
        print(f"Processing feed: {args.feed_url}")
        print(f"Episode limit: {args.episode_limit}")
        print("-" * 60)
        
        results = pipeline.process_feed(args.feed_url, args.episode_limit)
        
        # Print results
        print("\nTranscription Results:")
        print("=" * 60)
        
        for i, result in enumerate(results, 1):
            print(f"\nEpisode {i}: {result['episode_title']}")
            print(f"Status: {result['status']}")
            
            if result['status'] == 'success':
                print(f"Word count: {result['word_count']}")
                print(f"Duration: {result['duration_seconds']:.1f}s")
                print(f"Processing time: {result['processing_time_seconds']:.1f}s")
                print(f"Speed: {result['duration_seconds']/result['processing_time_seconds']:.1f}x realtime")
                print(f"Transcript: {result['transcript_path']}")
                print(f"JSON data: {result['json_path']}")
            elif result['status'] == 'already_transcribed':
                print(f"Word count: {result['word_count']}")
                print(f"Transcript: {result['transcript_path']}")
            elif result['status'] == 'failed':
                print(f"Error: {result['error']}")
        
        print("\n" + "=" * 60)
        successful = sum(1 for r in results if r['status'] == 'success')
        print(f"Processed {len(results)} episodes, {successful} successful")
        
        if successful > 0:
            print(f"\nTranscripts saved to: {pipeline.transcript_dir}")
            sys.exit(0)
        else:
            print("No episodes were successfully transcribed")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\nTranscription interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()