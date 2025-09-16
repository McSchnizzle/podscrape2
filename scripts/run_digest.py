#!/usr/bin/env python3
"""
Digest Generation Phase Script - Script Generation
Independent script for Phase 4: Generate digest scripts for qualifying topics
Reads JSON input from scoring phase or operates on all qualifying episodes.
"""

import os
import sys
import json
import logging
from datetime import datetime, date
from pathlib import Path
import argparse

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

# Set up environment
from dotenv import load_dotenv
load_dotenv()
from src.config.env import require_database_url
require_database_url()

from src.database.models import get_episode_repo, get_digest_repo
from src.generation.script_generator import ScriptGenerator

class DigestRunner:
    """Digest script generation phase"""

    def __init__(self, dry_run: bool = False, limit: int = None, verbose: bool = False):
        # Configure logging
        self.logger = logging.getLogger(__name__)
        level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(level=level, format='%(asctime)s - %(levelname)s - %(message)s')

        self.dry_run = dry_run
        self.limit = limit
        self.verbose = verbose

        # Initialize repositories and components
        self.episode_repo = get_episode_repo()
        self.digest_repo = get_digest_repo()

        # Initialize script generator
        try:
            from src.config.web_config import WebConfigManager
            self.web_config = WebConfigManager()
        except Exception:
            self.web_config = None

        try:
            from src.config.config_manager import ConfigManager
            self.script_generator = ScriptGenerator(
                web_config=self.web_config,
                config_manager=ConfigManager(web_config=self.web_config)
            )
        except Exception:
            self.script_generator = ScriptGenerator(web_config=self.web_config)

        # Verify API keys
        self._verify_dependencies()

        self.logger.info("Digest generation initialized")

    def _verify_dependencies(self):
        """Verify required dependencies"""
        self.logger.info("Verifying dependencies...")

        # Check OpenAI API key
        openai_key = os.getenv('OPENAI_API_KEY')
        if not openai_key or openai_key.startswith('test-') or openai_key == 'your-key-here':
            raise ValueError("Missing or invalid OPENAI_API_KEY")

        self.logger.info("✓ OpenAI API key verified")

    def generate_digests(self, episodes_data=None, target_date=None):
        """Generate digests from scoring phase or all qualifying episodes"""

        if target_date is None:
            target_date = date.today()

        # Handle different input types
        if episodes_data is None:
            # Generate for all qualifying episodes (no input provided)
            self.logger.info("Generating digests for all qualifying episodes from database")
            qualifying_topics = self._get_all_qualifying_topics()
        elif isinstance(episodes_data, str):
            # Load from JSON file
            with open(episodes_data, 'r') as f:
                data = json.load(f)
            if not data.get('success', False):
                return {
                    'success': False,
                    'error': f"Scoring phase failed: {data.get('error', 'Unknown error')}",
                    'digests_generated': 0,
                    'digests': []
                }
            qualifying_topics = self._extract_qualifying_topics_from_data(data)
        elif isinstance(episodes_data, dict):
            # Direct JSON data
            if not episodes_data.get('success', False):
                return {
                    'success': False,
                    'error': f"Scoring phase failed: {episodes_data.get('error', 'Unknown error')}",
                    'digests_generated': 0,
                    'digests': []
                }
            qualifying_topics = self._extract_qualifying_topics_from_data(episodes_data)
        else:
            return {
                'success': False,
                'error': "Invalid input format - expected JSON file path, dict, or None",
                'digests_generated': 0,
                'digests': []
            }

        if not qualifying_topics:
            self.logger.info("No qualifying topics found - generating no-content digest example")
            # Generate one no-content digest as example
            try:
                first_topic = list(self.script_generator.topic_instructions.keys())[0]
                if self.dry_run:
                    self.logger.info(f"🔍 DRY RUN: Would generate no-content digest for '{first_topic}'")
                    return {
                        'success': True,
                        'digests_generated': 0,
                        'digests': [],
                        'message': "No qualifying episodes - dry run completed"
                    }
                else:
                    digest = self.script_generator.create_digest(first_topic, target_date)
                    return {
                        'success': True,
                        'digests_generated': 1,
                        'digests': [self._digest_to_dict(digest)],
                        'message': "No qualifying episodes - generated example digest"
                    }
            except Exception as e:
                return {
                    'success': False,
                    'error': f"Failed to generate no-content digest: {e}",
                    'digests_generated': 0,
                    'digests': []
                }

        # Apply limit
        if self.limit:
            qualifying_topics = list(qualifying_topics)[:self.limit]

        self.logger.info(f"Generating digests for {len(qualifying_topics)} qualifying topics")

        generated_digests = []
        failed_digests = []

        for topic in qualifying_topics:
            try:
                self.logger.info(f"🎯 Generating digest: {topic}")

                if self.dry_run:
                    self.logger.info("🔍 DRY RUN: Would generate digest")
                    generated_digests.append({
                        'topic': topic,
                        'status': 'dry_run',
                        'script_path': None,
                        'script_word_count': 0,
                        'episode_count': 0
                    })
                    continue

                # Generate digest
                digest = self.script_generator.create_digest(topic, target_date)

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

                generated_digests.append(self._digest_to_dict(digest))

            except Exception as e:
                self.logger.error(f"   ✗ Failed to generate digest for {topic}: {e}")
                failed_digests.append({
                    'topic': topic,
                    'error': str(e)
                })

        return {
            'success': len(failed_digests) == 0,
            'digests_generated': len(generated_digests),
            'digests_failed': len(failed_digests),
            'digests': generated_digests,
            'failed': failed_digests
        }

    def _get_all_qualifying_topics(self):
        """Get all qualifying topics from database"""
        try:
            # Get threshold from web config
            threshold = 0.65
            if self.web_config:
                try:
                    threshold = float(self.web_config.get_setting('content_filtering', 'score_threshold', 0.65))
                except Exception:
                    pass

            # Find all episodes with scores above threshold
            episodes = self.episode_repo.get_scored_episodes()
            qualifying_topics = set()

            for episode in episodes:
                if episode.scores:
                    for topic, score in episode.scores.items():
                        if score >= threshold:
                            qualifying_topics.add(topic)

            return qualifying_topics

        except Exception as e:
            self.logger.error(f"Failed to get qualifying topics from database: {e}")
            return set()

    def _extract_qualifying_topics_from_data(self, data):
        """Extract qualifying topics from scoring phase data"""
        qualifying_topics = set()

        for episode in data.get('episodes', []):
            if episode.get('qualifying_topics'):
                qualifying_topics.update(episode['qualifying_topics'])

        return qualifying_topics

    def _digest_to_dict(self, digest):
        """Convert digest object to dictionary"""
        return {
            'id': digest.id,
            'topic': digest.topic,
            'digest_date': digest.digest_date.isoformat(),
            'script_path': digest.script_path,
            'script_word_count': digest.script_word_count,
            'episode_count': digest.episode_count,
            'episode_ids': getattr(digest, 'episode_ids', []),
            'mp3_path': getattr(digest, 'mp3_path', None),
            'mp3_title': getattr(digest, 'mp3_title', None),
            'mp3_summary': getattr(digest, 'mp3_summary', None)
        }

