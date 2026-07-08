"""
SQLAlchemy ORM Models for PostgreSQL (Supabase).

These models define the database schema for the RSS Podcast Transcript Digest System.
They are the authoritative source for the Python backend and must align with:
  - Canonical schema: supabase_schema.sql
  - TypeScript types: web_ui_hosted/utils/supabase.ts

Schema changes should be made via Alembic migrations: python3 -m alembic upgrade head

GitHub Issue #9: Consolidate data access on Supabase
"""

from __future__ import annotations

from datetime import datetime, date, timezone
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    DateTime,
    Date,
    Boolean,
    Text,
    Float,
    Index,
    UniqueConstraint,
    ForeignKey,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import JSON

# JSON column that uses JSONB on PostgreSQL and plain JSON on SQLite.
# This lets the same models work against both Supabase (production) and
# in-memory SQLite (tests) without dialect-specific CompileError.
JsonB = JSON().with_variant(JSONB(), "postgresql")

# ARRAY column that uses PostgreSQL native ARRAY on Postgres and JSON on
# SQLite.  On SQLite the column stores a JSON-encoded list, which is fine
# for test fixtures.
from sqlalchemy.types import TypeDecorator

class TextArray(TypeDecorator):
    """Portable TEXT[] — native ARRAY on Postgres, JSON on other dialects."""
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.ARRAY(Text))
        return dialect.type_descriptor(JSON())
from sqlalchemy.orm import DeclarativeBase, relationship

from src.database.episode_status import EpisodeStatus, VALID_EPISODE_STATUSES


class Base(DeclarativeBase):
    pass


class Feed(Base):
    __tablename__ = "feeds"

    id = Column(Integer, primary_key=True)
    feed_url = Column(String(2048), nullable=False, unique=True)
    feed_type = Column(String(50), nullable=False, default='rss')  # 'rss' or 'youtube'
    title = Column(String(512), nullable=False)
    description = Column(Text)
    active = Column(Boolean, nullable=False, default=True)
    priority = Column(Integer, nullable=False, default=100)  # Lower = higher priority
    consecutive_failures = Column(Integer, nullable=False, default=0)
    last_checked = Column(DateTime(timezone=False))
    last_episode_date = Column(DateTime(timezone=False))
    total_episodes_processed = Column(Integer, nullable=False, default=0)
    total_episodes_failed = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_feeds_active", "active"),
        Index("ix_feeds_priority", "priority"),
    )


class Episode(Base):
    __tablename__ = "episodes"

    id = Column(Integer, primary_key=True)
    episode_guid = Column(String(1024), nullable=False, unique=True)
    feed_id = Column(Integer, nullable=False)
    title = Column(String(1024), nullable=False)
    published_date = Column(DateTime(timezone=False), nullable=False)
    audio_url = Column(String(4096), nullable=False)
    duration_seconds = Column(Integer)
    description = Column(Text)
    audio_path = Column(String(4096))
    audio_downloaded_at = Column(DateTime(timezone=False))
    transcript_path = Column(String(4096))
    transcript_content = Column(Text)
    transcript_generated_at = Column(DateTime(timezone=False))
    transcript_word_count = Column(Integer)
    chunk_count = Column(Integer, nullable=False, default=0)
    scores = Column(JSON)  # { topic: float } - database-agnostic JSON
    scored_at = Column(DateTime(timezone=False))
    status = Column(String(64), nullable=False, default="pending")
    failure_count = Column(Integer, nullable=False, default=0)
    failure_reason = Column(Text)
    last_failure_at = Column(DateTime(timezone=False))
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_episodes_status_published", "status", "published_date"),
        Index("ix_episodes_scored", "scored_at"),
    )

    # State validation methods (Phase 6)
    def validate_state(self) -> tuple[bool, list[str]]:
        """
        Validate episode state consistency.

        Returns:
            tuple: (is_valid, list_of_errors)
        """
        errors = []

        # Valid states - use canonical enum
        if self.status not in VALID_EPISODE_STATUSES:
            errors.append(f"Invalid status: {self.status}. Valid: {VALID_EPISODE_STATUSES}")

        # Required fields per state
        if self.status == "pending":
            if not self.title:
                errors.append("pending state requires title")
            if not self.audio_url:
                errors.append("pending state requires audio_url")

        elif self.status == "processing":
            # Processing can have partial state - just check basics
            pass

        elif self.status == "transcribed":
            if not self.transcript_content:
                errors.append("transcribed state requires transcript_content")
            if not self.transcript_generated_at:
                errors.append("transcribed state requires transcript_generated_at")

        elif self.status == "scored":
            if not self.scores:
                errors.append("scored state requires scores")
            if not self.scored_at:
                errors.append("scored state requires scored_at")

        elif self.status == "digested":
            if not self.scores:
                errors.append("digested state requires scores")
            if not self.scored_at:
                errors.append("digested state requires scored_at")

        elif self.status == "failed":
            if self.failure_count == 0:
                errors.append("failed state requires failure_count > 0")

        elif self.status == "not_relevant":
            # Not relevant episodes should have been scored
            if not self.scores:
                errors.append("not_relevant state requires scores")
            if not self.scored_at:
                errors.append("not_relevant state requires scored_at")

        # Check state transition validity
        if self.status == "scored" and not self.transcript_content:
            errors.append("scored state requires episode to be transcribed first")

        return (len(errors) == 0, errors)


