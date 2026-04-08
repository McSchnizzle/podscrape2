#!/usr/bin/env python3
"""
End-to-end test of ScriptGenerator.create_digest() — exercises the EXACT
path that crashed last night with the script_content_predupe TypeError.

Picks today's topic + scored episodes, runs create_digest(), and reports
whether a digest was actually created in the database.

DOES NOT run TTS / publishing.
"""
import sys
from pathlib import Path
from datetime import date, timedelta

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))
from src.utils.phase_bootstrap import bootstrap_phase
bootstrap_phase()

from src.database.models import get_database_manager
from src.database.sqlalchemy_models import Digest as DigestModel
from src.generation.script_generator import ScriptGenerator
from src.config.web_config import WebConfigManager


def main():
    target_date = date.today()
    topic = "AI and Technology"

    print(f"Test: create_digest('{topic}', {target_date})")
    print()

    # Initialize ScriptGenerator the same way run_digest.py does
    web_config = WebConfigManager()
    try:
        from src.config.config_manager import ConfigManager
        sg = ScriptGenerator(
            web_config=web_config,
            config_manager=ConfigManager(web_config=web_config),
        )
    except Exception:
        sg = ScriptGenerator(web_config=web_config)

    # Count digests for today before
    db = get_database_manager()
    with db.get_session() as session:
        before = (
            session.query(DigestModel)
            .filter(DigestModel.topic == topic)
            .filter(DigestModel.digest_date == target_date)
            .count()
        )
        print(f"Existing digests for {topic} on {target_date}: {before}")
    print()

    print("Calling create_digest()...")
    try:
        digest = sg.create_digest(topic, target_date)
    except Exception as e:
        print(f"CRASHED with {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1

    if digest is None:
        print("create_digest returned None — no qualifying episodes? Or skipped?")
        return 0

    print(f"✓ Digest created: id={digest.id}")
    print(f"  topic: {digest.topic}")
    print(f"  date: {digest.digest_date}")
    print(f"  script_content: {len(digest.script_content or '')} chars")
    print(f"  script_content_predupe: {len(digest.script_content_predupe or '')} chars")
    print(f"  word_count: {digest.script_word_count}")
    print(f"  episode_count: {digest.episode_count}")
    print(f"  avg_score: {digest.average_score:.2f}" if digest.average_score else "")

    # Verify it's in the DB
    with db.get_session() as session:
        after = (
            session.query(DigestModel)
            .filter(DigestModel.topic == topic)
            .filter(DigestModel.digest_date == target_date)
            .count()
        )
        print(f"\nDigests for {topic} on {target_date} after: {after} (was {before})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
