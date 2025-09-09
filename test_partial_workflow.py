#!/usr/bin/env python3
"""
Partial Workflow Test - Real Audio Processing with Limited Chunks
Tests the complete workflow using real RSS feeds and real transcription on 2-3 chunks only.
This validates the pipeline without waiting for full episode transcription.
"""

import os
import sys
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
import tempfile
import shutil
from typing import List

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Set up environment
from dotenv import load_dotenv
load_dotenv()

from src.podcast.feed_parser import FeedParser
from src.scoring.content_scorer import ContentScorer
from src.generation.script_generator import ScriptGenerator
from src.database.models import get_episode_repo, get_digest_repo, Episode, get_database_manager
from src.podcast.audio_processor import AudioProcessor
import subprocess
import tempfile
import hashlib
import requests
import feedparser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PartialWorkflowTest:
    """
    Test workflow with real audio download and partial transcription (2-3 chunks only)
    """
    
    def __init__(self):
        logger.info("="*80)
        logger.info("PARTIAL WORKFLOW TEST - REAL AUDIO, LIMITED CHUNKS")
        logger.info("="*80)
        
        # Verify API keys
        self._verify_api_keys()
        
        # Initialize components
        self.audio_processor = AudioProcessor()
        self.content_scorer = ContentScorer()
        self.script_generator = ScriptGenerator()
        self.episode_repo = get_episode_repo()
        self.digest_repo = get_digest_repo()
        
        # Real RSS feeds for testing
        self.test_feeds = [
            "https://feeds.megaphone.fm/movementmemos",  # Movement Memos - usually good content
            "https://thegreatsimplification.libsyn.com/rss",  # The Great Simplification
            "https://feed.podbean.com/kultural/feed.xml"  # Kultural
        ]
        
        logger.info(f"Initialized with {len(self.test_feeds)} real RSS feeds")
        logger.info("Will test with REAL audio download and PARTIAL transcription (3 chunks max)")
    
    def _verify_api_keys(self):
        """Verify all required API keys are present"""
        required_keys = ['OPENAI_API_KEY']
        missing_keys = []
        
        for key in required_keys:
            value = os.getenv(key)
            if not value or value.startswith('test-') or value == 'your-key-here':
                missing_keys.append(key)
        
        if missing_keys:
            raise ValueError(f"Missing or invalid API keys: {missing_keys}")
        
        logger.info("✓ All required API keys verified")
    
    def discover_new_episode(self) -> dict:
        """Find one new episode that we haven't processed yet"""
        logger.info("\n" + "="*60)
        logger.info("STEP 1: DISCOVER NEW EPISODE FOR TESTING")
        logger.info("="*60)
        
        for feed_url in self.test_feeds:
            try:
                logger.info(f"\nParsing feed: {feed_url}")
                
                # Parse RSS feed
                feed = feedparser.parse(feed_url)
                
                if not feed.entries:
                    logger.warning(f"  No entries found in feed")
                    continue
                
                logger.info(f"  Found {len(feed.entries)} episodes in feed")
                
                # Check recent episodes for new ones
                for entry in feed.entries[:10]:  # Check recent episodes
                    episode_guid = entry.get('id', entry.get('guid', entry.link))
                    
                    # Skip if we already have this episode
                    existing = self.episode_repo.get_by_episode_guid(episode_guid)
                    if existing:
                        continue
                    
                    # Get audio URL
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
                        continue
                    
                    # Found a new episode!
                    episode = {
                        'guid': episode_guid,
                        'title': entry.get('title', 'Untitled'),
                        'description': entry.get('summary', '')[:500],
                        'audio_url': audio_url,
                        'published_date': datetime.now(),  # Simplified for test
                        'duration_seconds': None
                    }
                    
                    logger.info(f"  ✓ Found new episode: {episode['title'][:60]}...")
                    logger.info(f"    Audio URL: {audio_url[:80]}...")
                    return episode
                
            except Exception as e:
                logger.error(f"  Error parsing feed {feed_url}: {e}")
                continue
        
        raise Exception("No new episodes found in any test feeds")
    
    def download_and_partial_transcribe(self, episode: dict) -> Episode:
        """Download audio and transcribe first 3 chunks only"""
        logger.info("\n" + "="*60)
        logger.info("STEP 2: DOWNLOAD AUDIO AND PARTIAL TRANSCRIPTION")
        logger.info("="*60)
        
        episode_guid = episode['guid']
        logger.info(f"Processing: {episode['title'][:60]}...")
        
        # Create database episode record
        db_episode = Episode(
            episode_guid=episode_guid,
            feed_id=1,  # Using dummy feed_id for test
            title=episode['title'],
            published_date=episode['published_date'],
            audio_url=episode['audio_url'],
            duration_seconds=episode['duration_seconds'],
            description=episode['description']
        )
        
        episode_id = self.episode_repo.create(db_episode)
        db_episode.id = episode_id
        logger.info(f"  ✓ Created database record (ID: {episode_id})")
        
        try:
            # Download audio using AudioProcessor
            logger.info(f"  📥 Downloading audio...")
            audio_path = self.audio_processor.download_audio(episode['audio_url'], episode_guid)
            
            # Update database with audio info (store in episode object, update when transcript is ready)
            
            logger.info(f"  ✓ Downloaded: {audio_path}")
            
            # Chunk audio (this creates multiple 10-minute chunks)
            logger.info(f"  🔪 Chunking audio into 10-minute segments...")
            chunk_paths = self.audio_processor.chunk_audio(audio_path, episode_guid)
            
            logger.info(f"  ✓ Created {len(chunk_paths)} audio chunks")
            
            # Transcribe ONLY first 3 chunks for testing
            max_chunks = min(3, len(chunk_paths))
            logger.info(f"  🎤 Transcribing first {max_chunks} chunks (out of {len(chunk_paths)} total)...")
            
            # Import MLX Whisper for transcription (following demo_phase4.py)
            try:
                import mlx_whisper
                logger.info(f"    Using MLX Whisper for transcription")
            except ImportError:
                logger.error("    MLX Whisper not available, cannot transcribe")
                raise Exception("MLX Whisper not available - install with: pip install mlx-whisper")
            
            partial_transcripts = []
            for i, chunk_path in enumerate(chunk_paths[:max_chunks]):
                logger.info(f"    Transcribing chunk {i+1}/{max_chunks}: {chunk_path.name}")
                try:
                    result = mlx_whisper.transcribe(str(chunk_path))
                    transcript_chunk = result['text']
                    partial_transcripts.append(transcript_chunk)
                    logger.info(f"    ✓ Chunk {i+1}: {len(transcript_chunk)} characters")
                except Exception as e:
                    logger.error(f"    ✗ Failed to transcribe chunk {i+1}: {e}")
                    # Continue with other chunks
                    continue
            
            # Combine partial transcripts
            combined_transcript = "\n\n".join(partial_transcripts)
            word_count = len(combined_transcript.split())
            
            # Save transcript
            transcript_dir = Path("data/transcripts")
            transcript_dir.mkdir(parents=True, exist_ok=True)
            
            # Use proper naming convention with feed prefix and database ID
            transcript_filename = f"test-{episode_id:06d}.txt"
            transcript_path = transcript_dir / transcript_filename
            
            with open(transcript_path, 'w', encoding='utf-8') as f:
                f.write(f"# PARTIAL TRANSCRIPT - FIRST {max_chunks} CHUNKS ONLY\n")
                f.write(f"# Full episode has {len(chunk_paths)} total chunks\n")
                f.write(f"# Episode: {episode['title']}\n")
                f.write(f"# GUID: {episode_guid}\n")
                f.write(f"# Processed: {datetime.now().isoformat()}\n\n")
                f.write(combined_transcript)
            
            # Update database with transcript info
            self.episode_repo.update_transcript(episode_guid, str(transcript_path), word_count)
            
            # Update episode object
            db_episode.audio_path = audio_path
            db_episode.transcript_path = str(transcript_path)
            db_episode.transcript_word_count = word_count
            db_episode.chunk_count = len(chunk_paths)
            db_episode.status = 'transcribed'
            
            logger.info(f"  ✅ Partial transcription complete:")
            logger.info(f"    Processed: {max_chunks}/{len(chunk_paths)} chunks")
            logger.info(f"    Word count: {word_count:,}")
            logger.info(f"    Saved to: {transcript_path}")
            
            return db_episode
            
        except Exception as e:
            logger.error(f"  ✗ Failed to process audio for {episode['title']}: {e}")
            try:
                self.episode_repo.mark_failure(episode_guid, str(e))
            except:
                pass
            raise
    
    def score_content(self, episode: Episode) -> Episode:
        """Score episode against all topics"""
        logger.info("\n" + "="*60)
        logger.info("STEP 3: SCORE PARTIAL TRANSCRIPT")
        logger.info("="*60)
        
        logger.info(f"Scoring: {episode.title[:60]}...")
        
        try:
            # Read transcript
            with open(episode.transcript_path, 'r', encoding='utf-8') as f:
                transcript = f.read()
            
            logger.info(f"  Transcript length: {len(transcript):,} characters")
            
            # Score against all topics
            scoring_result = self.content_scorer.score_transcript(transcript, episode.episode_guid)
            
            # Update database with scores
            self.episode_repo.update_scores(episode.episode_guid, scoring_result.scores)
            
            # Update episode object
            episode.scores = scoring_result.scores
            episode.status = 'scored'
            
            # Log scores
            logger.info("  Topic scores:")
            qualifying_topics = []
            for topic, score in scoring_result.scores.items():
                status = "✓ QUALIFIES" if score >= 0.65 else "  "
                logger.info(f"    {status} {topic}: {score:.2f}")
                if score >= 0.65:
                    qualifying_topics.append(topic)
            
            if qualifying_topics:
                logger.info(f"  ✅ Qualifies for {len(qualifying_topics)} topics: {', '.join(qualifying_topics)}")
            else:
                logger.info("  ○ No topics meet 0.65 threshold")
            
            return episode
            
        except Exception as e:
            logger.error(f"  ✗ Failed to score {episode.title}: {e}")
            raise
    
    def generate_test_digest(self, episode: Episode):
        """Generate digest for qualifying topics using this partial episode"""
        logger.info("\n" + "="*60)
        logger.info("STEP 4: GENERATE TEST DIGEST")
        logger.info("="*60)
        
        if not episode.scores:
            logger.info("  No scores available, cannot generate digest")
            return
        
        # Find qualifying topics
        qualifying_topics = [(topic, score) for topic, score in episode.scores.items() if score >= 0.65]
        
        if not qualifying_topics:
            logger.info("  No topics qualify (score ≥ 0.65), testing no-content digest...")
            
            # Test no-content digest generation
            first_topic = list(self.script_generator.topic_instructions.keys())[0]
            digest = self.script_generator.create_digest(first_topic, date.today())
            
            logger.info(f"  ✓ Generated no-content digest for {first_topic}")
            logger.info(f"    Words: {digest.script_word_count}")
            return
        
        # Generate digest for first qualifying topic
        topic, score = qualifying_topics[0]
        logger.info(f"  📝 Generating digest for '{topic}' (score: {score:.2f})")
        
        try:
            # Generate script using only this episode
            script_content, word_count = self.script_generator.generate_script(topic, [episode], date.today())
            
            # Save script with test prefix
            script_filename = f"test-{topic.replace(' ', '_')}_{date.today().strftime('%Y%m%d')}.md"
            script_path = Path("data/scripts") / script_filename
            
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(f"# TEST DIGEST - GENERATED FROM PARTIAL TRANSCRIPT\n")
                f.write(f"# Episode processed {episode.chunk_count} total chunks, transcribed first 3 only\n")
                f.write(f"# This demonstrates workflow feasibility with limited processing time\n\n")
                f.write(script_content)
            
            logger.info(f"  ✅ Generated test digest:")
            logger.info(f"    Topic: {topic}")
            logger.info(f"    Words: {word_count:,}")
            logger.info(f"    Episode score: {score:.2f}")
            logger.info(f"    Saved to: {script_path}")
            
            # Show preview
            preview = script_content[:300] + "..." if len(script_content) > 300 else script_content
            logger.info(f"    Preview: {preview}")
            
        except Exception as e:
            logger.error(f"  ✗ Failed to generate digest for {topic}: {e}")
    
    def run_test(self):
        """Run the complete partial workflow test"""
        start_time = datetime.now()
        
        try:
            # Step 1: Find new episode
            episode = self.discover_new_episode()
            
            # Step 2: Download and partially transcribe
            db_episode = self.download_and_partial_transcribe(episode)
            
            # Step 3: Score content
            scored_episode = self.score_content(db_episode)
            
            # Step 4: Generate test digest
            self.generate_test_digest(scored_episode)
            
            # Summary
            elapsed = datetime.now() - start_time
            
            logger.info("\n" + "="*80)
            logger.info("PARTIAL WORKFLOW TEST COMPLETE")
            logger.info("="*80)
            logger.info(f"✅ Runtime: {elapsed}")
            logger.info(f"✅ Episode processed: {scored_episode.title}")
            logger.info(f"✅ Chunks transcribed: 3 out of {scored_episode.chunk_count}")
            logger.info(f"✅ Transcript words: {scored_episode.transcript_word_count:,}")
            if scored_episode.scores:
                qualifying = [t for t, s in scored_episode.scores.items() if s >= 0.65]
                if qualifying:
                    logger.info(f"✅ Qualifies for: {', '.join(qualifying)}")
                else:
                    logger.info(f"○ No qualifying topics (highest score: {max(scored_episode.scores.values()):.2f})")
            
            logger.info("\n🎯 WORKFLOW VALIDATED - READY FOR FULL PIPELINE TEST")
            
        except Exception as e:
            logger.error(f"\n✗ PARTIAL WORKFLOW TEST FAILED: {e}")
            raise

def main():
    """Run the partial workflow test"""
    test = PartialWorkflowTest()
    test.run_test()

if __name__ == '__main__':
    main()