class Digest(Base):
    __tablename__ = "digests"

    id = Column(Integer, primary_key=True)
    topic = Column(String(256), nullable=False)
    digest_date = Column(Date, nullable=False)
    digest_timestamp = Column(DateTime(timezone=False), nullable=False, default=lambda: datetime.now(timezone.utc))
    script_path = Column(String(4096))
    script_content = Column(Text)
    script_content_predupe = Column(Text)  # Pre-dedupe draft for audit/rollback
    script_word_count = Column(Integer)
    mp3_path = Column(String(4096))
    mp3_duration_seconds = Column(Integer)
    mp3_title = Column(String(1024))
    mp3_summary = Column(Text)
    # Issue #10/#29: episode_ids column removed. Use digest_episode_links table.
    episode_count = Column(Integer, nullable=False, default=0)
    average_score = Column(Integer)
    github_url = Column(String(4096))
    published_at = Column(DateTime(timezone=False))
    generated_at = Column(DateTime(timezone=False), default=lambda: datetime.now(timezone.utc))
    status = Column(String(50), default='draft')  # draft, generated, audio_generated, published
    is_favorite = Column(Boolean, nullable=False, default=False, server_default='false')

    __table_args__ = (
        UniqueConstraint("topic", "digest_date", "digest_timestamp", name="uq_digests_topic_date_timestamp"),
        Index("ix_digests_date", "digest_date"),
        Index("ix_digests_timestamp", "digest_timestamp"),
    )

    # State validation methods (Phase 6)
    def validate_state(self) -> tuple[bool, list[str]]:
        """
        Validate digest state consistency.

        Returns:
            tuple: (is_valid, list_of_errors)
        """
        errors = []

        # Required fields check
        if not self.topic:
            errors.append("digest requires topic")
        if not self.digest_date:
            errors.append("digest requires digest_date")

        # Script generation state
        if self.script_content and not self.script_word_count:
            errors.append("digest with script_content should have script_word_count")

        # TTS generation state
        if self.mp3_path and not self.mp3_duration_seconds:
            errors.append("digest with mp3_path should have mp3_duration_seconds")
        if self.mp3_path and not self.mp3_title:
            errors.append("digest with mp3_path should have mp3_title")
        if self.mp3_path and not self.mp3_summary:
            errors.append("digest with mp3_summary should have mp3_summary")

        # Publishing state
        if self.github_url and not self.mp3_path:
            errors.append("digest with github_url should have mp3_path")
        if self.published_at and not self.github_url:
            errors.append("digest with published_at should have github_url")

        # Issue #10/#29: episode_ids column removed. Use digest_episode_links table.

        return (len(errors) == 0, errors)

    def is_ready_for_tts(self) -> tuple[bool, list[str]]:
        """Check if digest is ready for TTS generation."""
        errors = []

        if not self.script_content:
            errors.append("missing script_content")
        if self.episode_count == 0:
            errors.append("no episodes (episode_count = 0)")

        return (len(errors) == 0, errors)

    def is_ready_for_publishing(self) -> tuple[bool, list[str]]:
        """Check if digest is ready for publishing to GitHub."""
        errors = []

        if not self.mp3_path:
            errors.append("missing mp3_path")
        if not self.mp3_title:
            errors.append("missing mp3_title")
        if not self.mp3_summary:
            errors.append("missing mp3_summary")

        # Check MP3 file exists
        from pathlib import Path
        if self.mp3_path and not Path(self.mp3_path).exists():
            errors.append(f"mp3_path points to non-existent file: {self.mp3_path}")

        return (len(errors) == 0, errors)


