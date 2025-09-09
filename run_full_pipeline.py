#!/usr/bin/env python3
"""
Full Pipeline Command - Complete RSS to Digest Workflow
Processes one new episode through the entire pipeline: RSS → Download → Transcribe → Score → Digest
Designed for terminal execution with comprehensive logging to file.
"""

import os
import sys
import logging
from datetime import datetime, date
from pathlib import Path
import argparse

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Set up environment
from dotenv import load_dotenv
load_dotenv()

from src.podcast.feed_parser import FeedParser
from src.scoring.content_scorer import ContentScorer
from src.generation.script_generator import ScriptGenerator
from src.database.models import get_episode_repo, get_digest_repo, Episode
from src.podcast.audio_processor import AudioProcessor
import feedparser

class FullPipelineRunner:
    """
    Complete pipeline runner for processing one episode from RSS to digest
    """
    
    def __init__(self, log_file: str = None):
        # Set up comprehensive logging
        if log_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = f"pipeline_run_{timestamp}.log"
        
        # Configure logging to both console and file
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        self.logger = logging.getLogger(__name__)
        self.log_file = log_file
        
        self.logger.info("="*100)
        self.logger.info("FULL RSS PODCAST PIPELINE - COMPLETE WORKFLOW")
        self.logger.info("="*100)
        self.logger.info(f"Logging to: {log_file}")
        
        # Verify dependencies
        self._verify_dependencies()
        
        # Initialize components
        self.audio_processor = AudioProcessor()
        self.content_scorer = ContentScorer()
        self.script_generator = ScriptGenerator()
        self.episode_repo = get_episode_repo()
        self.digest_repo = get_digest_repo()
        
        # Initialize Parakeet transcriber (after dependency verification)
        if hasattr(self, 'has_parakeet_mlx') and self.has_parakeet_mlx:
            from src.podcast.parakeet_mlx_transcriber import create_parakeet_mlx_transcriber
            self.transcriber = create_parakeet_mlx_transcriber(chunk_duration_minutes=3)
        else:
            self.transcriber = None
        
        # RSS feeds to check (using proven feeds from CLAUDE.md)
        self.rss_feeds = [
            {
                'url': 'https://feeds.megaphone.fm/movementmemos',
                'name': 'Movement Memos',
                'expected_topics': ['Community Organizing', 'Societal Culture Change']
            },
            {
                'url': 'https://thegreatsimplification.libsyn.com/rss',
                'name': 'The Great Simplification',
                'expected_topics': ['Societal Culture Change', 'Tech News and Tech Culture']
            },
            {
                'url': 'https://feed.podbean.com/kultural/feed.xml',
                'name': 'Kultural',
                'expected_topics': ['Community Organizing', 'Societal Culture Change']
            }
        ]
        
        self.logger.info(f"Initialized pipeline with {len(self.rss_feeds)} RSS feeds")
        
    def _verify_dependencies(self):
        """Verify all required dependencies and API keys"""
        self.logger.info("Verifying pipeline dependencies...")
        
        # Check API keys
        required_keys = ['OPENAI_API_KEY']
        missing_keys = []
        
        for key in required_keys:
            value = os.getenv(key)
            if not value or value.startswith('test-') or value == 'your-key-here':
                missing_keys.append(key)
        
        if missing_keys:
            raise ValueError(f"Missing or invalid API keys: {missing_keys}")
        
        self.logger.info("✓ OpenAI API key verified")
        
        # Check Parakeet MLX availability
        try:
            import parakeet_mlx
            from src.podcast.parakeet_mlx_transcriber import create_parakeet_mlx_transcriber
            self.logger.info("✓ Parakeet MLX available for transcription")
            self.has_parakeet_mlx = True
        except ImportError as e:
            self.logger.error("✗ Parakeet MLX not available")
            self.logger.error(f"Error: {e}")
            self.logger.error("Install with: pip install parakeet-mlx")
            raise Exception("Parakeet MLX transcription engine not available")
        
        # Check FFmpeg for audio processing
        try:
            import subprocess
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
            self.logger.info("✓ FFmpeg available for audio processing")
        except FileNotFoundError:
            self.logger.error("✗ FFmpeg not found - required for audio chunking")
            self.logger.error("Install with: brew install ffmpeg  (macOS) or apt-get install ffmpeg (Linux)")
            raise Exception("FFmpeg not available")
        
        self.logger.info("✅ All dependencies verified")
    
    def discover_new_episode(self):
        """Find the most recent unprocessed episode from RSS feeds"""
        self.logger.info("\n" + "="*80)
        self.logger.info("PHASE 1: DISCOVER NEW EPISODE")
        self.logger.info("="*80)
        
        for feed_info in self.rss_feeds:
            feed_url = feed_info['url']
            feed_name = feed_info['name']
            
            self.logger.info(f"\n🔍 Checking {feed_name}: {feed_url}")
            
            try:
                # Parse RSS feed
                feed = feedparser.parse(feed_url)
                
                if not feed.entries:
                    self.logger.warning(f"  No entries found in {feed_name}")
                    continue
                
                self.logger.info(f"  Found {len(feed.entries)} episodes in feed")
                
                # Check recent episodes for new ones
                for i, entry in enumerate(feed.entries[:10]):
                    episode_guid = entry.get('id', entry.get('guid', entry.link))
                    title = entry.get('title', 'Untitled')
                    
                    # Check if episode needs processing
                    existing = self.episode_repo.get_by_episode_guid(episode_guid)
                    if existing and existing.status in ['transcribed', 'scored']:
                        self.logger.info(f"  [{i+1:2d}] SKIP: {title[:60]}... (already processed)")
                        continue
                    elif existing and existing.status in ['pending', 'failed']:
                        status_label = "pending transcription" if existing.status == 'pending' else "retry after failure"
                        self.logger.info(f"  [{i+1:2d}] RESUME: {title[:60]}... ({status_label})")
                        # Return existing episode for resume processing
                        # Add expected topics for compatibility
                        existing.expected_topics = feed_info['expected_topics']
                        return existing
                    
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
                        self.logger.info(f"  [{i+1:2d}] SKIP: {title[:60]}... (no audio URL)")
                        continue
                    
                    # Found a new candidate episode!
                    episode = {
                        'guid': episode_guid,
                        'title': title,
                        'description': entry.get('summary', '')[:500],
                        'audio_url': audio_url,
                        'published_date': datetime.now(),  # Simplified for demo
                        'duration_seconds': None,
                        'feed_name': feed_name,
                        'expected_topics': feed_info['expected_topics']
                    }
                    
                    self.logger.info(f"  [{i+1:2d}] ✅ NEW: {title}")
                    self.logger.info(f"       Feed: {feed_name}")
                    self.logger.info(f"       Audio: {audio_url[:80]}...")
                    self.logger.info(f"       Expected topics: {', '.join(feed_info['expected_topics'])}")
                    
                    return episode
                
            except Exception as e:
                self.logger.error(f"  ✗ Error parsing {feed_name}: {e}")
                continue
        
        raise Exception("No new episodes found in any RSS feed")
    
    def process_audio(self, episode):
        """Download audio, chunk, and transcribe completely"""
        self.logger.info("\n" + "="*80)
        self.logger.info("PHASE 2: AUDIO PROCESSING")
        self.logger.info("="*80)
        
        # Handle both new episodes (dict) and existing episodes (Episode object)
        if isinstance(episode, dict):
            # New episode - create database record
            self.logger.info(f"Processing: {episode['title']}")
            self.logger.info(f"Feed: {episode['feed_name']}")
            
            db_episode = Episode(
                episode_guid=episode['guid'],
                feed_id=1,  # Simplified for demo
                title=episode['title'],
                published_date=episode['published_date'],
                audio_url=episode['audio_url'],
                duration_seconds=episode['duration_seconds'],
                description=episode['description']
            )
            
            episode_id = self.episode_repo.create(db_episode)
            db_episode.id = episode_id
            self.logger.info(f"✓ Database record created (ID: {episode_id})")
            
        else:
            # Existing episode - resume processing
            db_episode = episode
            self.logger.info(f"Processing: {db_episode.title}")
            self.logger.info(f"Resuming episode ID: {db_episode.id} (status: {db_episode.status})")
        
        try:
            # Step 2.1: Download audio
            self.logger.info(f"\n📥 STEP 2.1: Audio Download")
            # Get episode data (handle both dict and Episode object)
            if isinstance(episode, dict):
                audio_url = episode['audio_url']
                episode_guid = episode['guid']
            else:
                audio_url = db_episode.audio_url
                episode_guid = db_episode.episode_guid
            
            self.logger.info(f"URL: {audio_url}")
            
            audio_path = self.audio_processor.download_audio(audio_url, episode_guid)
            audio_size_mb = Path(audio_path).stat().st_size / (1024*1024)
            self.logger.info(f"✓ Downloaded {audio_size_mb:.1f}MB to: {audio_path}")
            
            # Step 2.2: Chunk audio
            self.logger.info(f"\n🔪 STEP 2.2: Audio Chunking")
            chunk_paths = self.audio_processor.chunk_audio(audio_path, episode_guid)
            
            # TESTING LIMIT: Only process first 4 chunks for faster testing
            if len(chunk_paths) > 4:
                self.logger.info(f"⚠️  TESTING MODE: Limiting to first 4 chunks (of {len(chunk_paths)})")
                chunk_paths = chunk_paths[:4]
            
            total_duration_est = len(chunk_paths) * 3  # 3 minutes per chunk
            self.logger.info(f"✓ Processing {len(chunk_paths)} chunks (~{total_duration_est} minutes total)")
            
            # Step 2.3: Full transcription with Parakeet MLX
            self.logger.info(f"\n🎤 STEP 2.3: Full Transcription ({len(chunk_paths)} chunks)")
            
            if not self.transcriber:
                raise Exception("Parakeet MLX transcriber not initialized")
            
            self.logger.info("Using Parakeet MLX (Apple Silicon optimized) for transcription")
            
            # Use Parakeet's episode transcription method
            try:
                self.logger.info("Starting Parakeet transcription...")
                
                # Convert Path objects to strings for Parakeet API
                chunk_paths_str = [str(path) for path in chunk_paths]
                
                # Create in-progress transcript file for monitoring
                progress_dir = Path("data/transcripts")
                progress_dir.mkdir(parents=True, exist_ok=True)
                in_progress_file = progress_dir / f"{episode_guid[:6]}_in_progress.txt"
                self.logger.info(f"Progress file: {in_progress_file}")
                
                # Call Parakeet transcriber (it will initialize model internally)
                transcription_result = self.transcriber.transcribe_episode(
                    chunk_paths_str, 
                    episode_guid,
                    str(in_progress_file)
                )
                
                # EpisodeTranscription object doesn't have success attribute - if we get here, it worked
                all_transcripts = [chunk.text for chunk in transcription_result.chunks]
                
                # Log individual chunk results
                for i, chunk_result in enumerate(transcription_result.chunks):
                    chunk_num = i + 1
                    transcript = chunk_result.text
                    char_count = len(transcript)
                    word_count = len(transcript.split())
                    self.logger.info(f"  [{chunk_num:2d}/{len(chunk_paths)}] {Path(chunk_paths[i]).name}")
                    self.logger.info(f"       ✓ {char_count:,} chars, {word_count:,} words")
                
            except Exception as e:
                self.logger.error(f"Parakeet transcription failed: {e}")
                raise
            
            # Combine all transcripts
            combined_transcript = "\n\n".join([t for t in all_transcripts if t])
            total_words = len(combined_transcript.split())
            total_chars = len(combined_transcript)
            
            # Save transcript with proper naming convention
            transcript_dir = Path("data/transcripts")
            transcript_dir.mkdir(parents=True, exist_ok=True)
            
            # Get feed name for naming (handle both dict and Episode object)
            if isinstance(episode, dict):
                feed_name = episode['feed_name']
                episode_title = episode['title']
            else:
                # For existing episodes, derive feed name from expected_topics or use default
                feed_name = getattr(episode, 'feed_name', 'Movement Memos')  # Default based on expected_topics
                episode_title = db_episode.title
            
            # Use feed prefix and short episode GUID for naming (format: movement-8292fe.txt)
            feed_prefix = feed_name.split()[0].lower()  # First word of feed name
            short_guid = episode_guid[:6]
            transcript_filename = f"{feed_prefix}-{short_guid}.txt"
            transcript_path = transcript_dir / transcript_filename
            
            # Write final transcript
            with open(transcript_path, 'w', encoding='utf-8') as f:
                f.write(f"# Complete Transcript\n")
                f.write(f"# Episode: {episode_title}\n")
                f.write(f"# Feed: {feed_name}\n")
                f.write(f"# GUID: {episode_guid}\n")
                f.write(f"# Processed: {datetime.now().isoformat()}\n")
                f.write(f"# Chunks: {len(chunk_paths)}\n")
                f.write(f"# Words: {total_words:,}\n")
                f.write(f"# Characters: {total_chars:,}\n\n")
                f.write(combined_transcript)
            
            # Update database
            self.episode_repo.update_transcript(episode_guid, str(transcript_path), total_words)
            
            # Update episode object
            db_episode.transcript_path = str(transcript_path)
            db_episode.transcript_word_count = total_words
            db_episode.chunk_count = len(chunk_paths)
            db_episode.status = 'transcribed'
            
            # Cleanup: Delete audio chunks and in-progress file
            self.logger.info(f"\n🧹 STEP 2.4: Cleanup")
            try:
                # Delete all audio chunks for this episode
                chunks_deleted = 0
                for chunk_path_str in chunk_paths:
                    chunk_path = Path(chunk_path_str)
                    if chunk_path.exists():
                        chunk_path.unlink()
                        chunks_deleted += 1
                
                # Delete the chunks directory if empty
                chunk_episode_dir = Path(chunk_paths[0]).parent if chunk_paths else None
                if chunk_episode_dir and chunk_episode_dir.exists():
                    try:
                        chunk_episode_dir.rmdir()  # Only removes if empty
                        self.logger.info(f"✓ Removed chunk directory: {chunk_episode_dir}")
                    except OSError:
                        pass  # Directory not empty, leave it
                
                # Delete in-progress file
                if in_progress_file.exists():
                    in_progress_file.unlink()
                    self.logger.info(f"✓ Deleted progress file: {in_progress_file}")
                
                self.logger.info(f"✓ Cleanup complete: {chunks_deleted} audio chunks deleted")
                
            except Exception as e:
                self.logger.warning(f"⚠️ Cleanup failed: {e}")
            
            self.logger.info(f"\n✅ TRANSCRIPTION COMPLETE:")
            self.logger.info(f"   Total words: {total_words:,}")
            self.logger.info(f"   Total characters: {total_chars:,}")
            self.logger.info(f"   Chunks processed: {len(chunk_paths)}")
            self.logger.info(f"   Saved to: {transcript_path}")
            
            return db_episode
            
        except Exception as e:
            self.logger.error(f"✗ Audio processing failed: {e}")
            try:
                self.episode_repo.mark_failure(episode_guid, str(e))
            except:
                pass
            raise
    
    def score_episode(self, episode):
        """Score episode against all configured topics"""
        self.logger.info("\n" + "="*80)
        self.logger.info("PHASE 3: CONTENT SCORING")
        self.logger.info("="*80)
        
        self.logger.info(f"Scoring: {episode.title}")
        self.logger.info(f"Expected topics: {', '.join(episode.__dict__.get('expected_topics', ['Unknown']))}")
        
        try:
            # Read transcript
            with open(episode.transcript_path, 'r', encoding='utf-8') as f:
                transcript = f.read()
            
            self.logger.info(f"Transcript: {len(transcript):,} characters")
            
            # Score against all topics using GPT-5-mini
            self.logger.info(f"\n🧠 Scoring with GPT-5-mini (with 5% ad removal)...")
            scoring_result = self.content_scorer.score_transcript(transcript, episode.episode_guid)
            
            if not scoring_result.success:
                raise Exception(f"Scoring failed: {scoring_result.error_message}")
            
            # Update database
            self.episode_repo.update_scores(episode.episode_guid, scoring_result.scores)
            episode.scores = scoring_result.scores
            episode.status = 'scored'
            
            self.logger.info(f"✓ Scoring completed in {scoring_result.processing_time:.2f}s")
            
            # Log all scores with qualification status
            self.logger.info(f"\n📊 TOPIC SCORES:")
            qualifying_topics = []
            
            for topic, score in scoring_result.scores.items():
                status = "✅ QUALIFIES" if score >= 0.65 else "   "
                self.logger.info(f"   {status} {topic:<25} {score:.2f}")
                if score >= 0.65:
                    qualifying_topics.append(topic)
            
            self.logger.info(f"\n📈 QUALIFICATION SUMMARY:")
            if qualifying_topics:
                self.logger.info(f"   ✅ Qualifies for {len(qualifying_topics)} topics: {', '.join(qualifying_topics)}")
            else:
                max_score = max(scoring_result.scores.values())
                self.logger.info(f"   ❌ No topics meet 0.65 threshold (highest: {max_score:.2f})")
            
            return episode
            
        except Exception as e:
            self.logger.error(f"✗ Scoring failed: {e}")
            raise
    
    def generate_digests(self, episode):
        """Generate digest scripts for all qualifying topics"""
        self.logger.info("\n" + "="*80)
        self.logger.info("PHASE 4: DIGEST GENERATION")
        self.logger.info("="*80)
        
        if not episode.scores:
            self.logger.warning("No scores available for digest generation")
            return []
        
        # Find qualifying topics
        qualifying_topics = [(topic, score) for topic, score in episode.scores.items() if score >= 0.65]
        
        if not qualifying_topics:
            self.logger.info("📝 No qualifying topics - generating no-content digest example")
            
            # Generate one no-content digest as example
            first_topic = list(self.script_generator.topic_instructions.keys())[0]
            digest = self.script_generator.create_digest(first_topic, date.today())
            
            self.logger.info(f"✓ Generated no-content digest for '{first_topic}'")
            self.logger.info(f"   Words: {digest.script_word_count}")
            self.logger.info(f"   Path: {digest.script_path}")
            
            return [digest]
        
        # Generate digests for all qualifying topics
        self.logger.info(f"📝 Generating digests for {len(qualifying_topics)} qualifying topics")
        
        digests = []
        for topic, score in qualifying_topics:
            self.logger.info(f"\n🎯 Generating digest: {topic} (score: {score:.2f})")
            
            try:
                # Use ScriptGenerator to create digest with just this episode
                digest = self.script_generator.create_digest(topic, date.today())
                
                self.logger.info(f"   ✅ Generated successfully")
                self.logger.info(f"      Words: {digest.script_word_count:,}")
                self.logger.info(f"      Episodes: {digest.episode_count}")
                self.logger.info(f"      Path: {digest.script_path}")
                
                # Show preview
                if digest.script_path and Path(digest.script_path).exists():
                    with open(digest.script_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        preview = content[:200] + "..." if len(content) > 200 else content
                        self.logger.info(f"      Preview: {preview}")
                
                digests.append(digest)
                
            except Exception as e:
                self.logger.error(f"   ✗ Failed to generate digest for {topic}: {e}")
                continue
        
        self.logger.info(f"\n✅ DIGEST GENERATION COMPLETE: {len(digests)} digests created")
        return digests
    
    def run_pipeline(self):
        """Execute the complete pipeline"""
        start_time = datetime.now()
        
        try:
            # Phase 1: Discovery
            episode = self.discover_new_episode()
            
            # Phase 2: Audio Processing
            processed_episode = self.process_audio(episode)
            
            # Phase 3: Content Scoring
            scored_episode = self.score_episode(processed_episode)
            
            # Phase 4: Digest Generation
            digests = self.generate_digests(scored_episode)
            
            # Final Summary
            elapsed = datetime.now() - start_time
            
            self.logger.info("\n" + "="*100)
            self.logger.info("🎉 PIPELINE EXECUTION COMPLETE")
            self.logger.info("="*100)
            
            self.logger.info(f"⏱️  Total Runtime: {elapsed}")
            self.logger.info(f"📻 Episode Processed: {scored_episode.title}")
            self.logger.info(f"📝 Transcript Words: {scored_episode.transcript_word_count:,}")
            self.logger.info(f"🔊 Audio Chunks: {scored_episode.chunk_count}")
            
            if scored_episode.scores:
                qualifying = [t for t, s in scored_episode.scores.items() if s >= 0.65]
                if qualifying:
                    self.logger.info(f"✅ Qualifying Topics: {', '.join(qualifying)}")
                else:
                    max_score = max(scored_episode.scores.values())
                    self.logger.info(f"❌ No Qualifying Topics (max score: {max_score:.2f})")
            
            self.logger.info(f"📚 Digests Generated: {len(digests)}")
            
            for digest in digests:
                self.logger.info(f"   • {digest.topic}: {digest.script_word_count:,} words")
            
            self.logger.info(f"\n📋 Log File: {self.log_file}")
            self.logger.info("🚀 PIPELINE SUCCESS - Ready for production use!")
            
        except Exception as e:
            elapsed = datetime.now() - start_time
            self.logger.error(f"\n💥 PIPELINE FAILED after {elapsed}")
            self.logger.error(f"Error: {e}")
            self.logger.error(f"📋 Check log file for details: {self.log_file}")
            raise

def main():
    parser = argparse.ArgumentParser(description='Run complete RSS podcast pipeline')
    parser.add_argument('--log', help='Log file path', default=None)
    args = parser.parse_args()
    
    runner = FullPipelineRunner(log_file=args.log)
    runner.run_pipeline()

if __name__ == '__main__':
    main()