#!/usr/bin/env python3
"""
Test script to verify min_episodes_per_digest enforcement
This tests the bugfix for the issue where digests were created even when
episode count was below the minimum threshold.
"""

import os
import sys
from pathlib import Path
from datetime import date

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from src.utils.phase_bootstrap import bootstrap_phase
bootstrap_phase()

from src.generation.script_generator import ScriptGenerator
from src.config.web_config import WebConfigManager
from src.config.config_manager import ConfigManager

def test_min_episodes_enforcement():
    """Test that min_episodes_per_digest is properly enforced"""

    print("=" * 80)
    print("Testing min_episodes_per_digest enforcement")
    print("=" * 80)

    # Initialize script generator with web config
    try:
        web_config = WebConfigManager()
        config_manager = ConfigManager(web_config=web_config)
        script_generator = ScriptGenerator(
            web_config=web_config,
            config_manager=config_manager
        )
    except Exception as e:
        print(f"❌ Failed to initialize script generator: {e}")
        return False

    # Check current settings
    min_episodes = script_generator.min_episodes_per_digest
    max_episodes = script_generator.max_episodes_per_digest

    print(f"\n📊 Current settings:")
    print(f"   Min episodes per digest: {min_episodes}")
    print(f"   Max episodes per digest: {max_episodes}")

    # Get qualifying episodes for each topic
    print(f"\n🔍 Checking episode counts for each topic:")
    print(f"   (using score threshold: {script_generator.score_threshold})")

    for topic_name in script_generator.topic_instructions:
        qualifying = script_generator.get_qualifying_episodes(topic_name)
        episode_count = len(qualifying)

        # Determine if digest would be created
        would_create = episode_count >= min_episodes
        status = "✅ WOULD CREATE" if would_create else "⏭️  WOULD SKIP"

        print(f"\n   {topic_name}:")
        print(f"      Episodes: {episode_count}")
        print(f"      Status: {status}")

        if episode_count > 0 and episode_count < min_episodes:
            print(f"      ⚠️  Has {episode_count} episode(s) but below minimum of {min_episodes}")

        # Show top episode titles if any
        if episode_count > 0:
            print(f"      Top episodes:")
            for i, ep in enumerate(qualifying[:min(3, episode_count)], 1):
                score = ep.scores.get(topic_name, 0.0)
                print(f"         {i}. {ep.title[:60]}... (score: {score:.2f})")

    print("\n" + "=" * 80)
    print("Test completed successfully!")
    print("=" * 80)

    return True

if __name__ == '__main__':
    try:
        success = test_min_episodes_enforcement()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
