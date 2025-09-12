#!/usr/bin/env python3
"""
Publishing Pipeline Integration - Complete End-to-End Publishing
Connects the main RSS→Audio pipeline with the Phase 7 publishing components:
1. Takes generated MP3s from data/completed-tts/
2. Uploads to GitHub releases
3. Generates RSS feed XML
4. Deploys to Vercel at podcast.paulrbrown.org
"""

import os
import sys
import logging
import json
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
import argparse

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Set up environment
from dotenv import load_dotenv
load_dotenv()

from src.database.models import get_database_manager, get_digest_repo
from src.publishing.github_publisher import create_github_publisher
from src.publishing.rss_generator import create_rss_generator, PodcastEpisode, create_podcast_metadata, PodcastMetadata
from src.publishing.retention_manager import create_retention_manager
from src.publishing.vercel_deployer import create_vercel_deployer

class PublishingPipelineRunner:
    """
    Complete publishing pipeline integration
    """
    
    def __init__(self, log_file: str = None, dry_run: bool = False):
        # Set up comprehensive logging
        if log_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = f"publishing_pipeline_{timestamp}.log"
        
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
        self.dry_run = dry_run
        
        self.logger.info("="*100)
        self.logger.info("RSS PODCAST PUBLISHING PIPELINE - COMPLETE WORKFLOW")
        self.logger.info("="*100)
        self.logger.info(f"Logging to: {log_file}")
        self.logger.info(f"Dry run mode: {'ON' if dry_run else 'OFF'}")
        
        # Verify environment variables
        self._verify_environment()
        
        # Initialize components
        self.db_manager = get_database_manager()
        self.digest_repo = get_digest_repo(self.db_manager)
        
        # Initialize publishing components
        if not dry_run:
            self.github_publisher = create_github_publisher()
            
            # Create podcast metadata for RSS generator
            podcast_metadata = PodcastMetadata(
                title="Daily AI & Tech Digest",
                description="AI-curated daily digest of podcast conversations about artificial intelligence, technology trends, and digital innovation.",
                author="Paul Brown", 
                email="brownpr0@gmail.com",
                category="Technology",
                subcategory="Tech News",
                website_url="https://podcast.paulrbrown.org",
                copyright="© 2025 Paul Brown"
            )
            self.rss_generator = create_rss_generator(podcast_metadata)
            
            self.retention_manager = create_retention_manager()
            self.vercel_deployer = create_vercel_deployer()
        
        self.logger.info("Publishing pipeline initialized successfully")
    
    def _verify_environment(self):
        """Verify required environment variables"""
        required_vars = ['GITHUB_TOKEN', 'GITHUB_REPOSITORY']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            self.logger.error(f"Missing required environment variables: {missing_vars}")
            self.logger.error("Please set these in your .env file:")
            for var in missing_vars:
                self.logger.error(f"  {var}=your_value_here")
            raise EnvironmentError(f"Missing environment variables: {missing_vars}")
        
        self.logger.info("Environment variables verified")
    
    def find_unpublished_digests(self, days_back: int = 30) -> List[Dict[str, Any]]:
        """Find digests that have MP3 files but haven't been published"""
        self.logger.info(f"Searching for unpublished digests from last {days_back} days...")
        
        # Get recent digests from database
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, topic, digest_date, mp3_path, mp3_title, mp3_summary,
                       mp3_duration_seconds, github_url, rss_published_at
                FROM digests 
                WHERE digest_date >= date('now', '-{} days')
                AND mp3_path IS NOT NULL 
                ORDER BY digest_date DESC
            """.format(days_back))
            
            digests = []
            for row in cursor.fetchall():
                digest = {
                    'id': row[0],
                    'topic': row[1],
                    'digest_date': row[2],
                    'mp3_path': row[3],
                    'mp3_title': row[4],
                    'mp3_summary': row[5],
                    'mp3_duration_seconds': row[6],
                    'github_url': row[7],
                    'rss_published_at': row[8]
                }
                
                # Resolve MP3 path if only a filename or missing
                def _resolve_mp3_path(p: str) -> Optional[Path]:
                    if not p:
                        return None
                    candidate = Path(p)
                    if candidate.is_file():
                        return candidate
                    base = Path('data') / 'completed-tts'
                    for folder in [base / 'current', base]:
                        cand = folder / candidate.name
                        if cand.is_file():
                            return cand
                    return None

                resolved = _resolve_mp3_path(digest['mp3_path'])
                if not resolved:
                    self.logger.warning(f"MP3 file not found: {digest['mp3_path']}")
                    continue
                else:
                    digest['mp3_path'] = str(resolved)
                    # Persist normalized path for future runs
                    try:
                        with self.db_manager.get_connection() as conn:
                            conn.execute("UPDATE digests SET mp3_path = ? WHERE id = ?", (digest['mp3_path'], digest['id']))
                            conn.commit()
                    except Exception:
                        pass
                
                digests.append(digest)
        
        self.logger.info(f"Found {len(digests)} digests with MP3 files:")
        for digest in digests:
            status = "PUBLISHED" if digest['github_url'] else "UNPUBLISHED"
            self.logger.info(f"  - {digest['digest_date']} | {digest['topic']} | {status}")
        
        return digests
    
    def publish_digest(self, digest: Dict[str, Any]) -> bool:
        """Publish a single digest to GitHub and update database"""
        try:
            self.logger.info(f"Publishing digest: {digest['topic']} ({digest['digest_date']})")
            
            # Skip if already published
            if digest['github_url']:
                self.logger.info(f"  Already published: {digest['github_url']}")
                return True
            
            if self.dry_run:
                self.logger.info("  DRY RUN: Would publish to GitHub")
                return True
            
            # Upload to GitHub (ensure resolved path)
            mp3_files = [digest['mp3_path']]
            digest_date = date.fromisoformat(digest['digest_date'])
            
            release = self.github_publisher.create_daily_release(digest_date, mp3_files)
            
            if release:
                # Update database with GitHub URL
                with self.db_manager.get_connection() as conn:
                    conn.execute("""
                        UPDATE digests 
                        SET github_url = ?, github_release_id = ?, published_at = ?
                        WHERE id = ?
                    """, (release.html_url, str(release.id), datetime.now().isoformat(), digest['id']))
                    conn.commit()
                
                self.logger.info(f"  ✅ Published to GitHub: {release.html_url}")
                digest['github_url'] = release.html_url  # Update for RSS generation
                return True
            else:
                self.logger.error(f"  ❌ Failed to publish to GitHub")
                return False
                
        except Exception as e:
            self.logger.error(f"  ❌ Failed to publish digest: {e}")
            return False
    
    def generate_rss_feed(self, digests: List[Dict[str, Any]]) -> Optional[str]:
        """Generate RSS feed from published digests"""
        try:
            self.logger.info("Generating RSS feed...")
            
            # Filter to only published digests
            published_digests = [d for d in digests if d.get('github_url')]
            self.logger.info(f"Creating RSS feed with {len(published_digests)} published episodes")
            
            if not published_digests:
                self.logger.warning("No published digests found - cannot generate RSS feed")
                return None
            
            if self.dry_run:
                self.logger.info("DRY RUN: Would generate RSS feed")
                return "<?xml version='1.0'?><!-- DRY RUN RSS FEED -->"
            
            # Convert digests to PodcastEpisode format
            episodes = []
            for digest in published_digests:
                # Extract MP3 URL from GitHub release
                # For now, construct the URL based on the GitHub release pattern
                repo = os.getenv('GITHUB_REPOSITORY', 'user/repo')
                date_str = digest['digest_date']
                mp3_filename = Path(digest['mp3_path']).name
                
                # GitHub release asset URL pattern
                mp3_url = f"https://github.com/{repo}/releases/download/daily-{date_str}/{mp3_filename}"
                
                episode = PodcastEpisode(
                    title=digest['mp3_title'] or f"{digest['topic']} - {digest['digest_date']}",
                    description=digest['mp3_summary'] or f"Daily digest for {digest['topic']}",
                    audio_url=mp3_url,
                    pub_date=datetime.fromisoformat(digest['digest_date'] + 'T12:00:00'),
                    duration_seconds=digest['mp3_duration_seconds'] or 0,
                    file_size=Path(digest['mp3_path']).stat().st_size if Path(digest['mp3_path']).exists() else 0,
                    guid=f"digest-{digest['digest_date']}-{digest['topic'].lower().replace(' ', '-')}"
                )
                episodes.append(episode)
            
            # Generate RSS XML
            rss_content = self.rss_generator.generate_rss_feed(episodes)
            
            # Save RSS feed locally
            rss_file = Path("data") / "rss" / "daily-digest.xml"
            rss_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(rss_file, 'w', encoding='utf-8') as f:
                f.write(rss_content)
            
            self.logger.info(f"✅ RSS feed generated: {rss_file}")
            return rss_content
            
        except Exception as e:
            self.logger.error(f"❌ Failed to generate RSS feed: {e}")
            return None
    
    def deploy_to_vercel(self, rss_content: str) -> bool:
        """Deploy RSS feed to Vercel"""
        try:
            self.logger.info("Deploying to Vercel...")
            
            if self.dry_run:
                self.logger.info("DRY RUN: Would deploy to Vercel")
                return True
            
            # Deploy using Vercel CLI
            result = self.vercel_deployer.deploy_rss_feed(rss_content, production=True)
            
            if result.success:
                self.logger.info(f"✅ Deployed to Vercel: {result.url}")
                
                # Validate deployment
                if self.vercel_deployer.validate_deployment():
                    self.logger.info("✅ Deployment validation passed")
                    
                    # Update database with RSS publication timestamp
                    with self.db_manager.get_connection() as conn:
                        conn.execute("""
                            UPDATE digests 
                            SET rss_published_at = ?
                            WHERE github_url IS NOT NULL 
                            AND rss_published_at IS NULL
                        """, (datetime.now().isoformat(),))
                        conn.commit()
                    
                    return True
                else:
                    self.logger.error("⚠️  Deployment validation failed")
                    return False
            else:
                self.logger.error(f"❌ Vercel deployment failed: {result.error}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Failed to deploy to Vercel: {e}")
            return False
    
    def run_complete_pipeline(self, days_back: int = 30) -> bool:
        """Run the complete publishing pipeline"""
        try:
            self.logger.info("🚀 Starting complete publishing pipeline...")
            start_time = datetime.now()
            
            # 1. Find unpublished digests
            digests = self.find_unpublished_digests(days_back)
            if not digests:
                self.logger.info("No digests found to publish")
                return True
            
            # 2. Publish unpublished digests to GitHub
            published_count = 0
            failed_count = 0
            
            for digest in digests:
                if not digest.get('github_url'):  # Only publish unpublished ones
                    if self.publish_digest(digest):
                        published_count += 1
                    else:
                        failed_count += 1
            
            self.logger.info(f"Publishing results: {published_count} published, {failed_count} failed")
            
            # 3. Generate RSS feed (include all digests, published and newly published)
            rss_content = self.generate_rss_feed(digests)
            if not rss_content:
                self.logger.error("Failed to generate RSS feed")
                return False
            
            # 4. Deploy to Vercel
            if not self.deploy_to_vercel(rss_content):
                self.logger.error("Failed to deploy to Vercel")
                return False
            
            # 5. Cleanup old files (optional)
            if not self.dry_run:
                try:
                    self.retention_manager.cleanup_all()
                    self.logger.info("✅ Cleanup completed")
                except Exception as e:
                    self.logger.warning(f"⚠️  Cleanup failed: {e}")
            
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.info("="*100)
            self.logger.info(f"🎉 Publishing pipeline completed successfully in {duration:.1f}s")
            self.logger.info(f"RSS feed should be available at: https://podcast.paulrbrown.org/daily-digest2.xml")
            self.logger.info("="*100)
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Publishing pipeline failed: {e}")
            return False

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='RSS Podcast Publishing Pipeline')
    parser.add_argument('--days-back', type=int, default=30, 
                       help='Number of days back to search for unpublished digests (default: 30)')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Dry run mode - show what would be done without making changes')
    parser.add_argument('--log-file', 
                       help='Custom log file path')
    parser.add_argument('--verbose', '-v', action='store_true', 
                       help='Verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        runner = PublishingPipelineRunner(
            log_file=args.log_file, 
            dry_run=args.dry_run
        )
        
        success = runner.run_complete_pipeline(args.days_back)
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"❌ Failed to run publishing pipeline: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
