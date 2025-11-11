#!/usr/bin/env python3
"""
Generate a preview digest script for Script Lab.
Called by Web UI API to show how a digest script would look with current instructions.
"""

import sys
import json
import logging
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.generation.script_generator import ScriptGenerator
from src.database.models import get_episode_repo
from src.config.web_config import WebConfigManager
from src.config.config_manager import ConfigManager

# Disable logging to stdout (we need clean JSON output)
logging.basicConfig(level=logging.ERROR)

def main():
    """
    Generate preview script for given topic.
    Expects JSON input on stdin with: {topic_name: str, instructions_md: str (optional)}
    Returns JSON on stdout with: {success: bool, script: str, char_count: int, word_count: int, error: str (optional)}
    """
    try:
        # Read input from stdin
        input_data = json.loads(sys.stdin.read())
        topic_name = input_data.get('topic_name')
        custom_instructions = input_data.get('instructions_md')

        if not topic_name:
            print(json.dumps({'success': False, 'error': 'Missing topic_name'}))
            return 1

        # Initialize components
        web_config = WebConfigManager()
        config_manager = ConfigManager(web_config=web_config)
        episode_repo = get_episode_repo()
        generator = ScriptGenerator(config_manager=config_manager, web_config=web_config)

        # Get scored episodes for this topic
        threshold = config_manager.get_score_threshold()
        max_episodes = generator.max_episodes_per_digest

        # Use get_scored_episodes_for_topic method
        scored_episodes = episode_repo.get_scored_episodes_for_topic(
            topic=topic_name,
            min_score=threshold,
            exclude_digested=False  # Include digested episodes for preview
        )

        # Limit to max episodes
        scored_episodes = scored_episodes[:max_episodes]

        if not scored_episodes:
            print(json.dumps({
                'success': True,
                'script': f'No scored episodes found for {topic_name} above threshold {threshold}.\n\nPlease run the scoring phase to get scored episodes.',
                'char_count': 0,
                'word_count': 0,
                'mode': 'none'
            }))
            return 0

        # If custom instructions provided, temporarily override topic instructions
        # (Note: This is just for preview - doesn't save to database)
        original_topics = generator.topics
        if custom_instructions:
            for topic in generator.topics:
                if topic.name == topic_name:
                    topic.content = custom_instructions
                    break

        # Generate script
        try:
            from datetime import date
            today = date.today()
            script, token_count = generator.generate_script(topic_name, scored_episodes, today)

            # Restore original topics
            generator.topics = original_topics

            # Calculate stats
            char_count = len(script)
            word_count = len(script.split())

            # Detect mode (dialogue vs narrative)
            # Check for both colon format (SPEAKER_1:) and bracket format (SPEAKER_1 [)
            mode = 'dialogue' if ('SPEAKER_1:' in script or 'SPEAKER_2:' in script or
                                 'SPEAKER_1 [' in script or 'SPEAKER_2 [' in script) else 'narrative'

            print(json.dumps({
                'success': True,
                'script': script,
                'char_count': char_count,
                'word_count': word_count,
                'token_count': token_count,
                'episode_count': len(scored_episodes),
                'mode': mode
            }))
            return 0

        except Exception as e:
            print(json.dumps({
                'success': False,
                'error': f'Script generation failed: {str(e)}'
            }))
            return 1

    except json.JSONDecodeError as e:
        print(json.dumps({'success': False, 'error': f'Invalid JSON input: {str(e)}'}))
        return 1
    except Exception as e:
        print(json.dumps({'success': False, 'error': f'Unexpected error: {str(e)}'}))
        return 1

if __name__ == '__main__':
    sys.exit(main())
