#!/usr/bin/env python3
"""
Publishing Pipeline Integration - RSS Generation and Deployment
Handles RSS generation and deployment for MP3s already uploaded by TTS phase:
1. Verifies digests have been uploaded to GitHub releases (by TTS phase)
2. Generates RSS feed XML from database records with GitHub URLs
3. Deploys RSS feed to Vercel at podcast.paulrbrown.org
4. Manages retention and cleanup
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
from src.utils.timezone import get_pacific_now

# Import centralized logging
try:
    from src.utils.logging_config import setup_phase_logging
except ImportError:
    from utils.logging_config import setup_phase_logging

class PublishingPipelineRunner:
    """
    RSS generation and deployment pipeline

    Handles the final publishing step for MP3s that have already been uploaded
    to GitHub releases by the TTS phase. Focuses on RSS generation and Vercel deployment.
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
        self.vercel_deployer = None
        gh_actions_val = os.getenv("GH_ACTIONS", os.getenv("GITHUB_ACTIONS", ""))
        self._is_github_actions = gh_actions_val.lower() == "true"
        self.logger.info(f"GitHub Actions detection: GH_ACTIONS={os.getenv('GH_ACTIONS')}, GITHUB_ACTIONS={os.getenv('GITHUB_ACTIONS')}, _is_github_actions={self._is_github_actions}")
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
            if not self._is_github_actions:
                self.vercel_deployer = create_vercel_deployer()
            else:
                self.logger.info("Skipping Vercel deployer initialization in GitHub Actions environment")
        
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
    
    def recover_orphaned_mp3s(self, days_back: int = 30):
        """Scan for MP3 files without database mp3_path entries and update database.

        This recovers from situations where TTS phase generated MP3s but failed to
        update the database (e.g., due to incorrect update_audio() signature).
        """
        from src.audio.audio_manager import AudioManager
        from pathlib import Path

        self.logger.info("🔍 Scanning for orphaned MP3 files without database entries...")

        # Get recent digests that might have orphaned MP3s
        recent_digests = self.digest_repo.get_recent_digests(days=days_back)

        recovered_count = 0
        for digest_model in recent_digests:
            # Skip digests that already have mp3_path set
            if digest_model.mp3_path:
                continue

            # Skip digests without metadata (can't recover)
            if not digest_model.mp3_title or not digest_model.mp3_summary:
                continue

            # Look for MP3 file matching the topic and date pattern
            topic_slug = digest_model.topic.replace(' ', '_').replace('and', 'and')
            date_str = digest_model.digest_date.strftime('%Y%m%d')

            # Search in common locations
            search_paths = [
                Path('data/completed-tts'),
                Path('.'),  # Current directory (after organize_audio_files)
            ]

            for search_dir in search_paths:
                if not search_dir.exists():
                    continue

                # Look for files matching pattern: Topic_YYYYMMDD_*.mp3
                pattern = f"{topic_slug}_{date_str}_*.mp3"
                matching_files = list(search_dir.glob(pattern))

                if matching_files:
                    # Use the first (should be only) matching file
                    mp3_file = matching_files[0]

                    # Get audio duration using ffprobe
                    try:
                        import subprocess
                        result = subprocess.run(
                            ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
                             '-of', 'csv=p=0', str(mp3_file)],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        duration = int(float(result.stdout.strip())) if result.stdout.strip() else digest_model.mp3_duration_seconds or 0
                    except Exception:
                        duration = digest_model.mp3_duration_seconds or 0

                    # Update database with recovered MP3 path
                    try:
                        self.digest_repo.update_audio(
                            digest_id=digest_model.id,
                            mp3_path=str(mp3_file),
                            duration_seconds=duration,
                            title=digest_model.mp3_title,
                            summary=digest_model.mp3_summary
                        )
                        self.logger.info(f"✅ Recovered orphaned MP3: {mp3_file.name} → digest {digest_model.id}")
                        recovered_count += 1
                        break  # Found and updated, move to next digest
                    except Exception as e:
                        self.logger.warning(f"Failed to update database for recovered MP3 {mp3_file}: {e}")

        if recovered_count > 0:
            self.logger.info(f"🎉 Recovered {recovered_count} orphaned MP3 file(s)")
        else:
            self.logger.info("✓ No orphaned MP3 files found")

    def find_unpublished_digests(self, days_back: int = 30) -> List[Dict[str, Any]]:
        """Find digests that have MP3 files but haven't been published"""
        self.logger.info(f"Searching for unpublished digests from last {days_back} days...")

        # Get recent digests from database using SQLAlchemy repository
        from datetime import timedelta
        cutoff_date = get_pacific_now() - timedelta(days=days_back)

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

            # If already published to GitHub, include regardless of local file existence
            if digest['github_url']:
                self.logger.info(f"Including already published digest: {digest['topic']} - {digest['digest_date']}")
            else:
                # For unpublished digests, check if local MP3 file exists
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

    def upload_digests_to_github(self, digests: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Upload digests to GitHub releases and update database with github_url

        Groups digests by date and creates/updates daily GitHub releases.
        Updates database with github_url for successfully uploaded digests.

        Args:
            digests: List of digest dictionaries with mp3_path

        Returns:
            Dictionary with upload statistics (uploaded, failed, skipped counts)
        """
        from datetime import datetime

        self.logger.info(f"📤 Uploading {len(digests)} digests to GitHub...")

        if self.dry_run:
            self.logger.info("DRY RUN: Would upload digests to GitHub")
            return {'uploaded': len(digests), 'failed': 0, 'skipped': 0}

        # Filter digests that already have github_url (skip re-upload)
        digests_to_upload = [d for d in digests if not d.get('github_url')]
        already_uploaded = len(digests) - len(digests_to_upload)

        if already_uploaded > 0:
            self.logger.info(f"⏭️  Skipping {already_uploaded} digests already uploaded to GitHub")

        if not digests_to_upload:
            self.logger.info("All digests already uploaded to GitHub")
            return {'uploaded': 0, 'failed': 0, 'skipped': already_uploaded}

        # Group digests by date (one release per date)
        digests_by_date = {}
        for digest in digests_to_upload:
            date = digest['digest_date']
            if date not in digests_by_date:
                digests_by_date[date] = []
            digests_by_date[date].append(digest)

        self.logger.info(f"Creating/updating {len(digests_by_date)} GitHub releases...")

        uploaded_count = 0
        failed_count = 0

        # Process each date group
        for release_date_str, date_digests in digests_by_date.items():
            try:
                self.logger.info(f"\n📅 Processing release for {release_date_str}...")

                # Collect MP3 file paths and validate they exist
                mp3_files = []
                for digest in date_digests:
                    mp3_path = digest.get('mp3_path')
                    if mp3_path and Path(mp3_path).exists():
                        mp3_files.append(mp3_path)
                        self.logger.info(f"  • {digest['topic']}: {Path(mp3_path).name}")
                    else:
                        self.logger.warning(f"  ⚠️  Missing MP3 for {digest['topic']}: {mp3_path}")

                if not mp3_files:
                    self.logger.warning(f"  ⚠️  No valid MP3 files found for {release_date_str}, skipping")
                    failed_count += len(date_digests)
                    continue

                # Upload to GitHub (creates/updates daily release)
                release_date = datetime.strptime(release_date_str, '%Y-%m-%d').date()
                github_release = self.github_publisher.create_daily_release(
                    release_date=release_date,
                    mp3_files=mp3_files
                )

                # Update database with github_url for all digests in this release
                github_url = github_release.html_url
                self.logger.info(f"  ✅ Release created: {github_url}")

                for digest in date_digests:
                    try:
                        # Update database
                        self.digest_repo.update_digest(digest['id'], {'github_url': github_url})
                        # Update in-place for RSS generation
                        digest['github_url'] = github_url
                        uploaded_count += 1
                        self.logger.info(f"  ✅ Updated database for {digest['topic']}")
                    except Exception as db_error:
                        self.logger.error(f"  ❌ Failed to update database for {digest['topic']}: {db_error}")
                        failed_count += 1

            except Exception as e:
                self.logger.error(f"❌ Failed to upload {release_date_str}: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
                failed_count += len(date_digests)

        self.logger.info(f"\n📊 Upload Summary:")
        self.logger.info(f"  ✅ Uploaded: {uploaded_count}")
        self.logger.info(f"  ❌ Failed: {failed_count}")
        self.logger.info(f"  ⏭️  Skipped: {already_uploaded}")

        return {
            'uploaded': uploaded_count,
            'failed': failed_count,
            'skipped': already_uploaded
        }

    def publish_digest(self, digest: Dict[str, Any]) -> bool:
        """Verify digest is ready for RSS generation (already uploaded by TTS phase)"""
        try:
            self.logger.info(f"Verifying digest: {digest['topic']} ({digest['digest_date']})")

            if self.dry_run:
                self.logger.info("  DRY RUN: Would verify digest for RSS")
                return True

            # Check if digest already has GitHub URL (uploaded by TTS phase)
            if digest.get('github_url'):
                self.logger.info(f"  ✅ Digest ready for RSS: {digest['github_url']}")
                return True

            # If no GitHub URL, check if a GitHub release exists for this date
            # This handles the case where TTS created a release but database wasn't updated due to workflow failure
            release_date = digest['digest_date']
            tag_name = f"daily-{release_date}"

            try:
                existing_release = self.github_publisher.get_release_by_tag(tag_name)
                if existing_release and existing_release.assets:
                    # Find the MP3 file for this specific digest
                    mp3_filename = Path(digest['mp3_path']).name if digest.get('mp3_path') else None
                    if mp3_filename:
                        # Check if this specific MP3 is in the release assets
                        asset_names = [asset['name'] for asset in existing_release.assets]
                        if mp3_filename in asset_names:
                            # Update database with GitHub URL
                            github_url = f"https://github.com/{self.github_publisher.repository}/releases/tag/{tag_name}"
                            self.logger.info(f"  🔧 Found existing GitHub release, updating database: {github_url}")

                            # Update the digest record with GitHub URL
                            self.digest_repo.update_digest(digest['id'], {'github_url': github_url})

                            # Update the digest dict for RSS generation
                            digest['github_url'] = github_url

                            self.logger.info(f"  ✅ Digest repaired and ready for RSS: {github_url}")
                            return True

            except Exception as repair_error:
                self.logger.warning(f"  ⚠️  Failed to check for existing GitHub release: {repair_error}")

            self.logger.warning(f"  ⚠️  Digest not yet uploaded to GitHub - skipping RSS generation")
            return False

        except Exception as e:
            self.logger.error(f"  ❌ Failed to verify digest: {e}")
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
                    pub_date=generate_unique_pubdate(digest['digest_date'], digest['topic'], digest['created_at'], mp3_path=digest['mp3_path']),
                    duration_seconds=digest['mp3_duration_seconds'] or 0,
                    file_size=Path(digest['mp3_path']).stat().st_size if Path(digest['mp3_path']).exists() else 0,
                    guid=guid
                )
                episodes.append(episode)
            
            # Generate RSS XML
            rss_content = self.rss_generator.generate_rss_feed(episodes)
            
            # Save RSS feed locally
            rss_file = Path("web_ui_hosted") / "public" / "daily-digest.xml"
            rss_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(rss_file, 'w', encoding='utf-8') as f:
                f.write(rss_content)
            
            self.logger.info(f"✅ RSS feed generated: {rss_file}")
            # RSS file is already saved to the correct location (web_ui_hosted/public/)
            # This is the only location that matters for Vercel deployment
            self.logger.info(f"✅ RSS saved to Vercel deployment location: {rss_file}")
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
            
            if self.vercel_deployer is None:
                self.logger.info("Skipping Vercel deploy (deployer not initialized)")
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

    def commit_rss_to_main(self, rss_content: str) -> bool:
        """Commit RSS feed to main branch to trigger Vercel deployment"""
        try:
            self.logger.info("📝 Committing RSS feed to main branch...")

            if self.dry_run:
                self.logger.info("DRY RUN: Would commit RSS feed")
                return True

            # Save RSS content to web_ui_hosted/public/daily-digest.xml (the only location that matters)
            rss_paths = [
                Path("web_ui_hosted/public/daily-digest.xml")
            ]

            for rss_path in rss_paths:
                rss_path.parent.mkdir(parents=True, exist_ok=True)
                with open(rss_path, 'w', encoding='utf-8') as f:
                    f.write(rss_content)
                self.logger.info(f"   📄 Saved RSS to {rss_path}")

            # Git operations
            import subprocess

            # Get remote URL
            github_token = os.getenv('GITHUB_TOKEN')
            github_repo = os.getenv('GITHUB_REPOSITORY')

            if github_token and github_repo:
                remote_url = f"https://x-access-token:{github_token}@github.com/{github_repo}.git"
                remote_name = remote_url
            else:
                remote_name = 'origin'

            # Step 1: Fetch latest changes from remote
            self.logger.info("   🔄 Fetching latest changes from remote...")
            fetch_result = subprocess.run(['git', 'fetch', remote_name],
                                         capture_output=True, text=True, timeout=60)
            if fetch_result.returncode != 0:
                self.logger.warning(f"Git fetch had issues: {fetch_result.stderr}")

            # Step 2: Check if there are any uncommitted changes beyond our RSS file
            status_result = subprocess.run(['git', 'status', '--porcelain'],
                                          capture_output=True, text=True, timeout=30)
            uncommitted_files = [line for line in status_result.stdout.strip().split('\n') 
                                if line and 'daily-digest.xml' not in line]
            
            if uncommitted_files:
                self.logger.warning(f"⚠️  Uncommitted changes detected (will be stashed): {len(uncommitted_files)} files")
                # Stash any other uncommitted changes
                stash_result = subprocess.run(['git', 'stash', 'push', '-u', '-m', 'RSS publish: stashing other changes'],
                                             capture_output=True, text=True, timeout=30)
                stashed = stash_result.returncode == 0
            else:
                stashed = False

            try:
                # Step 3: Pull latest changes with rebase strategy
                self.logger.info("   🔄 Pulling latest changes...")
                if github_token and github_repo:
                    pull_result = subprocess.run(['git', 'pull', '--rebase', remote_url, 'main'],
                                                capture_output=True, text=True, timeout=60)
                else:
                    pull_result = subprocess.run(['git', 'pull', '--rebase', 'origin', 'main'],
                                                capture_output=True, text=True, timeout=60)
                
                if pull_result.returncode != 0 and "up to date" not in pull_result.stderr.lower():
                    self.logger.warning(f"Git pull --rebase had issues: {pull_result.stderr}")
                    # Try to abort rebase if it's in progress
                    subprocess.run(['git', 'rebase', '--abort'], capture_output=True, text=True, timeout=10)

                # Step 4: Add the RSS file
                result = subprocess.run(['git', 'add', 'web_ui_hosted/public/daily-digest.xml'],
                                      capture_output=True, text=True, timeout=30)
                if result.returncode != 0:
                    self.logger.error(f"Git add failed: {result.stderr}")
                    return False

                # Step 5: Commit with timestamp
                timestamp = get_pacific_now().strftime("%Y-%m-%d %H:%M:%S %Z")
                commit_message = f"Update RSS feed - {timestamp}\n\n🤖 Generated with Claude Code\n\nCo-Authored-By: Claude <noreply@anthropic.com>"

                result = subprocess.run(['git', 'commit', '-m', commit_message],
                                      capture_output=True, text=True, timeout=30)
                if result.returncode != 0:
                    if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
                        self.logger.info("   ℹ️  No changes to commit (RSS feed unchanged)")
                        return True
                    else:
                        self.logger.error(f"Git commit failed: {result.stderr}")
                        return False

                # Step 6: Push to remote
                self.logger.info("   📤 Pushing to remote...")
                if github_token and github_repo:
                    result = subprocess.run(['git', 'push', remote_url, 'main'],
                                          capture_output=True, text=True, timeout=60)
                else:
                    result = subprocess.run(['git', 'push', 'origin', 'main'],
                                          capture_output=True, text=True, timeout=60)

                if result.returncode != 0:
                    self.logger.error(f"Git push failed: {result.stderr}")
                    return False

                self.logger.info("   ✅ RSS feed committed and pushed to main")
                self.logger.info("   🚀 Vercel will automatically deploy the updated RSS feed")
                return True

            finally:
                # Step 7: Pop stash if we stashed earlier
                if stashed:
                    self.logger.info("   🔄 Restoring stashed changes...")
                    pop_result = subprocess.run(['git', 'stash', 'pop'],
                                               capture_output=True, text=True, timeout=30)
                    if pop_result.returncode != 0:
                        self.logger.warning(f"⚠️  Failed to pop stash: {pop_result.stderr}")
                        self.logger.warning("   Run 'git stash pop' manually to restore your changes")

        except Exception as e:
            self.logger.error(f"❌ Failed to commit RSS to main: {e}")
            return False

    def run_complete_pipeline(self, days_back: int = 30) -> bool:
        """Run the complete publishing pipeline"""

        self.pipeline_logger.log_phase_start("Publishing Pipeline Phase")

        try:
            self.logger.info("🚀 Starting complete publishing pipeline...")
            start_time = get_pacific_now()

            # 0. RECOVERY: Scan for orphaned MP3 files and update database
            # This recovers from TTS phase failures where MP3 was generated but database wasn't updated
            self.recover_orphaned_mp3s(days_back)

            # 1. Find unpublished digests
            digests = self.find_unpublished_digests(days_back)
            if not digests:
                self.logger.info("No digests found to publish")
                return True

            # 2. Upload digests to GitHub releases (NEW STEP v1.43)
            # This sets github_url in database for digests that don't have it yet
            self.logger.info(f"\n📤 STEP 2: Upload to GitHub")
            upload_stats = self.upload_digests_to_github(digests)
            self.logger.info(f"Upload complete: ✅ {upload_stats['uploaded']} uploaded, "
                           f"❌ {upload_stats['failed']} failed, "
                           f"⏭️  {upload_stats['skipped']} skipped")

            # 3. Verify and repair digests - should now pass since github_url is set by upload step
            # This also handles edge cases where GitHub release exists but database wasn't updated
            self.logger.info(f"\n✅ STEP 3: Verify GitHub Status")
            verified = 0
            not_ready = 0
            for digest in digests:
                if self.publish_digest(digest):
                    verified += 1
                else:
                    not_ready += 1
            self.logger.info(f"Verified {verified} digests ready for RSS (not ready: {not_ready})")

            # 4. Generate RSS feed - includes all uploaded digests with github_url
            # Note: digests list has been modified in-place by upload and verify steps
            self.logger.info(f"\n📝 STEP 4: Generate RSS Feed")
            rss_content = self.generate_rss_feed(digests)
            if not rss_content:
                self.logger.error("Failed to generate RSS feed")
                return False

            # 5. Commit RSS feed to main branch (triggers automatic Vercel deployment)
            self.logger.info(f"\n🚀 STEP 5: Deploy RSS Feed")
            self.logger.info(f"Publishing decision point: dry_run={self.dry_run}, _is_github_actions={self._is_github_actions}")
            if self.dry_run:
                self.logger.info("DRY RUN: Would commit RSS feed to main branch")
            elif self._is_github_actions:
                self.logger.info("Running in GitHub Actions - calling commit_rss_to_main")
                if not self.commit_rss_to_main(rss_content):
                    self.logger.error("Failed to commit RSS feed to main branch")
                    return False
            else:
                # Running locally - can either commit directly or deploy to Vercel
                self.logger.info("Running locally - calling deploy_to_vercel")
                if not self.deploy_to_vercel(rss_content):
                    self.logger.error("Failed to deploy to Vercel")
                    return False

            # 6. Cleanup old files (optional) - only when not running under orchestrator or CI
            if not self.dry_run and not self._is_github_actions and not os.getenv('ORCHESTRATED_EXECUTION'):
                try:
                    self.retention_manager.cleanup_all()
                    self.logger.info("✅ Cleanup completed")
                except Exception as e:
                    self.logger.warning(f"⚠️  Cleanup failed: {e}")
            
            duration = (get_pacific_now() - start_time).total_seconds()

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
