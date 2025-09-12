#!/usr/bin/env python3
"""
Vercel Deployer for RSS Podcast Digest System
Deploys RSS feed to Vercel using the authenticated CLI
"""

import os
import json
import subprocess
import tempfile
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from ..utils.logging_config import get_logger
from ..utils.error_handling import retry_with_backoff, PodcastError

logger = get_logger(__name__)

@dataclass
class DeploymentResult:
    """Result of a Vercel deployment"""
    success: bool
    url: str
    deployment_id: Optional[str] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None

class VercelDeployer:
    """
    Manages RSS feed deployment to Vercel using the pre-authenticated CLI
    """
    
    def __init__(self, project_name: str = "podcast-paulrbrown-org"):
        """
        Initialize Vercel deployer
        
        Args:
            project_name: Vercel project name (defaults to podcast.paulrbrown.org project)
        """
        self.project_name = project_name
        
        # Verify Vercel CLI is available and authenticated
        self._verify_vercel_cli()
        
        logger.info(f"Vercel Deployer initialized for project: {project_name}")
    
    def _verify_vercel_cli(self):
        """Verify Vercel CLI is installed and authenticated"""
        try:
            # Check if vercel command exists
            result = subprocess.run(['which', 'vercel'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                raise PodcastError("Vercel CLI not found. Please install with: npm install -g vercel")
            
            # Check if authenticated
            result = subprocess.run(['vercel', 'whoami'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                raise PodcastError("Vercel CLI not authenticated. Please run: vercel login")
            
            username = result.stdout.strip()
            logger.info(f"Vercel CLI verified - authenticated as: {username}")
            
        except subprocess.TimeoutExpired:
            raise PodcastError("Vercel CLI verification timed out")
        except Exception as e:
            raise PodcastError(f"Vercel CLI verification failed: {e}")
    
    @retry_with_backoff(max_retries=2, backoff_factor=1.5)
    def deploy_rss_feed(self, rss_content: str, 
                       production: bool = True) -> DeploymentResult:
        """
        Deploy RSS feed content to Vercel
        
        Args:
            rss_content: RSS XML content to deploy
            production: If True, deploy to production; if False, deploy as preview
            
        Returns:
            DeploymentResult with deployment information
        """
        logger.info(f"Deploying RSS feed to Vercel ({'production' if production else 'preview'})")
        start_time = datetime.now()
        
        try:
            # Create temporary deployment directory
            with tempfile.TemporaryDirectory(prefix="rss_deploy_") as temp_dir:
                temp_path = Path(temp_dir)
                
                # Create static site structure for RSS feed
                self._create_deployment_structure(temp_path, rss_content)
                
                # Deploy using Vercel CLI
                deployment_result = self._run_vercel_deploy(temp_path, production)
                
                duration = (datetime.now() - start_time).total_seconds()
                deployment_result.duration_seconds = duration
                
                if deployment_result.success:
                    logger.info(f"Deployment successful in {duration:.1f}s: {deployment_result.url}")
                else:
                    logger.error(f"Deployment failed after {duration:.1f}s: {deployment_result.error}")
                
                return deployment_result
                
        except Exception as e:
            error_msg = f"RSS deployment failed: {e}"
            logger.error(error_msg)
            return DeploymentResult(
                success=False,
                url="",
                error=error_msg,
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )
    
    def _create_deployment_structure(self, temp_path: Path, rss_content: str):
        """Create the deployment directory structure"""
        # Create public directory
        public_dir = temp_path / "public"
        public_dir.mkdir(parents=True, exist_ok=True)
        
        # Save RSS feed as daily-digest.xml
        rss_file = public_dir / "daily-digest.xml"
        with open(rss_file, 'w', encoding='utf-8') as f:
            f.write(rss_content)
        
        # Create vercel.json configuration
        vercel_config = {
            "version": 2,
            "headers": [
                {
                    "source": "/daily-digest.xml",
                    "headers": [
                        {
                            "key": "Content-Type",
                            "value": "application/rss+xml; charset=utf-8"
                        },
                        {
                            "key": "Cache-Control", 
                            "value": "s-maxage=3600, stale-while-revalidate"
                        }
                    ]
                }
            ],
            "redirects": [
                {
                    "source": "/daily-digest2.xml",
                    "destination": "/daily-digest.xml",
                    "permanent": true
                }
            ]
        }
        
        vercel_json = temp_path / "vercel.json"
        with open(vercel_json, 'w', encoding='utf-8') as f:
            json.dump(vercel_config, f, indent=2)
        
        # Create simple index.html for the root
        index_html = public_dir / "index.html"
        with open(index_html, 'w', encoding='utf-8') as f:
            f.write(self._generate_index_html())
        
        logger.debug(f"Created deployment structure in {temp_path}")
    
    def _generate_index_html(self) -> str:
        """Generate a simple index page"""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily AI & Tech Digest Podcast</title>
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 600px; 
            margin: 50px auto; 
            padding: 20px;
            line-height: 1.6;
            color: #333;
        }
        .rss-link { 
            background: #f0f0f0; 
            padding: 15px; 
            border-radius: 8px; 
            margin: 20px 0;
            font-family: monospace;
        }
        .podcast-badge {
            display: inline-block;
            margin: 10px 5px;
        }
        .generated-at {
            color: #666;
            font-size: 0.9em;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #eee;
        }
    </style>
</head>
<body>
    <h1>🎙️ Daily AI & Tech Digest</h1>
    
    <p>Welcome to the automated daily digest of AI and technology podcast episodes. 
    This feed combines the most relevant content from various tech podcasts into 
    focused topic-based episodes.</p>
    
    <h2>RSS Feed</h2>
    <div class="rss-link">
        <strong>RSS URL:</strong> <a href="/daily-digest.xml">https://podcast.paulrbrown.org/daily-digest.xml</a>
    </div>
    
    <p>Subscribe in your favorite podcast app:</p>
    
    <div>
        <a href="https://podcasts.apple.com/podcast/id?feed=https://podcast.paulrbrown.org/daily-digest.xml" class="podcast-badge">
            📱 Apple Podcasts
        </a>
        <a href="https://open.spotify.com/show?feed=https://podcast.paulrbrown.org/daily-digest.xml" class="podcast-badge">
            🎵 Spotify
        </a>
        <a href="https://pocketcasts.com/submit/?url=https://podcast.paulrbrown.org/daily-digest.xml" class="podcast-badge">
            📻 Pocket Casts
        </a>
    </div>
    
    <h2>About</h2>
    <p>This podcast is automatically generated using AI to curate and synthesize 
    content from various tech podcasts. Episodes are scored for relevance and 
    combined into coherent narratives using GPT-5, then converted to speech 
    using ElevenLabs.</p>
    
    <div class="generated-at">
        Generated: """ + datetime.now().strftime('%B %d, %Y at %I:%M %p UTC') + """<br>
        System: RSS Podcast Transcript Digest System
    </div>
</body>
</html>"""
    
    def _run_vercel_deploy(self, temp_path: Path, production: bool) -> DeploymentResult:
        """Run vercel deploy command"""
        try:
            # Build vercel deploy command
            cmd = ['vercel', 'deploy', '--yes']
            
            if production:
                cmd.append('--prod')
            
            # Project name is now handled by vercel.json configuration
            
            # Set working directory to temp deployment directory
            logger.debug(f"Running command: {' '.join(cmd)} (cwd: {temp_path})")
            
            # Run deployment
            result = subprocess.run(
                cmd,
                cwd=temp_path,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                # Extract deployment URL from output
                deployment_url = result.stdout.strip().split('\n')[-1]
                
                # For production deploys, the URL might be the custom domain
                if production and 'podcast.paulrbrown.org' not in deployment_url:
                    # Use the custom domain URL
                    deployment_url = "https://podcast.paulrbrown.org"
                
                return DeploymentResult(
                    success=True,
                    url=deployment_url,
                    deployment_id=self._extract_deployment_id(result.stdout)
                )
            else:
                error_msg = f"Vercel deploy failed (exit {result.returncode}): {result.stderr}"
                return DeploymentResult(
                    success=False,
                    url="",
                    error=error_msg
                )
                
        except subprocess.TimeoutExpired:
            error_msg = "Vercel deployment timed out after 5 minutes"
            return DeploymentResult(success=False, url="", error=error_msg)
        except Exception as e:
            error_msg = f"Vercel deployment error: {e}"
            return DeploymentResult(success=False, url="", error=error_msg)
    
    def _extract_deployment_id(self, output: str) -> Optional[str]:
        """Extract deployment ID from Vercel CLI output"""
        try:
            # Look for deployment ID in output (usually starts with dpl_)
            lines = output.split('\n')
            for line in lines:
                if 'dpl_' in line and 'https://' in line:
                    # Extract deployment ID from URL
                    parts = line.split('/')
                    for part in parts:
                        if part.startswith('dpl_'):
                            return part
            return None
        except Exception:
            return None
    
    def get_deployment_info(self, deployment_url: str = None) -> Optional[Dict[str, Any]]:
        """Get information about current deployment"""
        try:
            cmd = ['vercel', 'list', '--format', 'json']
            if self.project_name:
                cmd.extend(['--scope', self.project_name])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                deployments = json.loads(result.stdout)
                if deployments and len(deployments) > 0:
                    # Return most recent deployment
                    latest = deployments[0]
                    return {
                        'url': latest.get('url'),
                        'name': latest.get('name'),
                        'state': latest.get('state'),
                        'created': latest.get('created'),
                        'deployment_id': latest.get('uid')
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get deployment info: {e}")
            return None
    
    def validate_deployment(self, expected_url: str = None) -> bool:
        """
        Validate that the deployment is working correctly
        
        Args:
            expected_url: Expected deployment URL to validate
            
        Returns:
            True if deployment is accessible and serving RSS content
        """
        try:
            import requests
            
            # Use provided URL or default to production domain
            test_url = expected_url or "https://podcast.paulrbrown.org/daily-digest.xml"
            
            logger.info(f"Validating deployment: {test_url}")
            
            # Test RSS feed endpoint
            response = requests.get(test_url, timeout=30)
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if 'xml' not in content_type:
                logger.warning(f"Unexpected content type: {content_type}")
            
            # Check if response looks like RSS
            content = response.text
            if not content.strip().startswith('<?xml') or '<rss' not in content:
                logger.error("Response doesn't appear to be valid RSS XML")
                return False
            
            logger.info("Deployment validation successful")
            return True
            
        except Exception as e:
            logger.error(f"Deployment validation failed: {e}")
            return False


def create_vercel_deployer(project_name: str = None) -> VercelDeployer:
    """Factory function to create Vercel deployer"""
    return VercelDeployer(project_name or "podcast-paulrbrown-org")


# CLI testing functionality
if __name__ == "__main__":
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description='Vercel Deployer CLI')
    parser.add_argument('--deploy-test', help='Deploy test RSS content from file')
    parser.add_argument('--production', action='store_true', help='Deploy to production (default: preview)')
    parser.add_argument('--validate', help='Validate deployment URL')
    parser.add_argument('--info', action='store_true', help='Show deployment info')
    parser.add_argument('--project', help='Vercel project name')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        deployer = create_vercel_deployer(args.project)
        
        if args.deploy_test:
            if not Path(args.deploy_test).exists():
                print(f"❌ RSS file not found: {args.deploy_test}")
                sys.exit(1)
            
            with open(args.deploy_test, 'r', encoding='utf-8') as f:
                rss_content = f.read()
            
            print(f"Deploying RSS feed from {args.deploy_test}...")
            result = deployer.deploy_rss_feed(rss_content, args.production)
            
            if result.success:
                print(f"✅ Deployment successful!")
                print(f"URL: {result.url}")
                print(f"Duration: {result.duration_seconds:.1f}s")
                
                # Validate deployment
                if deployer.validate_deployment(result.url):
                    print("✅ Deployment validation passed")
                else:
                    print("⚠️  Deployment validation failed")
            else:
                print(f"❌ Deployment failed: {result.error}")
                sys.exit(1)
        
        elif args.validate:
            if deployer.validate_deployment(args.validate):
                print(f"✅ Deployment is valid: {args.validate}")
            else:
                print(f"❌ Deployment validation failed: {args.validate}")
                sys.exit(1)
        
        elif args.info:
            info = deployer.get_deployment_info()
            if info:
                print("📋 Deployment Information:")
                print(f"URL: {info['url']}")
                print(f"Name: {info['name']}")
                print(f"State: {info['state']}")
                print(f"Created: {info['created']}")
                print(f"ID: {info['deployment_id']}")
            else:
                print("No deployment information available")
        
        else:
            print("Use --help for available commands")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