class Topic(Base):
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True)
    slug = Column(String(255), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    voice_id = Column(String(255))
    voice_settings = Column(JsonB)
    instructions_md = Column(Text)
    is_active = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)
    last_generated_at = Column(DateTime(timezone=False))
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Multi-voice dialogue support (v1.79)
    use_dialogue_api = Column(Boolean, nullable=False, default=False)
    dialogue_model = Column(String(50), nullable=False, default='eleven_turbo_v2_5')
    voice_config = Column(JsonB)  # {"speaker_1": {"name": "...", "voice_id": "..."}, "speaker_2": {...}}

    # Topic tracking support (v1.100)
    enable_topic_tracking = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("ix_topics_active", "is_active"),
        Index("ix_topics_sort", "sort_order"),
    )


class TopicInstructionVersion(Base):
    __tablename__ = "topic_instruction_versions"

    id = Column(Integer, primary_key=True)
    topic_id = Column(Integer, nullable=False)
    version = Column(Integer, nullable=False)
    instructions_md = Column(Text, nullable=False)
    change_note = Column(Text)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    created_by = Column(String(255))

    __table_args__ = (
        UniqueConstraint("topic_id", "version", name="uq_topic_instruction_version"),
        Index("ix_topic_instruction_topic", "topic_id"),
    )


class DigestEpisodeLink(Base):
    __tablename__ = "digest_episode_links"

    id = Column(Integer, primary_key=True)
    digest_id = Column(Integer, nullable=False)
    episode_id = Column(Integer, nullable=False)
    topic = Column(String(256))
    score = Column(Float)
    position = Column(Integer)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_digest_episode_digest", "digest_id"),
        Index("ix_digest_episode_episode", "episode_id"),
        UniqueConstraint("digest_id", "episode_id", name="uq_digest_episode"),
    )


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id = Column(String(64), primary_key=True)
    workflow_run_id = Column(BigInteger)
    workflow_name = Column(String(255))
    trigger = Column(String(128))
    status = Column(String(64))
    conclusion = Column(String(64))
    started_at = Column(DateTime(timezone=False))
    finished_at = Column(DateTime(timezone=False))
    phase = Column(JsonB)
    notes = Column(Text)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_pipeline_runs_started", "started_at"),
        Index("ix_pipeline_runs_workflow", "workflow_run_id"),
    )


class PipelineLog(Base):
    __tablename__ = "pipeline_logs"

    id = Column(Integer, primary_key=True)
    run_id = Column(String(128), nullable=False)
    phase = Column(String(64), nullable=False)
    timestamp = Column(DateTime(timezone=False), nullable=False, default=lambda: datetime.now(timezone.utc))
    level = Column(String(16), nullable=False)
    logger_name = Column(String(256), nullable=False)
    module = Column(String(256))
    function = Column(String(256))
    line = Column(Integer)
    message = Column(Text, nullable=False)
    extra = Column(JSON)

    __table_args__ = (
        Index("ix_pipeline_logs_run_phase_time", "run_id", "phase", "timestamp"),
        Index("ix_pipeline_logs_level", "level"),
    )


