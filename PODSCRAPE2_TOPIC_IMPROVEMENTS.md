# Topic Extraction and Deduplication Improvements

## Overview

This document describes improvements made to the topic extraction system in the AInewsletter project that should be replicated in podscrape2. The system solves two core problems:

1. **Preventing duplicate topics** when semantically similar topics are extracted with slightly different names (e.g., "GPT-5 Release" vs "Upcoming GPT-5 Release" vs "GPT-5.2 Announcement")
2. **Tracking story arcs** - recognizing that related topics over time form an evolving narrative, not separate events

## Problem Statement

The original topic extraction system had fundamental flaws:

1. **Extraction** creates new topics based on GPT's output with only exact slug matching
2. **Novelty detection** only compares topics with identical slugs
3. **No story awareness** - topics about the same ongoing story (e.g., GPT-5.2 rumors → date shifts → actual release) were treated as unrelated events
4. Result: Semantically identical topics get created as duplicates, and evolving stories fragment into disconnected pieces

Example of the problem:
- Episode 1 extracts topic: "GPT-5.2 Release Rumors" (slug: `gpt-52-release-rumors`)
- Episode 2 extracts topic: "GPT-5.2 Release Date Shifted" (slug: `gpt-52-release-date-shifted`)
- Episode 3 extracts topic: "GPT-5.2 Release" (slug: `gpt-52-release`)
- Episode 4 extracts topic: "GPT-5.2 Benchmark Performance" (slug: `gpt-52-benchmark-performance`)

These are all part of the same **story arc** - the GPT-5.2 release - but get stored as separate entries. Users want to see the evolution of this story, not four disconnected topics.

## Solution Architecture

The solution has three components:

### 1. Story Arc Recognition

**Story arcs** are predefined patterns that identify topics belonging to the same evolving narrative. Instead of treating "GPT-5.2 Release Rumors" and "GPT-5.2 Release" as separate topics, the system recognizes they're part of the same story.

Key implementation in `TopicExtractor`:

```python
# Story arc patterns - keywords that indicate topics belong to the same story
STORY_ARC_PATTERNS = {
    "gemini-3": ["gemini 3", "gemini-3", "gemini3"],
    "gpt-5-release": ["gpt-5", "gpt 5", "gpt5", "gpt-5.2", "gpt 5.2"],
    "openai-strategy": ["openai code red", "openai's focus", "openai's shift", "openai financial"],
    "ai-trust": ["ai trust", "trust in ai", "ai perception", "edelman", "ai sentiment"],
    "google-glasses": ["google glass", "smart glasses", "project aura", "android xr"],
    "cybersecurity-ciso": ["ciso", "cybersecurity", "zero trust", "cyber risk"],
    "ai-benchmarks": ["benchmark", "gdpval", "ai grading", "model performance"],
    "ai-education": ["ai education", "workforce development", "micro-credential", "educational"],
    "social-media-regulation": ["tiktok", "social media ban", "first amendment", "fcc", "media regulation"],
    "streaming-wars": ["netflix", "streaming", "warner bros", "disney acquisition"],
}

def _identify_story_arc(self, topic_name: str, key_points: List[str] = None) -> Optional[str]:
    """Identify which story arc a topic belongs to based on keywords."""
    text_to_check = topic_name.lower()
    if key_points:
        text_to_check += " " + " ".join(key_points).lower()

    for arc_id, patterns in STORY_ARC_PATTERNS.items():
        for pattern in patterns:
            if pattern in text_to_check:
                return arc_id
    return None
```

**GPT Prompt Enhancement for Story Arcs:**
```
ACTIVE STORY ARCS:
The following stories are currently being tracked. If this transcript discusses any of these,
you should EXTEND the existing story rather than create a new topic:

Story: GPT-5.2 Release
Current topic: "GPT-5.2 Release"
Key points so far:
- Initial rumors suggested late Q4 2024 release
- Release date shifted to mid-December
- GPT-5.2 officially released on December 10th, 2024
- Initial benchmarks show 15% improvement over GPT-5

When extending a story arc:
- Use the existing topic name exactly
- Add NEW developments as key points
- Mark is_update=true
```

### 2. Prevention: Semantic Matching During Extraction

**Before creating a new topic**, check if a semantically similar topic already exists using embedding similarity.

Key changes to `TopicExtractor`:

```python
# 1. Initialize semantic matcher
self.semantic_matcher = SemanticTopicMatcher(similarity_threshold=0.85)

# 2. In extract_and_store_topics():
# a) Fetch existing topics (30 days lookback)
existing_topics = self.db.get_recent_episode_topics(digest_topic=digest_topic, days=30)

# b) Include existing topic names in GPT prompt
existing_topic_names = self.semantic_matcher.get_topic_names_for_prompt(existing_topics)

# c) Before creating each topic, check for semantic match
matched_topic = self.semantic_matcher.find_matching_topic(
    new_topic_name=topic_name,
    new_key_points=key_points,
    existing_topics=existing_topics,
    digest_topic=digest_topic
)

if matched_topic:
    # Use existing topic's slug and name
    # Only add NEW key points not already present
    # Set is_update=True and link parent_topic_id
else:
    # Create as new topic
```

