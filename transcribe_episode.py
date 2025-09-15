#!/usr/bin/env python3
"""
RSS Podcast Transcription Script
Downloads and transcribes podcast episodes using OpenAI Whisper (local).

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
from src.podcast.openai_whisper_transcriber import create_openai_whisper_transcriber
from src.database.models import get_feed_repo, get_episode_repo, Feed, Episode
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
        self.feed_repo = get_feed_repo()
        self.episode_repo = get_episode_repo()

        # Initialize processors
        self.feed_parser = create_feed_parser()
        self.audio_processor = create_audio_processor()
        self.transcriber = create_openai_whisper_transcriber()

        # Initialize web config for database settings
        try:
            from src.config.web_config import WebConfigManager
            self.web_config = WebConfigManager()
        except Exception:
            self.web_config = None

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
    
    def _get_or_create_feed(self, parsed_feed, feed_url: str) -> Feed:
        """Get existing feed or create new one"""
        # Check if feed exists
        existing_feed = self.feed_repo.get_by_url(feed_url)
        if existing_feed:
            logger.info(f"Using existing feed: {existing_feed.title}")
            return existing_feed
        
        # Create new feed
        new_feed = Feed(
            feed_url=feed_url,
            title=parsed_feed.title,
            description=parsed_feed.description,
            active=True
        )
        feed_id = self.feed_repo.create(new_feed)
        new_feed.id = feed_id
        
        logger.info(f"Created new feed: {new_feed.title} (ID: {feed_id})")
        return new_feed
    
    def _process_episode(self, episode, feed_id: int, feed_title: str = None) -> dict:
        """Process a single episode"""
        logger.info(f"Processing episode: '{episode.title}'")
        
        # Check if episode already exists
        existing_episode = self.episode_repo.get_by_episode_guid(episode.guid)
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
            db_episode = Episode(
                episode_guid=episode.guid,
                feed_id=feed_id,
                title=episode.title,
                published_date=episode.published_date,
                duration_seconds=episode.duration_seconds,
                description=episode.description,
                audio_url=episode.audio_url,
                status='pending'
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
            self.episode_repo.update_audio_download(episode.guid, audio_path)
            logger.info(f"Audio downloaded: {audio_path}")
            
            # Chunk audio
            logger.info("Chunking audio for transcription...")
            audio_chunks = self.audio_processor.chunk_audio(audio_path, episode.guid)
            logger.info(f"Created {len(audio_chunks)} audio chunks")

            # Apply database setting for max chunks per episode
            max_chunks = 3  # Default value
            if self.web_config:
                try:
                    max_chunks = self.web_config.get_setting('audio_processing', 'max_chunks_per_episode', 3)
                    logger.info(f"Using database setting: max_chunks_per_episode = {max_chunks}")
                except Exception:
                    pass

            # Limit chunks based on database setting
            if len(audio_chunks) > max_chunks:
                audio_chunks = audio_chunks[:max_chunks]
                logger.info(f"Limited to {max_chunks} chunks for transcription (database setting)")

            # Create in-progress transcript file
            audio_filename = Path(audio_path).stem  # Get filename without extension
            progress_filename = f"{audio_filename}-progress.txt"
            progress_path = str(self.transcript_dir / progress_filename)
            transcript_filename = f"{audio_filename}.txt"
            final_transcript_path = str(self.transcript_dir / transcript_filename)

            # Transcribe using OpenAI Whisper with in-progress file
            logger.info("Starting OpenAI Whisper transcription...")
            self.episode_repo.update_status(episode.guid, 'transcribing')

            transcription = self.transcriber.transcribe_episode(audio_chunks, episode.guid, progress_path)

            # Rename progress file to final name
            if Path(progress_path).exists():
                Path(progress_path).rename(final_transcript_path)
                logger.info(f"Renamed progress file to: {final_transcript_path}")
            else:
                # Fallback: write transcript to final location if progress file doesn't exist
                with open(final_transcript_path, 'w', encoding='utf-8') as f:
                    f.write(transcription.transcript_text)
                logger.info(f"Wrote transcript to: {final_transcript_path}")
            
            # Update database with final transcript path (remove chunk_count parameter)
            self.episode_repo.update_transcript(
                episode.guid,
                final_transcript_path,
                transcription.word_count
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
            self.episode_repo.update_status(episode.guid, 'failed')
            raise


def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(description='Transcribe RSS podcast episodes using OpenAI Whisper (local)')
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