class EpisodeTopic(Base):
    """Tracks extracted topics from episode transcripts for deduplication"""
    __tablename__ = "episode_topics"

    id = Column(Integer, primary_key=True)
    episode_id = Column(Integer, nullable=False)
    topic_name = Column(String(512), nullable=False)
    topic_slug = Column(String(255), nullable=False)
    key_points = Column(TextArray(), nullable=False)  # Array of key insight strings
    first_mentioned_at = Column(DateTime(timezone=False), nullable=False)
    last_mentioned_at = Column(DateTime(timezone=False), nullable=False)
    mention_count = Column(Integer, nullable=False, default=1)
    digest_topic = Column(String(256), nullable=False)  # Parent topic (e.g., "AI and Technology")
    relevance_score = Column(Float)
    included_in_digest_id = Column(Integer)  # NULL until included in a digest
    included_at = Column(DateTime(timezone=False))

    # Topic evolution and type classification (v2.01+)
    topic_type = Column(String(50), nullable=False, default='other')  # model_release, use_case, personality, etc.
    novelty_score = Column(Float, nullable=False, default=1.0)  # 0.0-1.0, how novel is this info
    is_update = Column(Boolean, nullable=False, default=False)  # Is this an update to existing topic?
    parent_topic_id = Column(Integer, ForeignKey('episode_topics.id', ondelete='SET NULL'), nullable=True)
    evolution_summary = Column(Text, nullable=True)  # What changed since parent topic
    first_seen_at = Column(DateTime(timezone=True), nullable=True)  # When this topic slug first appeared

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    parent_topic = relationship('EpisodeTopic', remote_side=[id], backref='updates', foreign_keys=[parent_topic_id])

    __table_args__ = (
        UniqueConstraint('episode_id', 'topic_slug', name='uq_episode_topics_episode_slug'),
        Index('ix_episode_topics_episode', 'episode_id'),
        Index('ix_episode_topics_slug', 'topic_slug'),
        Index('ix_episode_topics_digest_topic', 'digest_topic'),
        Index('ix_episode_topics_included', 'included_in_digest_id'),
        Index('ix_episode_topics_mentioned', 'last_mentioned_at'),
    )


class CommonAd(Base):
    """Tracks frequently appearing advertisement content for filtering"""
    __tablename__ = "common_ads"

    id = Column(Integer, primary_key=True)
    advertiser_name = Column(String(256), nullable=False, unique=True)
    pattern_keywords = Column(JsonB, nullable=False)  # Array of keyword strings
    confidence_threshold = Column(Float, nullable=False, default=0.8)
    is_active = Column(Boolean, nullable=False, default=True)
    first_detected_at = Column(DateTime(timezone=False), nullable=False, default=lambda: datetime.now(timezone.utc))
    last_detected_at = Column(DateTime(timezone=False), nullable=False, default=lambda: datetime.now(timezone.utc))
    detection_count = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('ix_common_ads_active', 'is_active'),
        Index('ix_common_ads_advertiser', 'advertiser_name'),
    )


class WorkflowError(Base):
    """Persistent error tracking for workflow pattern analysis"""
    __tablename__ = "workflow_errors"

    id = Column(Integer, primary_key=True)
    error_date = Column(Date, nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    run_id = Column(String(128), nullable=False)
    workflow_run_id = Column(BigInteger)
    error_category = Column(String(64), nullable=False)
    phase = Column(String(64), nullable=False)
    severity = Column(String(16), nullable=False, default='error')
    feed_id = Column(Integer)
    feed_url = Column(String(2048))
    error_code = Column(String(32))
    error_message = Column(Text, nullable=False)
    error_summary = Column(String(512))
    extra = Column(JsonB)
    source_log_id = Column(Integer)
    resolved = Column(Boolean, nullable=False, default=False)
    resolved_at = Column(DateTime(timezone=True))
    resolution_notes = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_workflow_errors_date", "error_date"),
        Index("ix_workflow_errors_run_id", "run_id"),
        Index("ix_workflow_errors_category", "error_category"),
        Index("ix_workflow_errors_phase", "phase"),
        Index("ix_workflow_errors_feed_id", "feed_id"),
    )


