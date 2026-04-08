#!/usr/bin/env python3
"""
End-to-end test for StoryArcExtractor (post-claude-p migration, v3.31).

Picks a recent scored episode, calls extract_and_store_story_arcs() against
it, and reports what arcs/events were created or updated. Does NOT require
the full pipeline to run.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))
from src.utils.phase_bootstrap import bootstrap_phase
bootstrap_phase()

from src.database.models import get_database_manager, get_episode_repo
from src.database.sqlalchemy_models import Episode as EpisodeModel
from src.topic_tracking.topic_extractor import StoryArcExtractor


def main(episode_id: int = None):
    db = get_database_manager()
    with db.get_session() as session:
        if episode_id is None:
            ep = (
                session.query(EpisodeModel)
                .filter(
                    EpisodeModel.status == 'scored',
                    EpisodeModel.transcript_content.isnot(None),
                )
                .order_by(EpisodeModel.scored_at.desc())
                .first()
            )
        else:
            ep = session.query(EpisodeModel).filter(EpisodeModel.id == episode_id).first()

        if not ep:
            print("ERROR: no episode found")
            return 1

        # Pull all data we need before closing session
        ep_id = ep.id
        ep_guid = ep.episode_guid
        ep_feed = ep.feed_id
        ep_title = ep.title
        ep_published = ep.published_date
        ep_transcript = ep.transcript_content
        ep_scores = ep.scores or {}

    print(f"Test episode: {ep_id} '{ep_title[:60]}'")
    print(f"  feed_id={ep_feed}")
    print(f"  transcript: {len(ep_transcript or '')} chars")
    print(f"  scores: {ep_scores}")
    print()

    # Pick the topic with the highest score
    if not ep_scores:
        print("ERROR: episode has no scores")
        return 1
    digest_topic = max(ep_scores.items(), key=lambda kv: kv[1])[0]
    relevance = ep_scores[digest_topic]
    print(f"Using digest_topic='{digest_topic}' (score={relevance})")
    print()

    extractor = StoryArcExtractor()
    print("Calling extract_and_store_story_arcs() — this hits claude -p...")
    print()

    try:
        results = extractor.extract_and_store_story_arcs(
            episode_id=ep_id,
            episode_guid=ep_guid,
            feed_id=ep_feed,
            digest_topic=digest_topic,
            transcript=ep_transcript,
            episode_title=ep_title,
            episode_published_date=ep_published,
            relevance_score=relevance,
        )
    except Exception as e:
        print(f"FAILED with exception: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1

    print(f"Returned {len(results)} arc result(s):")
    for r in results:
        marker = '[NEW]' if r.get('is_new') else '[CONTINUING]'
        print(f"  {marker} {r.get('arc_name', '?')}")
        print(f"    summary: {r.get('event_summary', '')[:120]}")
        if 'arc_id' in r:
            print(f"    arc_id={r['arc_id']}")
        if 'event_id' in r:
            print(f"    event_id={r['event_id']}")
    return 0


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--episode-id", type=int, default=None)
    args = p.parse_args()
    sys.exit(main(args.episode_id))
