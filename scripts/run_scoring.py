#!/usr/bin/env python3
"""
Content Scoring Phase Script - AI Content Scoring
Independent script for Phase 3: Score transcripts against configured topics
Reads JSON input from audio phase or direct episode data.
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
import argparse

# Bootstrap phase initialization
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))
from src.utils.phase_bootstrap import bootstrap_phase
bootstrap_phase()

from src.database.models import get_episode_repo
from src.scoring.content_scorer import ContentScorer

# Import centralized logging
try:
    from src.utils.logging_config import setup_phase_logging
except ImportError:
    from utils.logging_config import setup_phase_logging

class ScoringRunner:
    """Content scoring phase"""

    def __init__(self, dry_run: bool = False, limit: int = None, verbose: bool = False,
                 ai_model: str = None, max_tokens: int = None, max_input_tokens: int = None,
                 max_episodes_per_batch: int = None, score_threshold: float = None):
        # Set up phase-specific logging
        self.pipeline_logger = setup_phase_logging("scoring", verbose=verbose, console_output=True)
        self.logger = self.pipeline_logger.get_logger()

        self.dry_run = dry_run
        self.limit = limit
        self.verbose = verbose

        # Store Web UI settings (will be passed to ContentScorer)
        self.web_settings = {}
        if ai_model is not None:
            self.web_settings['ai_model'] = ai_model
        if max_tokens is not None:
            self.web_settings['max_tokens'] = max_tokens
        if max_input_tokens is not None:
            self.web_settings['max_input_tokens'] = max_input_tokens
        if max_episodes_per_batch is not None:
            self.web_settings['max_episodes_per_batch'] = max_episodes_per_batch
        if score_threshold is not None:
            self.web_settings['score_threshold'] = score_threshold

        # Initialize repositories and components
        self.episode_repo = get_episode_repo()

        # Pass Web UI settings to ContentScorer via constructor override
        self.content_scorer = self._create_content_scorer()

        # Verify API keys
        self._verify_dependencies()

        self.logger.info("Content scoring initialized")
        if self.web_settings:
            self.logger.info(f"Using Web UI settings: {self.web_settings}")

    def _create_content_scorer(self):
        """Create ContentScorer with Web UI settings override"""
        if self.web_settings:
            # Create a wrapper class that overrides specific settings without modifying the database
            from src.config.web_config import WebConfigManager

            class OverrideWebConfig:
                def __init__(self, base_config, overrides):
                    self.base_config = base_config
                    self.overrides = overrides

                def get_setting(self, category, key, default=None):
                    # Check if we have an override for this setting
                    override_key = f"{category}.{key}"
                    if override_key in self.overrides:
                        return self.overrides[override_key]
                    # Fall back to base config
                    return self.base_config.get_setting(category, key, default)

                def get_category(self, category):
                    result = self.base_config.get_category(category)
                    # Apply any overrides for this category
                    for override_key, value in self.overrides.items():
                        if override_key.startswith(f"{category}."):
                            key = override_key.replace(f"{category}.", "")
                            result[key] = value
                    return result

                # Forward all other methods to base_config
                def __getattr__(self, name):
                    return getattr(self.base_config, name)

            base_config = WebConfigManager()
            overrides = {}

            # Map CLI settings to config paths (only for settings that ContentScorer actually uses)
            for key, value in self.web_settings.items():
                if key == 'ai_model':
                    overrides['ai_content_scoring.model'] = value
                elif key in ['max_tokens', 'max_episodes_per_batch']:
                    overrides[f'ai_content_scoring.{key}'] = value
                elif key == 'score_threshold':
                    overrides['content_filtering.score_threshold'] = value
                # Note: max_input_tokens not used by ContentScorer, skip it

            override_config = OverrideWebConfig(base_config, overrides)
            return ContentScorer(web_config=override_config)
        else:
            return ContentScorer()

    def _verify_dependencies(self):
        """Verify required dependencies"""
        self.logger.info("Verifying dependencies...")

        # Check OpenAI API key
        openai_key = os.getenv('OPENAI_API_KEY')
        if not openai_key or openai_key.startswith('test-') or openai_key == 'your-key-here':
            raise ValueError("Missing or invalid OPENAI_API_KEY")

        self.logger.info("✓ OpenAI API key verified")

    def score_episodes(self, episodes_data):
        """Score episodes from audio phase or direct input"""

        self.pipeline_logger.log_phase_start("Content Scoring Phase")

        if isinstance(episodes_data, str):
            # Load from JSON file
            with open(episodes_data, 'r') as f:
                data = json.load(f)
            if not data.get('success', False):
                return {
                    'success': False,
                    'error': f"Audio phase failed: {data.get('error', 'Unknown error')}",
                    'episodes_scored': 0,
                    'episodes': []
                }
            episodes = data.get('episodes', [])
        elif isinstance(episodes_data, dict):
            # Direct JSON data
            if not episodes_data.get('success', False):
                return {
                    'success': False,
                    'error': f"Audio phase failed: {episodes_data.get('error', 'Unknown error')}",
                    'episodes_scored': 0,
                    'episodes': []
                }
            episodes = episodes_data.get('episodes', [])
        else:
            # Handle list of episode GUIDs
            if isinstance(episodes_data, list):
                episodes = [{'guid': guid} for guid in episodes_data]
            else:
                return {
                    'success': False,
                    'error': "Invalid input format - expected JSON file path, dict, or list of GUIDs",
                    'episodes_scored': 0,
                    'episodes': []
                }

        if not episodes:
            return {
                'success': True,
                'episodes_scored': 0,
                'episodes': [],
                'message': "No episodes to score"
            }

        # Apply limit
        if self.limit:
            episodes = episodes[:self.limit]

        self.logger.info(f"Scoring {len(episodes)} episodes")

        scored_episodes = []
        failed_episodes = []

        for i, episode_data in enumerate(episodes, 1):
            try:
                episode_guid = episode_data['guid']
                episode_title = episode_data.get('title') or episode_guid

                # Get episode from database
                db_episode = self.episode_repo.get_by_episode_guid(episode_guid)
                if not db_episode:
                    if self.dry_run:
                        self.logger.warning(
                            f"Episode {episode_guid} not found in database during dry run; using input payload only"
                        )
                    else:
                        self.logger.error(f"Episode {episode_guid} not found in database")
                        failed_episodes.append({
                            'guid': episode_guid,
                            'title': episode_title,
                            'error': 'Episode not found in database'
                        })
                        continue
                else:
                    episode_title = db_episode.title

                self.logger.info(f"\n[{i}/{len(episodes)}] Scoring: {episode_title}")

                if self.dry_run:
                    self.logger.info("🔍 DRY RUN: Would score episode")
                    scored_episodes.append({
                        'guid': episode_guid,
                        'title': episode_title,
                        'status': 'dry_run',
                        'scores': {}
                    })
                    continue

                if not db_episode.transcript_path or not Path(db_episode.transcript_path).exists():
                    self.logger.error(f"No transcript found for episode {episode_guid}")
                    failed_episodes.append({
                        'guid': episode_guid,
                        'title': db_episode.title,
                        'error': 'No transcript available'
                    })
                    continue

                # Score the episode
                result = self._score_episode(db_episode)
                if result['success']:
                    scored_episodes.append(result)
                else:
                    failed_episodes.append({
                        'guid': episode_guid,
                        'title': db_episode.title,
                        'error': result['error']
                    })

            except Exception as e:
                self.logger.error(f"Failed to score episode: {e}")
                failed_episodes.append({
                    'guid': episode_data.get('guid', 'unknown'),
                    'error': str(e)
                })

        # Log completion
        self.pipeline_logger.log_phase_complete(
            f"Scored {len(scored_episodes)} episodes" +
            (f" ({len(failed_episodes)} failed)" if failed_episodes else "")
        )

        return {
            'success': len(failed_episodes) == 0,
            'episodes_scored': len(scored_episodes),
            'episodes_failed': len(failed_episodes),
            'episodes': scored_episodes,
            'failed': failed_episodes
        }

    def _score_episode(self, db_episode):
        """Score a single episode"""

        try:
            # Read transcript
            with open(db_episode.transcript_path, 'r', encoding='utf-8') as f:
                transcript = f.read()

            self.logger.info(f"Transcript: {len(transcript):,} characters")

            # Score against all topics using GPT
            self.logger.info("🧠 Scoring with GPT-5-mini...")
            scoring_result = self.content_scorer.score_transcript(transcript, db_episode.episode_guid)

            if not scoring_result.success:
                return {
                    'success': False,
                    'error': f"Scoring failed: {scoring_result.error_message}"
                }

            # Update database
            self.episode_repo.update_scores(db_episode.episode_guid, scoring_result.scores)

            self.logger.info(f"✓ Scoring completed in {scoring_result.processing_time:.2f}s")

            # Log scores with qualification status
            self.logger.info("📊 Topic Scores:")
            qualifying_topics = []
            threshold = 0.65  # Default threshold

            # Try to get threshold from web config
            try:
                from src.config.web_config import WebConfigManager
                web_config = WebConfigManager()
                threshold = float(web_config.get_setting('content_filtering', 'score_threshold', 0.65))
            except Exception:
                pass

            for topic, score in scoring_result.scores.items():
                status = "✅ QUALIFIES" if score >= threshold else "   "
                self.logger.info(f"   {status} {topic:<25} {score:.2f}")
                if score >= threshold:
                    qualifying_topics.append(topic)

            # Determine final episode status based on qualification
            if qualifying_topics:
                episode_status = 'scored'
                self.logger.info("📈 Qualification Summary:")
                self.logger.info(f"   ✅ Qualifies for {len(qualifying_topics)} topics: {', '.join(qualifying_topics)}")
            else:
                episode_status = 'not_relevant'
                max_score = max(scoring_result.scores.values()) if scoring_result.scores else 0
                self.logger.info("📈 Qualification Summary:")
                self.logger.info(f"   ❌ No topics meet {threshold} threshold (highest: {max_score:.2f}) - marking as not relevant")

            # Update episode status in database
            self.episode_repo.update_status(db_episode.episode_guid, episode_status)

            return {
                'success': True,
                'guid': db_episode.episode_guid,
                'title': db_episode.title,
                'status': episode_status,
                'scores': scoring_result.scores,
                'qualifying_topics': qualifying_topics,
                'threshold': threshold,
                'processing_time': scoring_result.processing_time
            }

        except Exception as e:
            self.logger.error(f"Scoring failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

def main():
    parser = argparse.ArgumentParser(description='Content Scoring Phase')
    parser.add_argument('input', nargs='?', help='Input JSON file from audio phase, episode GUID, or episode GUIDs (comma-separated)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be scored')
    parser.add_argument('--limit', type=int, help='Limit number of episodes')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    parser.add_argument('--output', help='Output JSON file (default: stdout)')

    # Web UI settings from orchestrator
    parser.add_argument('--ai-model', help='AI model for content scoring (from Web UI)')
    parser.add_argument('--max-tokens', type=int, help='Max output tokens (from Web UI)')
    parser.add_argument('--max-input-tokens', type=int, help='Max input tokens (from Web UI)')
    parser.add_argument('--max-episodes-per-batch', type=int, help='Max episodes per batch (from Web UI)')
    parser.add_argument('--score-threshold', type=float, help='Score threshold for qualification (from Web UI)')

    args = parser.parse_args()

    try:
        runner = ScoringRunner(
            dry_run=args.dry_run,
            limit=args.limit,
            verbose=args.verbose,
            ai_model=args.ai_model,
            max_tokens=args.max_tokens,
            max_input_tokens=args.max_input_tokens,
            max_episodes_per_batch=args.max_episodes_per_batch,
            score_threshold=args.score_threshold
        )

        # Handle input
        if args.input:
            if args.input.endswith('.json') or '/' in args.input:
                # JSON file input
                episodes_data = args.input
            elif ',' in args.input:
                # Comma-separated GUIDs
                guids = [guid.strip() for guid in args.input.split(',')]
                episodes_data = guids
            else:
                # Single episode GUID
                episodes_data = [args.input]
        else:
            # Read from stdin
            import sys
            episodes_data = json.load(sys.stdin)

        result = runner.score_episodes(episodes_data)

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
            'episodes_scored': 0,
            'episodes': []
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