class StoryArc(Base):
    """Tracks evolving news narratives over time"""
    __tablename__ = "story_arcs"

    id = Column(Integer, primary_key=True)
    arc_name = Column(String(512), nullable=False)
    arc_slug = Column(String(255), nullable=False, unique=True)
    functional_category = Column(String(50), nullable=False, default='other')
    digest_topic = Column(String(256), nullable=False)
    summary = Column(Text)
    started_at = Column(DateTime(timezone=True), nullable=False)
    last_updated_at = Column(DateTime(timezone=True), nullable=False)
    event_count = Column(Integer, nullable=False, default=1)
    source_count = Column(Integer, nullable=False, default=1)
    included_in_digest_id = Column(Integer)
    included_at = Column(DateTime(timezone=True))
    saturation_score = Column(Float, nullable=False, default=0.0)
    is_hot = Column(Boolean, nullable=False, default=False)
    hot_briefing = Column(Text)
    retain_until = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    events = relationship('StoryArcEvent', back_populates='story_arc', cascade='all, delete-orphan')

    __table_args__ = (
        Index('ix_story_arcs_digest_topic', 'digest_topic'),
        Index('ix_story_arcs_category', 'functional_category'),
        Index('ix_story_arcs_last_updated', 'last_updated_at'),
        Index('ix_story_arcs_slug', 'arc_slug'),
    )


class StoryArcEvent(Base):
    """Individual events within a story arc timeline"""
    __tablename__ = "story_arc_events"

    id = Column(Integer, primary_key=True)
    story_arc_id = Column(Integer, ForeignKey('story_arcs.id', ondelete='CASCADE'), nullable=False)
    event_date = Column(DateTime(timezone=True), nullable=False)
    event_summary = Column(Text, nullable=False)
    key_points = Column(TextArray(), nullable=False, default=[])
    source_feed_id = Column(Integer, ForeignKey('feeds.id', ondelete='SET NULL'))
    source_episode_id = Column(Integer, ForeignKey('episodes.id', ondelete='SET NULL'))
    source_episode_guid = Column(String(512))
    source_name = Column(String(256))
    perspective = Column(String(50))  # positive, negative, neutral, analytical
    relevance_score = Column(Float)
    extracted_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    story_arc = relationship('StoryArc', back_populates='events')

    __table_args__ = (
        Index('ix_story_arc_events_arc_id', 'story_arc_id'),
        Index('ix_story_arc_events_date', 'event_date'),
        Index('ix_story_arc_events_episode', 'source_episode_id'),
    )


class StoryArcCoverage(Base):
    """Junction table tracking which digests covered which story arcs (many-to-many)"""
    __tablename__ = "story_arc_coverage"

    id = Column(Integer, primary_key=True)
    story_arc_id = Column(Integer, ForeignKey('story_arcs.id', ondelete='CASCADE'), nullable=False)
    digest_id = Column(Integer, ForeignKey('digests.id', ondelete='CASCADE'), nullable=False)
    covered_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('ix_story_arc_coverage_arc_id', 'story_arc_id'),
        Index('ix_story_arc_coverage_digest_id', 'digest_id'),
        Index('ix_story_arc_coverage_covered_at', 'covered_at'),
    )


class WatchTheme(Base):
    """User-curated natural-language theme for personal weekly digest."""
    __tablename__ = "watch_themes"

    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    active = Column(Boolean, nullable=False, default=True, server_default='true')
    sort_order = Column(Integer, nullable=False, default=100, server_default='100')
    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('ix_watch_themes_active', 'active'),
        Index('ix_watch_themes_sort_order', 'sort_order'),
    )


class WatchDigestRun(Base):
    """Audit record of each weekly watch-digest generation run."""
    __tablename__ = "watch_digest_runs"

    id = Column(Integer, primary_key=True)
    run_date = Column(Date, nullable=False, unique=True)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    themes_scanned = Column(Integer, nullable=False)
    episodes_scanned = Column(Integer, nullable=False)
    html_content = Column(Text, nullable=True)
    markdown_content = Column(Text, nullable=True)
    email_delivered = Column(Boolean, nullable=False, default=False,
                             server_default='false')
    harold_delivered = Column(Boolean, nullable=False, default=False,
                              server_default='false')
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))