**GPT Prompt Enhancement:**
```
IMPORTANT - Existing Topics to Reuse:
The following topics already exist in our database. If any topic in this transcript
matches one of these (even if phrased differently), USE THE EXISTING TOPIC NAME:
- GPT-5 Release
- OpenAI Leadership Crisis
- Claude 3.5 Sonnet Launch
...

When you find content about an existing topic:
- Use the EXACT existing topic name (don't create a variation)
- Mark is_update=true
- Add only NEW key points not covered before
```

### 3. Cleanup: Two-Phase Daily Deduplication Script

> **Note for podscrape2**: The AInewsletter project runs this dedupe script daily at 7 AM via cron on the **shared Supabase database**. Since podscrape2 operates on the same `episode_topics` table, you do NOT need to implement or run your own deduplication. However, understanding how it works will help you write better topic extraction code that minimizes duplicates in the first place.

Even with prevention, some duplicates and fragmented story arcs may slip through. A daily dedupe process consolidates them using a **two-phase approach**:

```bash
python scripts/dedupe_topics.py [--dry-run] [--digest-topic NAME] [--verbose]
```

**Phase 1: Story Arc Consolidation**

Uses keyword-based `STORY_ARC_PATTERNS` to group related topics:
1. Identifies all topics belonging to each story arc
2. Keeps the canonical topic (oldest by first_mentioned_at)
3. Merges unique key points from all story arc topics (max 6 points)
4. Deletes duplicate story arc topics

**Phase 2: Semantic Duplicate Detection**

For topics not in story arcs, uses embedding similarity:
1. Computes embeddings for remaining topics
2. Uses union-find algorithm to group similar topics (≥0.80 similarity)
3. Merges duplicates into canonical topic
4. Deletes duplicate records

Example output:
```
PHASE 1: Story Arc Consolidation
Story Arc 'gpt-5-release': Consolidating 4 topics into 'GPT-5.2 Release'
  - Merging 'GPT-5.2 Release Rumors' (id=4)
  - Merging 'GPT-5.2 Release Date Shifted' (id=26)
  - Merging 'GPT-5.2 Benchmark Performance' (id=66)
  Result: 'GPT-5.2 Release' now has 6 key points

PHASE 2: Semantic Duplicate Detection
Found 2 groups of semantic duplicates
Group 1: 'AI Coding Assistants' has 1 duplicates
  Merging 'Code Generation Tools' into 'AI Coding Assistants'
```

## New Files to Create

### `src/topic_tracking/semantic_matcher.py`

```python
class SemanticTopicMatcher:
    """
    Finds semantically similar topics using embedding similarity.
    Uses text-embedding-3-small for cost-effective comparisons.
    """

    def __init__(self, similarity_threshold: float = 0.85):
        # 0.85 = 85% similar means same topic

    def find_matching_topic(
        self,
        new_topic_name: str,
        new_key_points: List[str],
        existing_topics: List[Dict],
        digest_topic: str = None
    ) -> Optional[TopicMatch]:
        """
        Find best matching existing topic for a new topic.
        Returns TopicMatch if similarity >= threshold, None otherwise.
        """

    def find_duplicate_groups(
        self,
        topics: List[Dict],
        similarity_threshold: float = None
    ) -> List[List[Dict]]:
        """
        Find groups of duplicate topics using union-find.
        Returns list of groups, each sorted by age (oldest first).
        """

    def get_topic_names_for_prompt(
        self,
        existing_topics: List[Dict],
        max_topics: int = 50
    ) -> str:
        """
        Generate formatted list of existing topic names for GPT prompt.
        Dedupes by slug and returns most recent unique names.
        """
```

Key implementation details:
- Uses `text-embedding-3-small` model (fast, cheap)
- Creates text representation: `topic_name + " " + " ".join(key_points)`
- Cosine similarity for comparison
- Caches embeddings to reduce API calls
- Union-find algorithm for grouping duplicates

### `scripts/dedupe_topics.py`

Daily cleanup script that:
1. Gets topics with `enable_topic_tracking=true`
2. For each digest_topic:
   - Fetches recent topics (configurable, default 30 days)
   - Finds duplicate groups using embedding similarity
   - Merges duplicates into canonical (oldest)
   - Deletes duplicate records
3. Logs comprehensive statistics

## Database Methods to Add

```python
def delete_episode_topic(self, topic_id: int) -> bool:
    """Delete an episode topic by ID."""

def update_episode_topic_key_points(self, topic_id: int, key_points: List[str]) -> None:
    """Update key points for an episode topic."""
```

## Configuration

The semantic matching and story arc tracking use these thresholds:

| Setting | Value | Purpose |
|---------|-------|---------|
| `similarity_threshold` | 0.80 | Consider topics as duplicates if 80%+ similar |
| `lookback_days` | 30 | Check against topics from last 30 days |
| `max_key_points` | 6 | Maximum key points after merging |
| `STORY_ARC_PATTERNS` | dict | Keyword patterns that identify story arcs |

