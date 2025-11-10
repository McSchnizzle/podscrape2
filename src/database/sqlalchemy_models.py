from __future__ import annotations

from datetime import datetime, date, timezone
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Date,
    Boolean,
    Text,
    Float,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import JSON
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Feed(Base):
    __tablename__ = "feeds"

    id = Column(Integer, primary_key=True)
    feed_url = Column(String(2048), nullable=False, unique=True)
    title = Column(String(512), nullable=False)
    description = Column(Text)
    active = Column(Boolean, nullable=False, default=True)
    consecutive_failures = Column(Integer, nullable=False, default=0)
    last_checked = Column(DateTime(timezone=False))
    last_episode_date = Column(DateTime(timezone=False))
    total_episodes_processed = Column(Integer, nullable=False, default=0)
    total_episodes_failed = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_feeds_active", "active"),
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

        # Valid states
        valid_states = ["pending", "processing", "transcribed", "scored", "digested", "failed"]
        if self.status not in valid_states:
            errors.append(f"Invalid status: {self.status}")

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
    script_word_count = Column(Integer)
    mp3_path = Column(String(4096))
    mp3_duration_seconds = Column(Integer)
    mp3_title = Column(String(1024))
    mp3_summary = Column(Text)
    episode_ids = Column(JSON)  # [int] - database-agnostic JSON
    episode_count = Column(Integer, nullable=False, default=0)
    average_score = Column(Integer)
    github_url = Column(String(4096))
    published_at = Column(DateTime(timezone=False))
    generated_at = Column(DateTime(timezone=False), default=lambda: datetime.now(timezone.utc))
    status = Column(String(50), default='draft')  # draft, generated, audio_generated, published

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

        # Episode linkage
        if self.episode_count > 0 and not self.episode_ids:
            errors.append("digest with episode_count > 0 should have episode_ids")
        if self.episode_ids and self.episode_count != len(self.episode_ids):
            errors.append(f"episode_count ({self.episode_count}) doesn't match episode_ids length ({len(self.episode_ids)})")

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
    voice_settings = Column(JSONB)
    instructions_md = Column(Text)
    is_active = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)
    last_generated_at = Column(DateTime(timezone=False))
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Multi-voice dialogue support (v1.79)
    use_dialogue_api = Column(Boolean, nullable=False, default=False)
    dialogue_model = Column(String(50), nullable=False, default='eleven_turbo_v2_5')
    voice_config = Column(JSONB)  # {"speaker_1": {"name": "...", "voice_id": "..."}, "speaker_2": {...}}

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
    workflow_run_id = Column(Integer)
    workflow_name = Column(String(255))
    trigger = Column(String(128))
    status = Column(String(64))
    conclusion = Column(String(64))
    started_at = Column(DateTime(timezone=False))
    finished_at = Column(DateTime(timezone=False))
    phase = Column(JSONB)
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
