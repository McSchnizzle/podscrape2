# Story Arcs: How They Work

This document explains the story arc tracking system, how it integrates with digest generation, and how repetition detection prevents stale content.

## Overview

Story arcs track **evolving news narratives** across podcast episodes. Instead of treating each episode as isolated content, the system identifies ongoing stories (like "OpenAI's GPT-5 Development" or "EU AI Act Implementation") and tracks how they develop over time.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         EXTRACTION PHASE                            │
│                        (run_audio.py)                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Episode Transcript                                                 │
│         │                                                           │
│         ▼                                                           │
│  ┌─────────────────┐                                                │
│  │ StoryArcExtractor│  Uses GPT to identify story arcs and events  │
│  │ (topic_extractor)│                                               │
│  └────────┬────────┘                                                │
│           │                                                         │
│           ▼                                                         │
│  ┌─────────────────┐     ┌─────────────────┐                        │
│  │   story_arcs    │────▶│ story_arc_events│                        │
│  │     table       │     │     table       │                        │
│  └─────────────────┘     └─────────────────┘                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                         DIGEST PHASE                                │
│                       (run_digest.py)                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. GET STORY ARC CONTEXT                                           │
│     ┌─────────────────────────────────────────┐                     │
│     │ _get_recent_story_arc_context(topic)    │                     │
│     │   - Gets active arcs (last 14 days)     │                     │
│     │   - Formats for GPT prompt context      │                     │
│     └─────────────────────────────────────────┘                     │
│                                                                     │
│  2. CHECK FOR REPETITION                                            │
│     ┌─────────────────────────────────────────┐                     │
│     │ _check_topic_repetition(episodes, topic)│                     │
│     │   - Compare active vs recently included │                     │
│     │   - If >50% overlap → add update framing│                     │
│     └─────────────────────────────────────────┘                     │
│                                                                     │
│  3. GENERATE SCRIPT                                                 │
│     ┌─────────────────────────────────────────┐                     │
│     │ generate_script(...)                    │                     │
│     │   - Story arc context in prompt         │                     │
│     │   - Repetition avoidance if needed      │                     │
│     └─────────────────────────────────────────┘                     │
│                                                                     │
│  4. MARK COVERED ARCS                                               │
│     ┌─────────────────────────────────────────┐                     │
│     │ mark_covered_story_arcs(digest_id, ...) │                     │
│     │   - Scans script for arc name mentions  │                     │
│     │   - Sets included_in_digest_id          │                     │
│     │   - Sets included_at timestamp          │                     │
│     └─────────────────────────────────────────┘                     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Database Schema

### story_arcs table
| Column | Type | Description |
|--------|------|-------------|
| id | int | Primary key |
| arc_name | text | Human-readable story name |
| arc_slug | text | Normalized slug for matching |
| functional_category | text | model_release, company_strategy, etc. |
| digest_topic | text | Parent topic (e.g., "AI and Technology") |
| event_count | int | Number of events in timeline |
| source_count | int | Number of unique source feeds |
| included_in_digest_id | int | FK to digests table (NULL if not included) |
| included_at | timestamp | When arc was included in digest |
| last_updated_at | timestamp | Last event added |

### story_arc_events table
| Column | Type | Description |
|--------|------|-------------|
| id | int | Primary key |
| story_arc_id | int | FK to story_arcs |
| event_date | timestamp | When event occurred |
| event_summary | text | 1-2 sentence summary |
| key_points | text[] | Array of specific details |
| source_name | text | Episode/feed title |
| perspective | text | positive, negative, neutral, analytical |

## Repetition Detection Flow

The system prevents digests from repeating the same content day after day:

```
Day 1 Digest:
├── Check recently covered arcs → None found
├── Generate full digest covering Arc A, Arc B, Arc C
├── mark_covered_story_arcs() → Marks A, B, C with today's timestamp
└── Done

Day 2 Digest:
├── Check recently covered arcs → Finds A, B, C from Day 1
├── Calculate overlap: 3/4 active arcs = 75% > 50% threshold
├── Add "CONTINUING COVERAGE" instructions to prompt:
│   - Focus ONLY on NEW developments
│   - Don't repeat benchmark data or statistics
│   - Frame as "latest developments" or "since we last covered..."
├── Generate digest with update framing
├── Mark any newly covered arcs
└── Done
```