def main():
    parser = argparse.ArgumentParser(description='Digest Generation Phase')
    parser.add_argument('input', nargs='?', help='Input JSON file from scoring phase (optional)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be generated')
    parser.add_argument('--limit', type=int, help='Limit number of digests')
    parser.add_argument('--date', help='Target date (YYYY-MM-DD, default: today)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    parser.add_argument('--output', help='Output JSON file (default: stdout)')

    args = parser.parse_args()

    try:
        runner = DigestRunner(
            dry_run=args.dry_run,
            limit=args.limit,
            verbose=args.verbose
        )

        # Parse target date
        target_date = None
        if args.date:
            try:
                target_date = datetime.strptime(args.date, '%Y-%m-%d').date()
            except ValueError:
                raise ValueError(f"Invalid date format: {args.date} (expected YYYY-MM-DD)")

        # Handle input
        episodes_data = None
        if args.input:
            if args.input.endswith('.json') or '/' in args.input:
                # JSON file input
                episodes_data = args.input
            else:
                raise ValueError(f"Invalid input format: {args.input}")
        elif not sys.stdin.isatty():
            # Read from stdin
            episodes_data = json.load(sys.stdin)

        result = runner.generate_digests(episodes_data, target_date)

        # Output JSON
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(result, f, indent=2)
        else:
            print(json.dumps(result))
            sys.stdout.flush()

        # Exit code
        sys.exit(0 if result['success'] else 1)

    except Exception as e:
        error_result = {
            'success': False,
            'error': str(e),
            'digests_generated': 0,
            'digests': []
        }

        if args.output:
            with open(args.output, 'w') as f:
                json.dump(error_result, f, indent=2)
        else:
            print(json.dumps(error_result))
            sys.stdout.flush()

        sys.exit(1)

if __name__ == '__main__':
    main()