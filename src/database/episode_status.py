"""
Canonical Episode Status Enum - Single Source of Truth

This module defines the valid episode status values and state transitions.
All status-related logic should reference this module.

GitHub Issue #21: Align episode status enum across DB, validators, and UI
"""

from enum import Enum
from typing import Set


class EpisodeStatus(str, Enum):
    """
    Valid episode status values for the pipeline.

    State Machine:

    pending --> processing --> transcribed --> scored --> digested
                    |              |            |
                    v              v            v
                  failed        failed      not_relevant
                    ^              ^            ^
                    |______________|____________|

    Terminal states: digested, not_relevant, failed
    """

    # Initial state after RSS discovery
    PENDING = "pending"

    # Transient state during audio download/transcription
    # Reset back to pending if stuck > 10 minutes
    PROCESSING = "processing"

    # Successfully transcribed, awaiting scoring
    TRANSCRIBED = "transcribed"

    # Scored and qualifies for at least one topic
    SCORED = "scored"

    # Scored but doesn't qualify for any topic (terminal)
    NOT_RELEVANT = "not_relevant"

    # Included in a generated digest script (terminal)
    DIGESTED = "digested"

    # Processing failed after max retries (terminal)
    FAILED = "failed"

    @classmethod
    def valid_values(cls) -> Set[str]:
        """Return set of valid status string values"""
        return {status.value for status in cls}

    @classmethod
    def terminal_states(cls) -> Set['EpisodeStatus']:
        """States that represent end of processing"""
        return {cls.DIGESTED, cls.NOT_RELEVANT, cls.FAILED}

    @classmethod
    def active_states(cls) -> Set['EpisodeStatus']:
        """States that may still need processing"""
        return {cls.PENDING, cls.PROCESSING, cls.TRANSCRIBED, cls.SCORED}

    @classmethod
    def can_transition(cls, from_status: 'EpisodeStatus', to_status: 'EpisodeStatus') -> bool:
        """
        Validate if a status transition is allowed.

        Returns True if transition is valid, False otherwise.
        """
        valid_transitions = {
            cls.PENDING: {cls.PROCESSING, cls.FAILED},
            cls.PROCESSING: {cls.TRANSCRIBED, cls.PENDING, cls.FAILED},  # PENDING for reset
            cls.TRANSCRIBED: {cls.SCORED, cls.NOT_RELEVANT, cls.FAILED},
            cls.SCORED: {cls.DIGESTED, cls.NOT_RELEVANT, cls.FAILED},
            # Terminal states - no transitions out (except admin reset)
            cls.DIGESTED: set(),
            cls.NOT_RELEVANT: set(),
            cls.FAILED: {cls.PENDING},  # Allow retry from failed
        }
        return to_status in valid_transitions.get(from_status, set())


# For backwards compatibility with string comparisons
VALID_EPISODE_STATUSES = EpisodeStatus.valid_values()