## Key Methods

### StoryArcRepository (src/database/story_arc_repo.py)

```python
# Get arcs active in the last N days
get_active_story_arcs(topic, days=14) -> List[Dict]

# Get arcs included in digests within lookback window
get_recently_included_arcs(topic, days=3) -> List[Dict]

# Get arcs ready for digest generation
get_story_arcs_for_digest(topic, min_events=2, exclude_included=True) -> List[Dict]

# Mark an arc as included in a digest
mark_story_arc_included(story_arc_id, digest_id) -> None
```

### ScriptGenerator (src/generation/script_generator.py)

```python
# Get story arc context for GPT prompt
_get_recent_story_arc_context(topic, days_back=14) -> str

# Check for overlap with recent coverage
_check_topic_repetition(episodes, topic) -> Tuple[bool, str, List[str]]
# Returns: (has_overlap, message, recently_covered_arc_names)

# Build repetition avoidance instructions
_build_repetition_avoidance_instructions(recently_covered_arcs) -> str

# Mark arcs mentioned in script as included
mark_covered_story_arcs(digest_id, topic, script_content) -> int
```

## Functional Categories

Story arcs are classified into these categories:

| Category | Description | Example |
|----------|-------------|---------|
| model_release | New model announcements, updates | "GPT-5 Development Timeline" |
| company_strategy | Business moves, pivots, leadership | "OpenAI Restructuring" |
| research | Papers, studies, breakthroughs | "Scaling Laws Research" |
| regulation | Policy, legal, governance | "EU AI Act Implementation" |
| product_launch | New products, features, services | "Claude 3 Launch" |
| partnership | Collaborations, acquisitions | "Microsoft-OpenAI Partnership" |
| controversy | Disputes, criticisms, debates | "AI Safety Debates" |
| industry_trend | Broader patterns, market shifts | "AI Agent Adoption" |
| technique | New methods, approaches | "Chain-of-Thought Prompting" |
| use_case | Applications, implementations | "AI in Healthcare" |

## Configuration

Settings via web_settings table:

| Key | Default | Description |
|-----|---------|-------------|
| topic_tracking.retention_days | 14 | How far back to look for active arcs |
| topic_evolution.similarity_threshold | 0.85 | Semantic matching threshold |
| topic_evolution.embedding_model | text-embedding-3-small | Model for embeddings |

## Repetition Avoidance Prompt

When >50% overlap is detected, this is injected into the prompt:

```
## CONTINUING COVERAGE - FOCUS ON NEW DEVELOPMENTS ONLY

The following story arcs were covered in recent digests (last 3 days):
  - AI Agents as Force Multipliers
  - Knowledge Work Redefinition
  - 2026 as Critical Deadline

**CRITICAL INSTRUCTIONS FOR AVOIDING REPETITION:**
1. DO NOT repeat benchmark data, statistics, or specific numbers
2. DO NOT re-explain background context that listeners already know
3. Focus ONLY on what is NEW or has CHANGED since last coverage
4. Frame coverage as "latest developments" or "continuing our coverage of..."
5. If an arc has no new developments, briefly acknowledge and move on
6. Prioritize fresh insights over rehashing known information
7. Assume listeners are already familiar with the basics

Example framing:
- "Building on what we discussed recently about [topic]..."
- "There's a new development in the [story] we've been following..."
- "The latest update on [topic] shows..."
```

## Web UI

Navigate to `/story-arcs` to view and manage story arcs with expandable timelines.

## Version History

- v2.29: Initial story arc tracking system
- v2.64: Integrated story arcs into digest generation (replaced episode_topics)
- v2.66: Full repetition detection with update framing
- v2.67: Added mark_covered_story_arcs call after digest creation
