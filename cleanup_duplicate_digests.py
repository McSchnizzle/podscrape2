#!/usr/bin/env python3
"""
Cleanup script to remove duplicate digests (same topic, same date)
Keeps only the newest digest per topic per day (highest ID).
"""

import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# Bootstrap phase initialization
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from src.database.models import get_digest_repo, get_database_manager
from src.database.sqlalchemy_models import Digest as DigestModel

def main():
    """Clean up duplicate digests"""
    print("🧹 Duplicate Digest Cleanup Script")
    print("=" * 50)

    # Get all digests pending TTS
    digest_repo = get_digest_repo()
    pending_digests = digest_repo.get_digests_pending_tts()

    print(f"Found {len(pending_digests)} digests pending TTS")

    # Group by topic and date
    duplicates_by_topic_date = defaultdict(list)
    for digest in pending_digests:
        key = (digest.topic, digest.digest_date)
        duplicates_by_topic_date[key].append(digest)

    # Find duplicates (groups with more than one digest)
    duplicates_found = 0
    digests_to_delete = []
    digests_to_keep = []

    for (topic, date), digests in duplicates_by_topic_date.items():
        if len(digests) > 1:
            duplicates_found += 1
            # Sort by ID descending (newest first)
            digests.sort(key=lambda x: x.id, reverse=True)
            newest = digests[0]
            older = digests[1:]

            digests_to_keep.append(newest)
            digests_to_delete.extend(older)

            print(f"\n📝 {topic} on {date}:")
            print(f"   ✅ Keep: ID {newest.id} (newest)")
            for old in older:
                print(f"   🗑️  Delete: ID {old.id} (older)")
        else:
            # No duplicates for this topic/date
            digests_to_keep.append(digests[0])

    print(f"\n📊 Summary:")
    print(f"   Topics with duplicates: {duplicates_found}")
    print(f"   Digests to keep: {len(digests_to_keep)}")
    print(f"   Digests to delete: {len(digests_to_delete)}")

    if len(digests_to_delete) == 0:
        print("✅ No duplicates found - database is clean!")
        return

    # Auto-confirm deletion (for automation)
    print(f"\n✅ Proceeding to delete {len(digests_to_delete)} duplicate digests...")

    # Delete duplicates
    db_manager = get_database_manager()
    deleted_count = 0

    with db_manager.get_session() as session:
        try:
            for digest in digests_to_delete:
                digest_model = session.query(DigestModel).filter(DigestModel.id == digest.id).first()
                if digest_model:
                    session.delete(digest_model)
                    deleted_count += 1

            session.commit()
            print(f"✅ Successfully deleted {deleted_count} duplicate digests")

            # Show final summary
            remaining_pending = digest_repo.get_digests_pending_tts()
            remaining_by_topic = defaultdict(int)
            for digest in remaining_pending:
                remaining_by_topic[digest.topic] += 1

            print(f"\n📈 After cleanup:")
            print(f"   Total pending digests: {len(remaining_pending)}")
            for topic, count in remaining_by_topic.items():
                print(f"   {topic}: {count} digest(s)")

        except Exception as e:
            session.rollback()
            print(f"❌ Error during cleanup: {e}")
            return

    print("\n🎉 Cleanup completed successfully!")
    print("TTS phase will now process only the newest digest per topic.")

if __name__ == "__main__":
    main()