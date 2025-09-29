from __future__ import annotations

from datetime import datetime, date, UTC
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
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

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
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_episodes_status_published", "status", "published_date"),
        Index("ix_episodes_scored", "scored_at"),
    )


class Digest(Base):
    __tablename__ = "digests"

    id = Column(Integer, primary_key=True)
    topic = Column(String(256), nullable=False)
    digest_date = Column(Date, nullable=False)
    digest_timestamp = Column(DateTime(timezone=False), nullable=False, default=lambda: datetime.now(UTC))
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
    generated_at = Column(DateTime(timezone=False), default=lambda: datetime.now(UTC))

    __table_args__ = (
        UniqueConstraint("topic", "digest_date", "digest_timestamp", name="uq_digests_topic_date_timestamp"),
        Index("ix_digests_date", "digest_date"),
        Index("ix_digests_timestamp", "digest_timestamp"),
    )


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
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

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
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
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
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

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
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_pipeline_runs_started", "started_at"),
        Index("ix_pipeline_runs_workflow", "workflow_run_id"),
    )
