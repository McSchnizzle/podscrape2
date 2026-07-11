"""Shared constants for the Harold R&D applicability signal (kanban #2855).

`ContentScorer` asks the same claude -p call that scores topic relevance to
also rate how applicable an episode is to Harold's own R&D pipeline (agent
orchestration, memory systems, TTS/STT, e-ink/reMarkable integrations, local
models, MCP/tool protocols, workflow automation, self-improvement loops).
That score is persisted under a RESERVED key inside `episodes.scores` --
the same JSON column real topic scores live in.

Every consumer that iterates `episode.scores` (digest topic selection,
podcast-relevance gating, retention, dashboard display, ops scripts) MUST
either look up a specific topic name by exact key (safe by construction --
`_harold_rnd` can never equal a real topic name) or explicitly skip
underscore-prefixed keys when doing blind iteration (`.values()`, `.items()`,
`max(...)`). See `tests/test_harold_rnd_reserved_key.py` for the contract
this file exists to protect.
"""

# Reserved key inside episodes.scores JSON. Leading underscore guarantees it
# can never collide with a real topic name (topic names come from the
# `topics` DB table / config/topics.json and are never underscore-prefixed).
HAROLD_RND_SCORE_KEY = "_harold_rnd"

# Episodes with _harold_rnd >= this threshold are candidates for the weekly
# R&D miner (scripts/rnd_miner.py) and are exempted from the retention
# manager's age-based transcript/episode deletion.
HAROLD_RND_RETENTION_THRESHOLD_DEFAULT = 0.7


def is_reserved_score_key(key: str) -> bool:
    """True if `key` is a reserved (non-topic) key inside episodes.scores."""
    return isinstance(key, str) and key.startswith("_")
