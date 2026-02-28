# Story Arc Deduplication and Merge

Review all active story arcs, identify duplicates/near-duplicates, and merge them.

## Steps

1. **Fetch all story arcs from the database**:
```bash
source .venv/bin/activate && python3 -c "
from src.database.story_arc_repo import get_story_arc_repo
import json

repo = get_story_arc_repo()
arcs = repo.get_all_story_arcs(limit=500)
# Group by digest_topic
topics = {}
for arc in arcs:
    topic = arc['digest_topic']
    if topic not in topics:
        topics[topic] = []
    topics[topic].append({
        'id': arc['id'],
        'name': arc['arc_name'],
        'slug': arc['arc_slug'],
        'category': arc['functional_category'],
        'events': arc['event_count'],
        'sources': arc['source_count'],
        'summary': arc.get('summary', ''),
        'is_hot': arc.get('is_hot', False)
    })

for topic, topic_arcs in topics.items():
    print(f'\n=== {topic} ({len(topic_arcs)} arcs) ===')
    for a in sorted(topic_arcs, key=lambda x: -x['events']):
        hot = ' HOT' if a['is_hot'] else ''
        print(f\"  [{a['id']}] {a['name']} ({a['events']} events, {a['sources']} sources, {a['category']}){hot}\")
"
```

2. **Review the output above.** For each digest_topic group, identify arcs that are clearly about the same story (duplicates or near-duplicates). Consider:
   - Arc names that reference the same entity, event, or development
   - Arcs with overlapping summaries or similar slugs
   - Arcs that would naturally be covered together in a digest
   - NEVER merge hot arcs unless they are clear duplicates of each other

3. **For each group of duplicates**, determine the primary arc (the one with the most events) and merge:
```bash
source .venv/bin/activate && python3 -c "
from src.database.story_arc_repo import get_story_arc_repo
repo = get_story_arc_repo()

# Example: merge arcs 45 and 67 into primary arc 23
result = repo.merge_arcs(primary_arc_id=PRIMARY_ID, duplicate_arc_ids=[DUP_ID_1, DUP_ID_2])
print(f'Merged: {result}')
"
```

4. **Report results**: Summarize what was merged, how many events were consolidated, and any arcs that were borderline (for human review).

## Notes
- Run this periodically (every 3 days) to keep the arc list clean
- Err on the side of NOT merging if uncertain -- false merges lose data
- Hot arcs (is_hot=True) should only be merged with other hot arcs about the exact same story
- After merging, the primary arc inherits all events, coverage records, and recalculated stats
