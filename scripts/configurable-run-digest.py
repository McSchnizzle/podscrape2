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

# Bootstrap phase initialization
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))
from src.utils.phase_bootstrap import bootstrap_phase
bootstrap_phase()

from src.database.models import get_episode_repo, get_digest_repo
from src.generation.script_generator import ScriptGenerator

# Import centralized logging
try:
    from src.utils.logging_config import setup_phase_logging
except ImportError:
    from utils.logging_config import setup_phase_logging

class DigestRunner:
    """Digest script generation phase"""

    def __init__(self, dry_run: bool = False, limit: int = None, verbose: bool = False):
        # Set up phase-specific logging
        self.pipeline_logger = setup_phase_logging("digest", verbose=verbose, console_output=True)
        self.logger = self.pipeline_logger.get_logger()

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

        self.pipeline_logger.log_phase_start("Digest Script Generation Phase")

        if target_date is None:
            target_date = date.today()

        # Note: episodes_data parameter is intentionally ignored when using create_daily_digests
        # This allows the digest phase to work with all qualifying episodes from database,
        # supporting scenarios where no new episodes were scored but backlog exists
        self.logger.info("Generating daily digests for all active topics (automatic topic discovery)")

        # Handle dry run mode
        if self.dry_run:
            self.logger.info("🔍 DRY RUN: Would generate digests for all active topics")
            return {
                'success': True,
                'digests_generated': 0,
                'digests': [],
                'message': "Dry run completed - no digests generated"
            }

        # Use create_daily_digests for proper topic handling and fallback logic
        self.logger.info("Generating daily digests for all qualifying topics")
        try:
            digests = self.script_generator.create_daily_digests(target_date)

            # Log details for each generated digest
            generated_digests = []
            for digest in digests:
                self.logger.info(f"   ✅ Generated digest: {digest.topic}")
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

            # Log completion
            self.pipeline_logger.log_phase_complete(
                f"Generated {len(generated_digests)} digests successfully"
            )

            return {
                'success': True,
                'digests_generated': len(generated_digests),
                'digests_failed': 0,
                'digests': generated_digests,
                'failed': []
            }

        except Exception as e:
            self.logger.error(f"Failed to generate daily digests: {e}")
            self.pipeline_logger.log_phase_complete("Failed to generate digests")

            return {
                'success': False,
                'error': str(e),
                'digests_generated': 0,
                'digests_failed': 1,
                'digests': [],
                'failed': [{'error': str(e)}]
            }


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
        else:
            # Fix: Only read from stdin if it's actually a terminal (interactive mode)
            # When run as subprocess from Web UI, stdin might not be properly set up
            if not sys.stdin.isatty() and hasattr(sys.stdin, 'readable') and sys.stdin.readable():
                # Read from stdin if available, but with timeout to prevent hanging
                try:
                    import select
                    # Check if data is available on stdin without blocking
                    if select.select([sys.stdin], [], [], 0.1)[0]:  # 100ms timeout
                        stdin_content = sys.stdin.read().strip()
                        if stdin_content:
                            episodes_data = json.loads(stdin_content)
                except (json.JSONDecodeError, EOFError, ImportError, OSError):
                    # No valid JSON input from stdin, proceed with None
                    pass

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