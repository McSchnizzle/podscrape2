from __future__ import annotations

from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Date,
    Boolean,
    Text,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
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
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

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
    transcript_generated_at = Column(DateTime(timezone=False))
    transcript_word_count = Column(Integer)
    chunk_count = Column(Integer, nullable=False, default=0)
    scores = Column(JSONB)  # { topic: float }
    scored_at = Column(DateTime(timezone=False))
    status = Column(String(64), nullable=False, default="pending")
    failure_count = Column(Integer, nullable=False, default=0)
    failure_reason = Column(Text)
    last_failure_at = Column(DateTime(timezone=False))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_episodes_status_published", "status", "published_date"),
        Index("ix_episodes_scored", "scored_at"),
    )


class Digest(Base):
    __tablename__ = "digests"

    id = Column(Integer, primary_key=True)
    topic = Column(String(256), nullable=False)
    digest_date = Column(Date, nullable=False)
    script_path = Column(String(4096))
    script_word_count = Column(Integer)
    mp3_path = Column(String(4096))
    mp3_duration_seconds = Column(Integer)
    mp3_title = Column(String(1024))
    mp3_summary = Column(Text)
    episode_ids = Column(JSONB)  # [int]
    episode_count = Column(Integer, nullable=False, default=0)
    average_score = Column(Integer)
    github_url = Column(String(4096))
    published_at = Column(DateTime(timezone=False))
    generated_at = Column(DateTime(timezone=False), default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("topic", "digest_date", name="uq_digests_topic_date"),
        Index("ix_digests_date", "digest_date"),
    )

