# Smart Story Arc Merge & Condense

Intelligent review, deduplication, merging, and condensing of story arcs. Uses claude -p for analysis.

## Steps

### 1. Fetch all arcs with their events

```bash
source .venv/bin/activate && python3 -c "
from src.database.story_arc_repo import get_story_arc_repo
import json

repo = get_story_arc_repo()
arcs = repo.get_all_story_arcs(limit=500)
topics = {}
for arc in arcs:
    topic = arc['digest_topic']
    if topic not in topics:
        topics[topic] = []

    # Get events for large arcs
    full_arc = repo.get_story_arc_by_id(arc['id'])
    events_preview = []
    if full_arc and 'events' in full_arc:
        for e in full_arc['events'][:5]:
            events_preview.append(e.get('event_summary', '')[:120])

    topics[topic].append({
        'id': arc['id'],
        'name': arc['arc_name'],
        'slug': arc['arc_slug'],
        'category': arc['functional_category'],
        'events': arc['event_count'],
        'sources': arc['source_count'],
        'summary': arc.get('summary', ''),
        'is_hot': arc.get('is_hot', False),
        'saturation': arc.get('saturation_score', 0),
        'recent_events': events_preview
    })

for topic, topic_arcs in topics.items():
    print(f'\n=== {topic} ({len(topic_arcs)} arcs) ===')
    for a in sorted(topic_arcs, key=lambda x: -x['events']):
        hot = ' 🔥HOT' if a['is_hot'] else ''
        sat = f' sat={a[\"saturation\"]:.1f}' if a['saturation'] > 0 else ''
        print(f'  [{a[\"id\"]}] {a[\"name\"]} ({a[\"events\"]} events, {a[\"sources\"]} sources, {a[\"category\"]}){hot}{sat}')
        if a['summary']:
            print(f'       Summary: {a[\"summary\"][:100]}')
        for ev in a['recent_events'][:2]:
            print(f'       Event: {ev}')
"
```

### 2. Analyze and identify merge candidates

Review the arcs above. When deciding what to merge, follow these rules:

**DO merge** arcs that:
- Reference the exact same story/development from different angles
- Are clearly a subset of a broader arc (e.g., "GPT-5 release" into "OpenAI GPT-5 family")
- Have overlapping event summaries about the same topic

**DO NOT merge** arcs that:
- Are about the same company/entity but different stories (e.g., "OpenAI fundraising" vs "OpenAI safety concerns" — keep separate)
- Are both hot — unless they are clearly duplicates
- Cover different aspects even if related (e.g., "AI regulation" vs "AI in healthcare regulation")

**Size consideration**: If merging would create an arc with 30+ events, the post-merge condensing step is critical. Consider whether merging actually helps or just creates noise.

### 3. Execute merges

For each merge group, pick the primary (most events, best name) and merge:

```bash
source .venv/bin/activate && python3 -c "
from src.database.story_arc_repo import get_story_arc_repo
repo = get_story_arc_repo()
result = repo.merge_arcs(primary_arc_id=PRIMARY_ID, duplicate_arc_ids=[DUP_ID_1, DUP_ID_2])
print(f'Merged: {result}')
"
```

### 4. Condense large arcs post-merge

After merging, any arc with 15+ events should be condensed. Use claude -p to analyze the full event timeline and produce a condensed summary.

```bash
source .venv/bin/activate && python3 << 'PYEOF'
import os, subprocess, json
from src.database.story_arc_repo import get_story_arc_repo
from src.database.models import get_database_manager
from src.database.sqlalchemy_models import StoryArc

ARC_ID = REPLACE_WITH_ARC_ID  # Arc to condense

repo = get_story_arc_repo()
arc = repo.get_story_arc_by_id(ARC_ID)
if not arc:
    print(f"Arc {ARC_ID} not found"); exit(1)

events = arc.get('events', [])
print(f"Arc: {arc['arc_name']} ({len(events)} events)")

# Build event timeline for claude -p
timeline = []
for e in sorted(events, key=lambda x: str(x.get('event_date', ''))):
    timeline.append(f"[{str(e.get('event_date',''))[:10]}] {e.get('event_summary','')} (source: {e.get('source_name','unknown')})")

prompt = f"""You are an editorial analyst. Below is the event timeline for a story arc called "{arc['arc_name']}" (category: {arc['functional_category']}).

TIMELINE ({len(events)} events):
{chr(10).join(timeline)}

CURRENT SUMMARY: {arc.get('summary', 'None')}

TASKS:
1. Write a concise SUMMARY (2-3 sentences) that captures the current state and trajectory of this story
2. Identify any REDUNDANT events (events that say essentially the same thing from different sources) — list their dates
3. If this arc has a hot_briefing, suggest an updated briefing that incorporates all events

Return your response as:
SUMMARY: [your summary]
REDUNDANT: [list of redundant event dates, or "none"]
BRIEFING: [updated briefing if applicable, or "n/a"]"""

# Call claude -p with subscription
claude_path = os.path.expanduser("~/.local/bin/claude")
if not os.path.exists(claude_path):
    claude_path = "claude"
env = os.environ.copy()
env.pop("CLAUDECODE", None)
env.pop("ANTHROPIC_API_KEY", None)

result = subprocess.run(
    [claude_path, "-p", "--model", "sonnet", "--effort", "medium",
     "--tools", "", "--no-session-persistence", "-"],
    input=prompt, capture_output=True, text=True, timeout=120, env=env,
)
if result.returncode != 0:
    print(f"claude -p failed: {result.stderr[:300]}")
    exit(1)

print(f"\n--- Claude Analysis ---")
print(result.stdout)

# Optionally update the summary in the database
response = result.stdout
if "SUMMARY:" in response:
    summary_line = response.split("SUMMARY:")[1].split("\n")[0].strip()
    if summary_line and len(summary_line) > 20:
        db = get_database_manager()
        with db.get_session() as session:
            sa = session.query(StoryArc).filter(StoryArc.id == ARC_ID).first()
            if sa:
                sa.summary = summary_line
                session.commit()
                print(f"\nUpdated arc summary in database.")
PYEOF
```

### 5. Report results

Summarize: which arcs were merged, which were condensed, current arc counts by topic.

## Notes
- Run every 3 days to keep arcs clean
- Err on the side of NOT merging — false merges lose data
- After condensing, review the updated summary before moving on
- The condense step uses claude -p with --effort medium (subscription, not API billing)
- Orphan arcs (0 events, >3 days old) are automatically cleaned up by the retention system
