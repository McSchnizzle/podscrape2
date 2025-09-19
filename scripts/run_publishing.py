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



def resolve_dry_run_flag(cli_flag: bool) -> bool:
    env_value = os.getenv("DRY_RUN")
    if env_value is not None:
        return env_value.strip().lower() in {"1", "true", "yes", "on"}
    return cli_flag

# Bootstrap phase initialization
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))
from src.utils.phase_bootstrap import bootstrap_phase
bootstrap_phase()

from src.database.models import get_digest_repo
from src.publishing.github_publisher import create_github_publisher
from src.publishing.rss_generator import create_rss_generator, PodcastEpisode, create_podcast_metadata, PodcastMetadata
from src.publishing.retention_manager import create_retention_manager
from src.publishing.vercel_deployer import create_vercel_deployer
from src.utils.rss_timestamps import generate_unique_pubdate

# Import centralized logging
try:
    from src.utils.logging_config import setup_phase_logging
except ImportError:
    from utils.logging_config import setup_phase_logging

class PublishingPipelineRunner:
    """
    Complete publishing pipeline integration
    """
    
    def __init__(self, log_file: str = None, dry_run: bool = False, verbose: bool = False):
        # Set up phase-specific logging
        self.pipeline_logger = setup_phase_logging("publishing", verbose=verbose, console_output=True)
        self.logger = self.pipeline_logger.get_logger()

        self.log_file = log_file or str(self.pipeline_logger.get_log_file())
        self.dry_run = dry_run
        if log_file:
            self.logger.info(f"Logging to: {log_file}")
        self.logger.info(f"Dry run mode: {'ON' if dry_run else 'OFF'}")
        
        # Verify environment variables
        self._verify_environment()
        
        # Initialize components
        self.digest_repo = get_digest_repo()
        
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
        """Verify environment for publishing.

        Requires repository name, and either a GITHUB_TOKEN or GH CLI auth.
        """
        repo = os.getenv('GITHUB_REPOSITORY')
        token = os.getenv('GITHUB_TOKEN')
        if not repo:
            self.logger.error("Missing required environment variable: GITHUB_REPOSITORY")
            raise EnvironmentError("Missing GITHUB_REPOSITORY")
        # If token missing, attempt to detect GH CLI auth (non-fatal)
        if not token:
            try:
                import subprocess
                env_nt = os.environ.copy()
                env_nt.pop('GITHUB_TOKEN', None)
                r = subprocess.run(['gh','auth','status'], capture_output=True, text=True, timeout=10, env=env_nt)
                if r.returncode != 0:
                    self.logger.warning("No GITHUB_TOKEN and GH CLI not authenticated — publishing may fail")
                else:
                    self.logger.info("Using GH CLI authentication for publishing")
            except Exception as e:
                self.logger.warning(f"GH CLI check failed: {e}")
        self.logger.info("Environment variables verified (repository set)")
    
    def find_unpublished_digests(self, days_back: int = 30) -> List[Dict[str, Any]]:
        """Find digests that have MP3 files but haven't been published"""
        self.logger.info(f"Searching for unpublished digests from last {days_back} days...")

        # Get recent digests from database using SQLAlchemy repository
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=days_back)

        recent_digests = self.digest_repo.get_recent_digests(days=days_back)

        digests = []
        for digest_model in recent_digests:
            # Only include digests that have MP3 files
            if not digest_model.mp3_path:
                continue

            digest = {
                'id': digest_model.id,
                'topic': digest_model.topic,
                'digest_date': digest_model.digest_date.isoformat(),
                'mp3_path': digest_model.mp3_path,
                'mp3_title': digest_model.mp3_title,
                'mp3_summary': digest_model.mp3_summary,
                'mp3_duration_seconds': digest_model.mp3_duration_seconds,
                'github_url': digest_model.github_url,
                'created_at': digest_model.generated_at,  # Add creation timestamp for unique pubDate
                'rss_published_at': None  # This field doesn't exist in the new schema
            }

            # Resolve MP3 path if only a filename or missing
            from src.audio.audio_manager import AudioManager
            resolved = AudioManager.resolve_existing_mp3_path(digest['mp3_path'])
            if not resolved:
                self.logger.warning(f"MP3 file not found: {digest['mp3_path']}")
                continue
            else:
                digest['mp3_path'] = str(resolved)
                # Persist normalized path for future runs
                try:
                    self.digest_repo.update_digest(digest_model.id, {'mp3_path': digest['mp3_path']})
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
            
            if self.dry_run:
                self.logger.info("  DRY RUN: Would publish to GitHub")
                return True
            
            # Upload to GitHub (ensure resolved path)
            mp3_path = digest['mp3_path']
            try:
                size = Path(mp3_path).stat().st_size
                self.logger.info(f"  Local MP3 ready: {Path(mp3_path).name} ({size} bytes)")
            except Exception as e:
                self.logger.error(f"  Local MP3 not accessible: {mp3_path} ({e})")
                return False
            mp3_files = [mp3_path]
            digest_date = date.fromisoformat(digest['digest_date'])
            
            # Always call create_daily_release; it uploads missing assets when a release exists
            release = self.github_publisher.create_daily_release(digest_date, mp3_files)
            
            if release:
                # Log assets on the release to aid debugging
                try:
                    asset_names = [a.get('name') for a in (release.assets or [])]
                    self.logger.info(f"  Release assets now: {asset_names}")
                except Exception:
                    pass
                # Update database with GitHub URL
                update_data = {
                    'github_url': release.html_url,
                    'github_release_id': str(release.id),
                    'published_at': datetime.now()
                }
                self.digest_repo.update_digest(digest['id'], update_data)
                
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
                
                # Create unique GUID by including MP3 filename (which contains timestamp)
                mp3_basename = Path(digest['mp3_path']).stem  # Gets filename without extension
                guid = f"digest-{digest['digest_date']}-{digest['topic'].lower().replace(' ', '-')}-{mp3_basename}"

                episode = PodcastEpisode(
                    title=digest['mp3_title'] or f"{digest['topic']} - {digest['digest_date']}",
                    description=digest['mp3_summary'] or f"Daily digest for {digest['topic']}",
                    audio_url=mp3_url,
                    pub_date=generate_unique_pubdate(digest['digest_date'], digest['topic'], digest['created_at']),
                    duration_seconds=digest['mp3_duration_seconds'] or 0,
                    file_size=Path(digest['mp3_path']).stat().st_size if Path(digest['mp3_path']).exists() else 0,
                    guid=guid
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
            # Also write to public for Vercel auto-deploy
            public_file = Path("public") / "daily-digest.xml"
            public_file.parent.mkdir(parents=True, exist_ok=True)
            with open(public_file, 'w', encoding='utf-8') as f:
                f.write(rss_content)
            self.logger.info(f"✅ Wrote public RSS: {public_file}")
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
                    
                    # RSS publication tracking not needed in new schema - deployment success is sufficient
                    
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

        self.pipeline_logger.log_phase_start("Publishing Pipeline Phase")

        try:
            self.logger.info("🚀 Starting complete publishing pipeline...")
            start_time = datetime.now()
            
            # 1. Find unpublished digests
            digests = self.find_unpublished_digests(days_back)
            if not digests:
                self.logger.info("No digests found to publish")
                return True
            
            # 2. Ensure releases and assets for all digests (idempotent)
            ensured = 0
            failures = 0
            for digest in digests:
                if self.publish_digest(digest):
                    ensured += 1
                else:
                    failures += 1
            self.logger.info(f"Ensured GitHub releases for {ensured} digests (failures: {failures})")
            
            # 3. Generate RSS feed (include all digests, published and newly published)
            rss_content = self.generate_rss_feed(digests)
            if not rss_content:
                self.logger.error("Failed to generate RSS feed")
                return False
            
            # 4. Deploy to Vercel (skip when running inside GitHub Actions runner)
            if self.dry_run:
                self.logger.info("DRY RUN: Would deploy to Vercel")
            elif os.getenv("GITHUB_ACTIONS", "").lower() == "true":
                self.logger.info("Skipping Vercel deploy inside GitHub Actions environment")
            else:
                if not self.deploy_to_vercel(rss_content):
                    self.logger.error("Failed to deploy to Vercel")
                    return False

            # 5. Cleanup old files (optional) - only when not running under orchestrator or CI
            if not self.dry_run and os.getenv("GITHUB_ACTIONS", "").lower() != "true" and not os.getenv('ORCHESTRATED_EXECUTION'):
                try:
                    self.retention_manager.cleanup_all()
                    self.logger.info("✅ Cleanup completed")
                except Exception as e:
                    self.logger.warning(f"⚠️  Cleanup failed: {e}")
            
            duration = (datetime.now() - start_time).total_seconds()

            # Log completion
            self.pipeline_logger.log_phase_complete(f"Publishing completed successfully in {duration:.1f}s")

            self.logger.info(f"RSS feed should be available at: https://podcast.paulrbrown.org/daily-digest.xml")
            
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
    
    dry_run = resolve_dry_run_flag(args.dry_run)

    try:
        runner = PublishingPipelineRunner(
            log_file=args.log_file, 
            dry_run=dry_run
        )
        
        success = runner.run_complete_pipeline(args.days_back)

        # Output JSON result for orchestrator
        result = {
            'success': success,
            'message': 'Publishing pipeline completed successfully' if success else 'Publishing pipeline failed',
            'phase': 'publishing'
        }
        print(json.dumps(result))
        sys.stdout.flush()

        sys.exit(0 if success else 1)
        
    except Exception as e:
        # Output JSON error for orchestrator
        error_result = {
            'success': False,
            'error': str(e),
            'phase': 'publishing'
        }
        print(json.dumps(error_result))
        sys.stdout.flush()

        print(f"❌ Failed to run publishing pipeline: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