The models used are configured in `web_settings`:

| Setting | Default | Purpose |
|---------|---------|---------|
| `topic_tracking.extraction_model` | `gpt-5.2-chat-latest` | Model for topic extraction |
| `topic_evolution.embedding_model` | `text-embedding-3-small` | Model for semantic similarity |
| `ai_content_scoring.model` | `gpt-5.2-chat-latest` | Model for content scoring |

## Key Behavior Changes

### Before
- GPT extracts topics with whatever names it chooses
- New topics created unless exact slug match exists
- Duplicate topics accumulate over time
- Evolving stories fragment into disconnected topics
- No awareness of ongoing narratives

### After
- **Story arc awareness**: GPT receives context about active stories and extends them
- GPT receives list of existing topic names and is instructed to reuse them
- New topics checked against existing via embedding similarity
- Matching topics add new key points instead of creating duplicates
- Daily dedupe consolidates story arcs first, then semantic duplicates
- Topics tell evolving stories with key points showing the narrative progression
- Stories consolidate information over time instead of fragmenting

## Implementation Checklist for podscrape2

### Required (topic extraction improvements)

1. [x] Create `src/topic_tracking/semantic_matcher.py` with `SemanticTopicMatcher` class
2. [x] Add `STORY_ARC_PATTERNS` dictionary to `TopicExtractor`
3. [x] Update `TopicExtractor.__init__()`:
   - [x] Initialize `SemanticTopicMatcher`
   - [x] Load model from `web_settings` (`topic_tracking.extraction_model`)
4. [x] Update `TopicExtractor.extract_and_store_topics()`:
   - [x] Fetch existing topics (30 days)
   - [x] Generate existing topic names for prompt
   - [x] Generate active story arcs for prompt
   - [x] Check if topic belongs to a story arc first
   - [x] If in story arc: extend the canonical topic with new key points
   - [x] If not in arc: check semantic match
   - [x] If semantic match found: use existing name/slug, merge key points, set is_update=True
   - [x] If no match: create as new topic (existing behavior)
5. [x] Update `TopicExtractor._create_extraction_prompt()`:
   - [x] Accept `existing_topic_names` parameter
   - [x] Accept `active_story_arcs` parameter
   - [x] Include existing topics section in prompt
   - [x] Include active story arcs section in prompt
   - [x] Emphasize extending stories rather than creating new topics
6. [x] Add database methods:
   - [x] `delete_episode_topic(topic_id)`
   - [x] `update_episode_topic_key_points(topic_id, key_points)`

### NOT Required (handled by AInewsletter)

7. [x] ~~Create `scripts/dedupe_topics.py`~~ - **Runs daily on shared database**
8. [x] ~~Add to daily cron~~ - **Already scheduled at 7 AM**

## Testing

To verify the implementation:

```bash
# Dry run to see what would be deduplicated
python scripts/dedupe_topics.py --dry-run --verbose

# Test on single digest topic
python scripts/dedupe_topics.py --dry-run --digest-topic "AI and Technology"

# Run actual deduplication
python scripts/dedupe_topics.py --verbose
```

## Expected Outcomes

1. **Story arc tracking**: Ongoing stories like "GPT-5.2 Release" are tracked as single evolving narratives
2. **Key points tell the story**: Key points show progression: rumors → date shifts → release → benchmarks
3. **Fewer duplicate topics**: Topics like "GPT-5 Release" and "GPT-5.2 Announcement" get consolidated
4. **Richer key points**: Information from multiple episodes gets merged into canonical topics
5. **Better tracking**: Evolution of topics over time becomes clearer
6. **Cleaner digests**: Newsletter generation has less redundancy to filter

## Example: Story Arc in Action

**Before (fragmented topics):**
- Topic: "GPT-5.2 Release Rumors" - 2 key points
- Topic: "GPT-5.2 Release Date Shifted" - 2 key points
- Topic: "GPT-5.2 Release" - 3 key points
- Topic: "GPT-5.2 Benchmark Performance" - 2 key points

**After (consolidated story arc):**
- Topic: "GPT-5.2 Release" - 6 key points:
  1. Initial rumors suggested late Q4 2024 release
  2. Release date shifted to mid-December due to safety testing
  3. GPT-5.2 officially released on December 10th, 2024
  4. Initial benchmarks show 15% improvement over GPT-5 on reasoning tasks
  5. Enterprise pricing announced at $0.03/1K tokens
  6. Multimodal capabilities expanded to include video understanding

## Questions to Resolve

1. ~~Should similarity_threshold be configurable in web_settings?~~ - Currently hardcoded at 0.80
2. Should we add a "merged_from" audit trail when consolidating?
3. Do we need to update any digest generation logic to handle the new structure?
4. How should new story arcs be added? Currently requires code changes to `STORY_ARC_PATTERNS`

---

*Generated from AInewsletter implementation on 2025-12-13*
