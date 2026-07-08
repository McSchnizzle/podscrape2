"""
SQLAlchemy-based database models and repositories for RSS Podcast Transcript Digest System.

DATABASE ARCHITECTURE (v2.30+):
-------------------------------
This module provides the Python data access layer for PostgreSQL (Supabase).

The system uses a SINGLE database (Supabase PostgreSQL) with TWO access patterns:
  - Python (this module): SQLAlchemy ORM for backend pipeline, scripts, migrations
  - TypeScript (web_ui_hosted/utils/supabase.ts): Supabase JS SDK for Web UI API routes

Both stacks connect to the SAME Supabase PostgreSQL database.

CANONICAL SCHEMA: supabase_schema.sql
SCHEMA MANAGEMENT: Alembic migrations (alembic/versions/)

DEPRECATED: SQLite is no longer supported. The legacy SQLite schema has been
archived to archive/legacy_schemas/schema_sqlite_legacy.sql.

GitHub Issue #9: Consolidate data access on Supabase
"""

import json
import logging
from datetime import datetime, date, timedelta, timezone
from typing import Optional, List, Dict, Any, Union, TypeVar, Type
from dataclasses import dataclass

from sqlalchemy import create_engine, text, func
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError, ProgrammingError

from .sqlalchemy_models import (
    Base,
    Feed as FeedModel,
    Episode as EpisodeModel,
    Digest as DigestModel,
    Topic as TopicModel,
    TopicInstructionVersion as TopicInstructionModel,
    DigestEpisodeLink as DigestEpisodeLinkModel,
    PipelineRun as PipelineRunModel,
    PipelineLog as PipelineLogModel,
    WorkflowError as WorkflowErrorModel,
)
from src.config.env import require_database_url
from src.config.web_config import SettingsKeys, DEFAULTS

# Note: Valid statuses defined in src.database.episode_status.EpisodeStatus
# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class Feed:
    """RSS Podcast Feed model - dataclass for API compatibility"""
    feed_url: str
    title: str
    description: Optional[str] = None
    active: bool = True
    consecutive_failures: int = 0
    last_checked: Optional[datetime] = None
    last_episode_date: Optional[datetime] = None
    total_episodes_processed: int = 0
    total_episodes_failed: int = 0
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class Episode:
    """RSS Podcast Episode model - dataclass for API compatibility"""
    episode_guid: str
    feed_id: int
    title: str
    published_date: datetime
    audio_url: str
    duration_seconds: Optional[int] = None
    description: Optional[str] = None
    audio_path: Optional[str] = None
    audio_downloaded_at: Optional[datetime] = None
    transcript_path: Optional[str] = None
    transcript_content: Optional[str] = None
    transcript_generated_at: Optional[datetime] = None
    transcript_word_count: Optional[int] = None
    chunk_count: int = 0
    scores: Optional[Dict[str, float]] = None
    scored_at: Optional[datetime] = None
    status: str = 'pending'  # See episode_status.py: pending, processing, transcribed, scored, not_relevant, digested, failed
    failure_count: int = 0
    failure_reason: Optional[str] = None
    last_failure_at: Optional[datetime] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class Digest:
    """Topic-based digest model - dataclass for API compatibility"""
    topic: str
    digest_date: date
    digest_timestamp: Optional[datetime] = None
    script_path: Optional[str] = None
    script_content: Optional[str] = None
    script_content_predupe: Optional[str] = None  # v3.26: pre-dedupe draft for audit
    script_word_count: Optional[int] = None
    mp3_path: Optional[str] = None
    mp3_duration_seconds: Optional[int] = None
    mp3_title: Optional[str] = None
    mp3_summary: Optional[str] = None
    # Issue #10/#29: episode_ids field removed. Use digest_episode_links table.
    episode_count: int = 0
    average_score: Optional[float] = None
    github_url: Optional[str] = None
    published_at: Optional[datetime] = None
    id: Optional[int] = None
    generated_at: Optional[datetime] = None
    status: Optional[str] = 'draft'  # draft, generated, audio_generated, published


@dataclass
class Topic:
    slug: str
    name: str
    description: Optional[str] = None
    voice_id: Optional[str] = None
    voice_settings: Optional[Dict[str, Any]] = None
    instructions_md: Optional[str] = None
    is_active: bool = True
    sort_order: int = 0
    last_generated_at: Optional[datetime] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Multi-voice dialogue support (v1.79+)
    use_dialogue_api: bool = False
    dialogue_model: str = 'eleven_turbo_v2_5'
    voice_config: Optional[Dict[str, Any]] = None
    # Topic tracking and deduplication (v2.00+)
    enable_topic_tracking: bool = False


@dataclass
class TopicInstructionVersion:
    topic_id: int
    version: int
    instructions_md: str
    change_note: Optional[str] = None
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None
    id: Optional[int] = None


@dataclass
class DigestEpisodeLink:
    digest_id: int
    episode_id: int
    topic: Optional[str] = None
    score: Optional[float] = None
    position: Optional[int] = None
    created_at: Optional[datetime] = None
    id: Optional[int] = None


@dataclass
class PipelineRun:
    id: str
    workflow_run_id: Optional[int] = None
    workflow_name: Optional[str] = None
    trigger: Optional[str] = None
    status: Optional[str] = None
    conclusion: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    phase: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class PipelineLog:
    run_id: str
    phase: str
    timestamp: datetime
    level: str
    logger_name: str
    module: Optional[str] = None
    function: Optional[str] = None
    line: Optional[int] = None
    message: str = ""
    extra: Optional[Dict[str, Any]] = None
    id: Optional[int] = None


@dataclass
class WorkflowError:
    """Persistent error record for workflow pattern analysis"""
    error_date: date
    occurred_at: datetime
    run_id: str
    error_category: str
    phase: str
    error_message: str
    workflow_run_id: Optional[int] = None
    severity: str = 'error'
    feed_id: Optional[int] = None
    feed_url: Optional[str] = None
    error_code: Optional[str] = None
    error_summary: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None
    source_log_id: Optional[int] = None
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DatabaseManager:
    """
    SQLAlchemy-based database manager for PostgreSQL.
    Provides session management, connection pooling, and transaction support.
    """

    def __init__(self, database_url: str = None):
        self.database_url = database_url or require_database_url()

        # Get pool settings from DEFAULTS (avoids circular import with WebConfigManager)
        pool_size = DEFAULTS.get(
            (SettingsKeys.Database.CATEGORY, SettingsKeys.Database.POOL_SIZE),
            {"default": 5}
        )["default"]
        max_overflow = DEFAULTS.get(
            (SettingsKeys.Database.CATEGORY, SettingsKeys.Database.MAX_OVERFLOW),
            {"default": 10}
        )["default"]
        pool_recycle = DEFAULTS.get(
            (SettingsKeys.Database.CATEGORY, SettingsKeys.Database.POOL_RECYCLE_SECONDS),
            {"default": 3600}
        )["default"]

        # SQLite (used in tests) does not support pool_size / max_overflow
        is_sqlite = self.database_url.startswith("sqlite://")
        is_memory_sqlite = is_sqlite and ":memory:" in self.database_url

        engine_kwargs: dict = {
            "pool_pre_ping": not is_sqlite,
            "pool_recycle": pool_recycle,
            "echo": False,  # Set to True for SQL debugging
        }
        if is_memory_sqlite:
            # In-memory SQLite requires a single connection pool so data survives
            # across sessions within the same DatabaseManager (used by tests).
            engine_kwargs["connect_args"] = {"check_same_thread": False}
            engine_kwargs["poolclass"] = StaticPool
        elif not is_sqlite:
            engine_kwargs["pool_size"] = pool_size
            engine_kwargs["max_overflow"] = max_overflow

        self.engine = create_engine(self.database_url, **engine_kwargs)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        # Logging removed to prevent circular dependency with DatabaseLogHandler
        # logger.info(f"Database manager initialized with PostgreSQL")

    def get_session(self) -> Session:
        """Get a new database session"""
        return self.SessionLocal()

    def test_connection(self) -> bool:
        """Test database connectivity"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False


class FeedRepository:
    """Repository for Feed database operations using SQLAlchemy"""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def create(self, feed: Feed) -> int:
        """Create new feed and return ID"""
        with self.db.get_session() as session:
            try:
                feed_model = FeedModel(
                    feed_url=feed.feed_url,
                    title=feed.title,
                    description=feed.description,
                    active=feed.active,
                    consecutive_failures=feed.consecutive_failures,
                    last_checked=feed.last_checked,
                    last_episode_date=feed.last_episode_date,
                    total_episodes_processed=feed.total_episodes_processed,
                    total_episodes_failed=feed.total_episodes_failed
                )
                session.add(feed_model)
                session.commit()
                session.refresh(feed_model)
                return feed_model.id
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to create feed: {e}")
                raise

    def get_by_url(self, feed_url: str) -> Optional[Feed]:
        """Get feed by URL"""
        with self.db.get_session() as session:
            feed_model = session.query(FeedModel).filter(FeedModel.feed_url == feed_url).first()
            return self._model_to_feed(feed_model) if feed_model else None

    def get_active_feeds(self) -> List[Feed]:
        """Get all active feeds"""
        with self.db.get_session() as session:
            feed_models = session.query(FeedModel).filter(FeedModel.active == True).all()
            return [self._model_to_feed(model) for model in feed_models]

    def update_last_checked(self, feed_id: int, last_checked: datetime, last_episode_date: datetime = None):
        """Update feed last checked timestamp"""
        with self.db.get_session() as session:
            try:
                feed_model = session.query(FeedModel).filter(FeedModel.id == feed_id).first()
                if feed_model:
                    feed_model.last_checked = last_checked
                    if last_episode_date:
                        feed_model.last_episode_date = last_episode_date
                    feed_model.updated_at = datetime.now(timezone.utc)
                    session.commit()
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to update feed {feed_id}: {e}")
                raise

    def increment_failure(self, feed_id: int):
        """Increment consecutive failures count"""
        with self.db.get_session() as session:
            try:
                feed_model = session.query(FeedModel).filter(FeedModel.id == feed_id).first()
                if feed_model:
                    feed_model.consecutive_failures += 1
                    feed_model.updated_at = datetime.now(timezone.utc)
                    session.commit()
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to increment failure for feed {feed_id}: {e}")
                raise

    def reset_failures(self, feed_id: int):
        """Reset consecutive failures count"""
        with self.db.get_session() as session:
            try:
                feed_model = session.query(FeedModel).filter(FeedModel.id == feed_id).first()
                if feed_model:
                    feed_model.consecutive_failures = 0
                    feed_model.updated_at = datetime.now(timezone.utc)
                    session.commit()
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to reset failures for feed {feed_id}: {e}")
                raise

    def get_all(self) -> List[Feed]:
        """Get all feeds regardless of active state"""
        with self.db.get_session() as session:
            feed_models = session.query(FeedModel).order_by(FeedModel.title).all()
            return [self._model_to_feed(model) for model in feed_models]

    def get_by_id(self, feed_id: int) -> Optional[Feed]:
        """Get feed by ID"""
        with self.db.get_session() as session:
            feed_model = session.query(FeedModel).filter(FeedModel.id == feed_id).first()
            return self._model_to_feed(feed_model) if feed_model else None

    def get_by_title(self, title: str) -> Optional[Feed]:
        """Get feed by title"""
        with self.db.get_session() as session:
            feed_model = session.query(FeedModel).filter(FeedModel.title == title).first()
            return self._model_to_feed(feed_model) if feed_model else None

    def set_active(self, feed_id: int, active: bool):
        """Set feed active status"""
        with self.db.get_session() as session:
            try:
                feed_model = session.query(FeedModel).filter(FeedModel.id == feed_id).first()
                if feed_model:
                    feed_model.active = active
                    feed_model.updated_at = datetime.now(timezone.utc)
                    session.commit()
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to set active status for feed {feed_id}: {e}")
                raise

    def update_title(self, feed_id: int, title: str):
        """Update feed title"""
        with self.db.get_session() as session:
            try:
                feed_model = session.query(FeedModel).filter(FeedModel.id == feed_id).first()
                if feed_model:
                    feed_model.title = title
                    feed_model.updated_at = datetime.now(timezone.utc)
                    session.commit()
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to update title for feed {feed_id}: {e}")
                raise

    def _model_to_feed(self, model: FeedModel) -> Feed:
        """Convert SQLAlchemy model to dataclass"""
        return Feed(
            id=model.id,
            feed_url=model.feed_url,
            title=model.title,
            description=model.description,
            active=model.active,
            consecutive_failures=model.consecutive_failures,
            last_checked=model.last_checked,
            last_episode_date=model.last_episode_date,
            total_episodes_processed=model.total_episodes_processed,
            total_episodes_failed=model.total_episodes_failed,
            created_at=model.created_at,
            updated_at=model.updated_at
        )

class EpisodeRepository:
    """Repository for Episode database operations using SQLAlchemy"""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def create(self, episode: Episode) -> int:
        """Create new episode and return ID"""
        with self.db.get_session() as session:
            try:
                episode_model = EpisodeModel(
                    episode_guid=episode.episode_guid,
                    feed_id=episode.feed_id,
                    title=episode.title,
                    published_date=episode.published_date,
                    audio_url=episode.audio_url,
                    duration_seconds=episode.duration_seconds,
                    description=episode.description,
                    status=episode.status,
                    scores=episode.scores,
                    scored_at=episode.scored_at,
                    audio_path=episode.audio_path,
                    audio_downloaded_at=episode.audio_downloaded_at,
                    transcript_path=episode.transcript_path,
                    transcript_content=episode.transcript_content,
                    transcript_generated_at=episode.transcript_generated_at,
                    transcript_word_count=episode.transcript_word_count,
                    chunk_count=episode.chunk_count,
                    failure_count=episode.failure_count,
                    failure_reason=episode.failure_reason,
                    last_failure_at=episode.last_failure_at
                )
                session.add(episode_model)
                session.commit()
                session.refresh(episode_model)
                return episode_model.id
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to create episode: {e}")
                raise

    def get_or_create(self, episode: Episode) -> tuple[int, bool]:
        """Get existing episode by guid or create new one.

        Returns:
            Tuple of (episode_id, was_created) where was_created is True if a new
            episode was created, False if an existing one was found.
        """
        existing = self.get_by_episode_guid(episode.episode_guid)
        if existing:
            return existing.id, False
        return self.create(episode), True

    def get_by_episode_guid(self, episode_guid: str) -> Optional[Episode]:
        """Get episode by episode_guid"""
        with self.db.get_session() as session:
            episode_model = session.query(EpisodeModel).filter(EpisodeModel.episode_guid == episode_guid).first()
            return self._model_to_episode(episode_model) if episode_model else None

    def get_by_status(self, status: str) -> List[Episode]:
        """Get all episodes with specific status"""
        with self.db.get_session() as session:
            episode_models = session.query(EpisodeModel)\
                .filter(EpisodeModel.status == status)\
                .order_by(EpisodeModel.published_date.desc())\
                .all()
            return [self._model_to_episode(model) for model in episode_models]

    def get_pending_by_priority(self, limit: Optional[int] = None) -> List[Episode]:
        """Get pending episodes ordered by feed priority (lower = higher priority),
        then published_date desc as tiebreaker. Used by the standalone audio cron."""
        with self.db.get_session() as session:
            query = session.query(EpisodeModel)\
                .join(FeedModel, EpisodeModel.feed_id == FeedModel.id)\
                .filter(EpisodeModel.status == 'pending')\
                .order_by(FeedModel.priority.asc(), EpisodeModel.published_date.desc())
            if limit is not None:
                query = query.limit(limit)
            return [self._model_to_episode(model) for model in query.all()]

    def get_pending_balanced(self, youtube_limit: Optional[int] = None,
                             rss_limit: Optional[int] = None) -> List[Episode]:
        """Get pending episodes with separate caps per feed type.
        YouTube and RSS subsets are independently priority-ordered, then concatenated.
        Prevents one feed type's backlog from starving the other in audio cron runs."""
        with self.db.get_session() as session:
            yt_query = session.query(EpisodeModel)\
                .join(FeedModel, EpisodeModel.feed_id == FeedModel.id)\
                .filter(EpisodeModel.status == 'pending')\
                .filter(FeedModel.feed_type == 'youtube')\
                .order_by(FeedModel.priority.asc(), EpisodeModel.published_date.desc())
            if youtube_limit is not None:
                yt_query = yt_query.limit(youtube_limit)
            yt_models = yt_query.all()

            rss_query = session.query(EpisodeModel)\
                .join(FeedModel, EpisodeModel.feed_id == FeedModel.id)\
                .filter(EpisodeModel.status == 'pending')\
                .filter(FeedModel.feed_type != 'youtube')\
                .order_by(FeedModel.priority.asc(), EpisodeModel.published_date.desc())
            if rss_limit is not None:
                rss_query = rss_query.limit(rss_limit)
            rss_models = rss_query.all()

            return [self._model_to_episode(m) for m in (yt_models + rss_models)]

    def get_by_status_list(self, statuses: List[str]) -> List[Episode]:
        """Get all episodes with any of the specified statuses"""
        with self.db.get_session() as session:
            episode_models = session.query(EpisodeModel)\
                .filter(EpisodeModel.status.in_(statuses))\
                .filter(EpisodeModel.transcript_path.isnot(None))\
                .order_by(EpisodeModel.id)\
                .all()
            return [self._model_to_episode(model) for model in episode_models]

    def get_scored_episodes_for_topic(self, topic: str, min_score: float = 0.65,
                                    start_date: date = None, end_date: date = None,
                                    exclude_digested: bool = True) -> List[Episode]:
        """Get episodes scored above threshold for specific topic

        Args:
            topic: Topic to filter by
            min_score: Minimum score threshold (0.65 default)
            start_date: Optional start date filter
            end_date: Optional end date filter
            exclude_digested: If True, exclude episodes that have already been digested

        Returns:
            List of qualifying episodes sorted by score (highest first)
        """
        with self.db.get_session() as session:
            # Use database-agnostic JSON filtering
            # Only get episodes that are in 'scored' status (this naturally excludes 'digested' episodes)
            # The exclude_digested parameter is for explicit control, though it's already implicit in the status filter
            query = session.query(EpisodeModel)\
                .filter(EpisodeModel.scores.isnot(None))

            if exclude_digested:
                # Only include scored episodes (not digested, not failed, etc.)
                query = query.filter(EpisodeModel.status == 'scored')
            else:
                # Include both scored and digested episodes (for re-processing if needed)
                query = query.filter(EpisodeModel.status.in_(['scored', 'digested']))

            if start_date:
                query = query.filter(EpisodeModel.published_date >= start_date)

            if end_date:
                query = query.filter(EpisodeModel.published_date <= end_date)

            episode_models = query.order_by(EpisodeModel.published_date.desc()).all()

            # Filter and sort by topic score in Python (database-agnostic)
            scored_episodes = []
            for model in episode_models:
                if model.scores and topic in model.scores:
                    score = model.scores[topic]
                    if isinstance(score, (int, float)) and score >= min_score:
                        scored_episodes.append((score, model))

            # Sort by score descending, then by date descending
            scored_episodes.sort(key=lambda x: (x[0], x[1].published_date), reverse=True)

            return [self._model_to_episode(model) for score, model in scored_episodes]

    def update_status(self, episode_guid: str, status: str):
        """Update episode status"""
        with self.db.get_session() as session:
            try:
                episode_model = session.query(EpisodeModel)\
                    .filter(EpisodeModel.episode_guid == episode_guid).first()
                if episode_model:
                    episode_model.status = status
                    episode_model.updated_at = datetime.now(timezone.utc)
                    session.commit()
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to update episode status {episode_guid}: {e}")
                raise

    def mark_episodes_as_digested(self, episode_guids: List[str]):
        """Mark multiple episodes as digested"""
        with self.db.get_session() as session:
            try:
                session.query(EpisodeModel)\
                    .filter(EpisodeModel.episode_guid.in_(episode_guids))\
                    .update({
                        EpisodeModel.status: 'digested',
                        EpisodeModel.updated_at: datetime.now(timezone.utc)
                    })
                session.commit()
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to mark episodes as digested: {e}")
                raise

    def reset_stuck_processing_episodes(self, timeout_minutes: int = 10) -> int:
        """Reset episodes stuck in 'processing' status back to 'pending'

        Args:
            timeout_minutes: Episodes in processing status longer than this are considered stuck

        Returns:
            Number of episodes reset
        """
        from datetime import timedelta
        timeout_threshold = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)

        with self.db.get_session() as session:
            try:
                # Use synchronize_session=False to avoid timezone comparison issues
                # between Python datetime objects and database values
                reset_count = session.query(EpisodeModel)\
                    .filter(EpisodeModel.status == 'processing')\
                    .filter(EpisodeModel.updated_at < timeout_threshold)\
                    .update({
                        EpisodeModel.status: 'pending',
                        EpisodeModel.updated_at: datetime.now(timezone.utc)
                    }, synchronize_session=False)

                session.commit()

                if reset_count > 0:
                    logger.info(f"Reset {reset_count} stuck episode(s) from 'processing' to 'pending'")

                return reset_count
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to reset stuck processing episodes: {e}")
                raise

    def update_audio_download(self, episode_guid: str, audio_path: str):
        """Update audio download information"""
        with self.db.get_session() as session:
            try:
                episode_model = session.query(EpisodeModel)\
                    .filter(EpisodeModel.episode_guid == episode_guid).first()
                if episode_model:
                    episode_model.audio_path = audio_path
                    episode_model.audio_downloaded_at = datetime.now(timezone.utc)
                    episode_model.updated_at = datetime.now(timezone.utc)
                    session.commit()
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to update audio download for episode {episode_guid}: {e}")
                raise

    def append_transcript_chunk(self, episode_guid: str, chunk_text: str, chunk_number: int) -> int:
        """
        Append transcript chunk to existing transcript content (memory-efficient incremental writes).
        Returns updated word count.
        """
        with self.db.get_session() as session:
            try:
                episode_model = session.query(EpisodeModel)\
                    .filter(EpisodeModel.episode_guid == episode_guid).first()

                if not episode_model:
                    raise ValueError(f"Episode not found: {episode_guid}")

                # Append chunk to existing transcript with space separator
                if episode_model.transcript_content:
                    episode_model.transcript_content += " " + chunk_text
                else:
                    episode_model.transcript_content = chunk_text

                # Update word count
                word_count = len(episode_model.transcript_content.split())
                episode_model.transcript_word_count = word_count
                episode_model.updated_at = datetime.now(timezone.utc)

                # Update status to 'transcribed' on first chunk
                if chunk_number == 1:
                    episode_model.status = 'processing'
                    episode_model.transcript_generated_at = datetime.now(timezone.utc)

                session.commit()
                return word_count

            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to append transcript chunk for episode {episode_guid}: {e}")
                raise

    def finalize_transcript(self, episode_guid: str):
        """Mark transcript as complete after all chunks appended"""
        with self.db.get_session() as session:
            try:
                episode_model = session.query(EpisodeModel)\
                    .filter(EpisodeModel.episode_guid == episode_guid).first()

                if episode_model:
                    episode_model.status = 'transcribed'
                    episode_model.updated_at = datetime.now(timezone.utc)
                    session.commit()

            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to finalize transcript for episode {episode_guid}: {e}")
                raise

    def update_transcript(self, episode_guid: str, transcript_path: str, word_count: int, transcript_content: Optional[str] = None):
        """Update transcript information"""
        with self.db.get_session() as session:
            try:
                episode_model = session.query(EpisodeModel)\
                    .filter(EpisodeModel.episode_guid == episode_guid).first()
                if episode_model:
                    episode_model.transcript_path = transcript_path
                    episode_model.transcript_generated_at = datetime.now(timezone.utc)
                    episode_model.transcript_word_count = word_count
                    episode_model.status = 'transcribed'
                    episode_model.updated_at = datetime.now(timezone.utc)
                    if transcript_content is not None:
                        episode_model.transcript_content = transcript_content
                    session.commit()
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to update transcript for episode {episode_guid}: {e}")
                raise

    def update_scores(self, episode_guid: str, scores: Dict[str, float]):
        """Update AI scores for episode"""
        with self.db.get_session() as session:
            try:
                episode_model = session.query(EpisodeModel)\
                    .filter(EpisodeModel.episode_guid == episode_guid).first()
                if episode_model:
                    episode_model.scores = scores
                    episode_model.scored_at = datetime.now(timezone.utc)
                    episode_model.status = 'scored'
                    episode_model.updated_at = datetime.now(timezone.utc)
                    session.commit()
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to update scores for episode {episode_guid}: {e}")
                raise

    def mark_failure(self, episode_guid: str, failure_reason: str):
        """Mark episode as failed and increment failure count"""
        with self.db.get_session() as session:
            try:
                episode_model = session.query(EpisodeModel)\
                    .filter(EpisodeModel.episode_guid == episode_guid).first()
                if episode_model:
                    episode_model.failure_count += 1
                    episode_model.failure_reason = failure_reason
                    episode_model.last_failure_at = datetime.now(timezone.utc)
                    if episode_model.failure_count >= 3:
                        episode_model.status = 'failed'
                    episode_model.updated_at = datetime.now(timezone.utc)
                    session.commit()
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to mark failure for episode {episode_guid}: {e}")
                raise

    def get_recent_episodes(self, limit: int = 10) -> List[Episode]:
        """Get recent episodes for debugging/monitoring"""
        with self.db.get_session() as session:
            episode_models = session.query(EpisodeModel)\
                .order_by(EpisodeModel.published_date.desc())\
                .limit(limit)\
                .all()
            return [self._model_to_episode(model) for model in episode_models]

    def get_scored_episodes_sample(self, limit: int = 5) -> List[Episode]:
        """Get sample of scored episodes for testing/debugging"""
        with self.db.get_session() as session:
            episode_models = session.query(EpisodeModel)\
                .filter(EpisodeModel.status == 'scored')\
                .filter(EpisodeModel.scores.isnot(None))\
                .limit(limit)\
                .all()
            return [self._model_to_episode(model) for model in episode_models]

    def count_scored_since(self, cutoff: datetime) -> int:
        """Count episodes whose scored_at timestamp is at or after ``cutoff``.

        Used by the orchestrator to report an accurate scored-episode count even
        when the scoring/audio phase runs out-of-band on a dedicated cron (the
        ``--skip-audio`` nightly path scores nothing in-run, so a bare in-run
        count is a misleading ``0`` — see kanban #2423).
        """
        with self.db.get_session() as session:
            return session.query(EpisodeModel)\
                .filter(EpisodeModel.scored_at.isnot(None))\
                .filter(EpisodeModel.scored_at >= cutoff)\
                .count()

    def get_failed_episodes(self) -> List[Episode]:
        """Get episodes that have failed processing"""
        with self.db.get_session() as session:
            episode_models = session.query(EpisodeModel)\
                .filter(EpisodeModel.status == 'failed')\
                .order_by(EpisodeModel.last_failure_at.desc())\
                .all()
            return [self._model_to_episode(model) for model in episode_models]

    def get_undigested_episodes(self, limit: int = 50) -> List[Episode]:
        """Get episodes that haven't been included in any digest.

        Returns episodes that are scored but not yet digested, ordered by
        published date (most recent first).

        Args:
            limit: Maximum number of episodes to return. Default is 50.

        Returns:
            List of Episode objects that are ready for digest inclusion.
        """
        with self.db.get_session() as session:
            episode_models = session.query(EpisodeModel)\
                .filter(EpisodeModel.status == 'scored')\
                .filter(EpisodeModel.scores.isnot(None))\
                .order_by(EpisodeModel.published_date.desc())\
                .limit(limit)\
                .all()
            return [self._model_to_episode(model) for model in episode_models]

    def cleanup_old_episodes(self, days_old: int = 14):
        """Delete episodes older than specified days"""
        with self.db.get_session() as session:
            try:
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
                deleted_count = session.query(EpisodeModel)\
                    .filter(EpisodeModel.published_date < cutoff_date)\
                    .delete()
                session.commit()
                return deleted_count
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to cleanup old episodes: {e}")
                raise

    def get_by_id(self, episode_id: int) -> Optional[Episode]:
        """Get episode by ID"""
        with self.db.get_session() as session:
            episode_model = session.query(EpisodeModel).filter(EpisodeModel.id == episode_id).first()
            return self._model_to_episode(episode_model) if episode_model else None

    def update_status_by_id(self, episode_id: int, status: str):
        """Update episode status by ID"""
        with self.db.get_session() as session:
            try:
                episode_model = session.query(EpisodeModel).filter(EpisodeModel.id == episode_id).first()
                if episode_model:
                    episode_model.status = status
                    episode_model.updated_at = datetime.now(timezone.utc)
                    session.commit()
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to update episode {episode_id} status: {e}")
                raise

    def get_by_status(self, status: str) -> List[Episode]:
        """Get episodes by status"""
        with self.db.get_session() as session:
            episode_models = session.query(EpisodeModel).filter(EpisodeModel.status == status).all()
            return [self._model_to_episode(model) for model in episode_models]

    def get_by_id(self, episode_id: int) -> Optional[Episode]:
        """Get episode by ID"""
        with self.db.get_session() as session:
            episode_model = session.query(EpisodeModel).filter(EpisodeModel.id == episode_id).first()
            return self._model_to_episode(episode_model) if episode_model else None

    def update_transcript_path(self, episode_id: int, transcript_path: str):
        """Update episode transcript path"""
        with self.db.get_session() as session:
            try:
                episode_model = session.query(EpisodeModel).filter(EpisodeModel.id == episode_id).first()
                if episode_model:
                    episode_model.transcript_path = transcript_path
                    episode_model.updated_at = datetime.now(timezone.utc)
                    session.commit()
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to update transcript path for episode {episode_id}: {e}")
                raise

    def update_feed_id(self, episode_id: int, feed_id: int):
        """Update episode feed ID"""
        with self.db.get_session() as session:
            try:
                episode_model = session.query(EpisodeModel).filter(EpisodeModel.id == episode_id).first()
                if episode_model:
                    episode_model.feed_id = feed_id
                    episode_model.updated_at = datetime.now(timezone.utc)
                    session.commit()
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to update feed ID for episode {episode_id}: {e}")
                raise

    def get_by_feed_id(self, feed_id: int, limit: int = None) -> List[Episode]:
        """Get episodes by feed ID"""
        with self.db.get_session() as session:
            query = session.query(EpisodeModel).filter(EpisodeModel.feed_id == feed_id)
            if limit:
                query = query.limit(limit)
            episode_models = query.all()
            return [self._model_to_episode(model) for model in episode_models]

    def _model_to_episode(self, model: EpisodeModel) -> Episode:
        """Convert SQLAlchemy model to dataclass"""
        return Episode(
            id=model.id,
            episode_guid=model.episode_guid,
            feed_id=model.feed_id,
            title=model.title,
            published_date=model.published_date,
            audio_url=model.audio_url,
            duration_seconds=model.duration_seconds,
            description=model.description,
            audio_path=model.audio_path,
            audio_downloaded_at=model.audio_downloaded_at,
            transcript_path=model.transcript_path,
            transcript_content=model.transcript_content,
            transcript_generated_at=model.transcript_generated_at,
            transcript_word_count=model.transcript_word_count,
            chunk_count=model.chunk_count,
            scores=model.scores,
            scored_at=model.scored_at,
            status=model.status,
            failure_count=model.failure_count,
            failure_reason=model.failure_reason,
            last_failure_at=model.last_failure_at,
            created_at=model.created_at,
            updated_at=model.updated_at
        )

class DigestRepository:
    """Repository for Digest database operations using SQLAlchemy"""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def create(self, digest: Digest) -> int:
        """Create new digest and return ID.

        Note: episode_ids is deprecated (Issue #10). Use digest_episode_links table.
        """
        with self.db.get_session() as session:
            try:
                # Use provided timestamp or generate new one
                digest_timestamp = digest.digest_timestamp or datetime.now(timezone.utc)

                # Note: episode_ids is deprecated, using digest_episode_links instead
                digest_model = DigestModel(
                    topic=digest.topic,
                    digest_date=digest.digest_date,
                    digest_timestamp=digest_timestamp,
                    episode_count=digest.episode_count,
                    script_path=digest.script_path,
                    script_content=digest.script_content,
                    script_content_predupe=digest.script_content_predupe,
                    script_word_count=digest.script_word_count,
                    mp3_path=digest.mp3_path,
                    mp3_duration_seconds=digest.mp3_duration_seconds,
                    mp3_title=digest.mp3_title,
                    mp3_summary=digest.mp3_summary,
                    average_score=digest.average_score,
                    github_url=digest.github_url,
                    published_at=digest.published_at,
                    status=digest.status or 'draft'
                )
                session.add(digest_model)
                session.commit()
                session.refresh(digest_model)
                return digest_model.id
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to create digest: {e}")
                raise

    def get_by_topic_date(self, topic: str, digest_date: date) -> Optional[Digest]:
        """Get digest by topic and date"""
        with self.db.get_session() as session:
            digest_model = session.query(DigestModel)\
                .filter(DigestModel.topic == topic, DigestModel.digest_date == digest_date)\
                .first()
            return self._model_to_digest(digest_model) if digest_model else None

    def get_by_date(self, digest_date: date) -> List[Digest]:
        """Get all digests for a specific date"""
        with self.db.get_session() as session:
            digest_models = session.query(DigestModel)\
                .filter(DigestModel.digest_date == digest_date)\
                .all()
            return [self._model_to_digest(model) for model in digest_models]

    def get_by_id(self, digest_id: int) -> Optional[Digest]:
        """Get digest by ID"""
        with self.db.get_session() as session:
            digest_model = session.query(DigestModel).filter(DigestModel.id == digest_id).first()
            return self._model_to_digest(digest_model) if digest_model else None

    def update_script(self, digest_id: int, script_path: str, word_count: int, script_content: Optional[str] = None):
        """Update script information and set status to 'generated'"""
        with self.db.get_session() as session:
            try:
                digest_model = session.query(DigestModel).filter(DigestModel.id == digest_id).first()
                if digest_model:
                    digest_model.script_path = script_path
                    digest_model.script_word_count = word_count
                    if script_content is not None:
                        digest_model.script_content = script_content
                    digest_model.status = 'generated'
                    session.commit()
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to update script for digest {digest_id}: {e}")
                raise

    def update_audio(self, digest_id: int, mp3_path: str, duration_seconds: int,
                    title: str, summary: str):
        """Update audio information and set status to 'audio_generated'"""
        with self.db.get_session() as session:
            try:
                digest_model = session.query(DigestModel).filter(DigestModel.id == digest_id).first()
                if digest_model:
                    digest_model.mp3_path = mp3_path
                    digest_model.mp3_duration_seconds = duration_seconds
                    digest_model.mp3_title = title
                    digest_model.mp3_summary = summary
                    digest_model.status = 'audio_generated'
                    session.commit()
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to update audio for digest {digest_id}: {e}")
                raise

    def update_published(self, digest_id: int, github_url: str):
        """Update publishing information and set status to 'published'"""
        with self.db.get_session() as session:
            try:
                digest_model = session.query(DigestModel).filter(DigestModel.id == digest_id).first()
                if digest_model:
                    digest_model.github_url = github_url
                    digest_model.published_at = datetime.now(timezone.utc)
                    digest_model.status = 'published'
                    session.commit()
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to update published info for digest {digest_id}: {e}")
                raise

    def get_recent_digests(self, days: int = 7) -> List[Digest]:
        """Get recent digests for RSS feed generation"""
        from datetime import timedelta
        with self.db.get_session() as session:
            cutoff_date = date.today() - timedelta(days=days)
            digest_models = session.query(DigestModel)\
                .filter(DigestModel.digest_date >= cutoff_date)\
                .filter(DigestModel.mp3_path.isnot(None))\
                .order_by(DigestModel.digest_date.desc(), DigestModel.topic)\
                .all()
            return [self._model_to_digest(model) for model in digest_models]

    def get_latest_digest_date(self) -> Optional[date]:
        """Get the most recent digest date"""
        with self.db.get_session() as session:
            result = session.query(DigestModel.digest_date)\
                .order_by(DigestModel.digest_date.desc())\
                .first()
            return result[0] if result else None

    def get_published_digests(self) -> List[Digest]:
        """Get all digests that have GitHub URLs (are published)"""
        with self.db.get_session() as session:
            digest_models = session.query(DigestModel)\
                .filter(DigestModel.github_url.isnot(None))\
                .order_by(DigestModel.digest_date.desc())\
                .all()
            return [self._model_to_digest(model) for model in digest_models]

    def clear_github_url(self, digest_id: int):
        """Clear the GitHub URL for a digest (unpublish)"""
        with self.db.get_session() as session:
            try:
                digest_model = session.query(DigestModel).filter(DigestModel.id == digest_id).first()
                if digest_model:
                    digest_model.github_url = None
                    digest_model.published_at = None
                    session.commit()
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to clear GitHub URL for digest {digest_id}: {e}")
                raise

    def update_digest(self, digest_id: int, update_data: Dict[str, Any]):
        """Update digest with provided data"""
        with self.db.get_session() as session:
            try:
                digest_model = session.query(DigestModel).filter(DigestModel.id == digest_id).first()
                if digest_model:
                    for key, value in update_data.items():
                        if hasattr(digest_model, key):
                            setattr(digest_model, key, value)
                    session.commit()
                else:
                    logger.warning(f"Digest {digest_id} not found for update")
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to update digest {digest_id}: {e}")
                raise

    def get_published_digests_without_rss(self) -> List[Digest]:
        """Get published digests that don't have RSS publication timestamp (not applicable in new schema)"""
        # In the new schema, we don't track RSS publication separately
        # Return empty list since we'll handle RSS generation differently
        return []

    def get_digests_pending_tts(self) -> List[Digest]:
        """Get digests that have scripts but no MP3 files (pending TTS)

        Filters out 0-episode digests since they have no content to convert to audio.
        Orders by episode_count DESC so digests with content are processed first.
        Accepts digests with either script_path or script_content (database-first).

        v3.55 (kanban #1617): 'General Summary' topic is permanently excluded.
        It has no voice configuration and can never be converted to audio; any
        surviving rows from before the disable are silently ignored here so they
        can never perpetually orphan in pending-TTS.
        """
        from sqlalchemy import or_
        with self.db.get_session() as session:
            digest_models = session.query(DigestModel)\
                .filter(or_(
                    DigestModel.script_path.isnot(None),
                    DigestModel.script_content.isnot(None)
                ))\
                .filter(DigestModel.mp3_path.is_(None))\
                .filter(DigestModel.episode_count > 0)\
                .filter(DigestModel.topic != "General Summary")\
                .order_by(DigestModel.episode_count.desc(), DigestModel.digest_date.asc())\
                .all()
            return [self._model_to_digest(model) for model in digest_models]

    def get_digests_completed(self) -> List[Digest]:
        """Get digests that have MP3 files (completed TTS)"""
        with self.db.get_session() as session:
            digest_models = session.query(DigestModel)\
                .filter(DigestModel.mp3_path.isnot(None))\
                .order_by(DigestModel.digest_date.desc())\
                .all()
            return [self._model_to_digest(model) for model in digest_models]

    def _model_to_digest(self, model: DigestModel) -> Digest:
        """Convert SQLAlchemy model to dataclass.

        Issue #10/#29: episode_ids field removed - use digest_episode_links table.
        """
        return Digest(
            id=model.id,
            topic=model.topic,
            digest_date=model.digest_date,
            digest_timestamp=model.digest_timestamp,
            script_path=model.script_path,
            script_content=model.script_content,
            script_content_predupe=getattr(model, 'script_content_predupe', None),
            script_word_count=model.script_word_count,
            mp3_path=model.mp3_path,
            mp3_duration_seconds=model.mp3_duration_seconds,
            mp3_title=model.mp3_title,
            mp3_summary=model.mp3_summary,
            episode_count=model.episode_count,
            average_score=model.average_score,
            github_url=model.github_url,
            published_at=model.published_at,
            generated_at=model.generated_at,
            status=getattr(model, 'status', 'draft')
        )


class TopicRepository:
    """Repository for topic metadata and instructions."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def get_active_topics(self) -> List[Topic]:
        """Return all active topics ordered by sort order/name."""
        return self._safe_query_topics(active_only=True)

    def get_all_topics(self) -> List[Topic]:
        """Return all topics (active + inactive)."""
        return self._safe_query_topics(active_only=False)

    def update_instructions(self, topic_id: int, instructions_md: str,
                            change_note: str = None, created_by: str = None) -> TopicInstructionVersion:
        """Persist new instruction text and version for a topic."""
        with self.db.get_session() as session:
            try:
                topic_model = session.query(TopicModel).filter(TopicModel.id == topic_id).first()
                if topic_model is None:
                    raise ValueError(f"Topic {topic_id} not found")

                topic_model.instructions_md = instructions_md
                topic_model.updated_at = datetime.now(timezone.utc)

                latest_version = session.query(func.max(TopicInstructionModel.version))\
                    .filter(TopicInstructionModel.topic_id == topic_id)\
                    .scalar() or 0

                version_model = TopicInstructionModel(
                    topic_id=topic_id,
                    version=latest_version + 1,
                    instructions_md=instructions_md,
                    change_note=change_note,
                    created_at=datetime.now(timezone.utc),
                    created_by=created_by
                )
                session.add(version_model)
                session.commit()
                session.refresh(topic_model)
                session.refresh(version_model)
                return self._model_to_instruction_version(version_model)
            except SQLAlchemyError as exc:
                session.rollback()
                logger.error(f"Failed to update instructions for topic {topic_id}: {exc}")
                raise

    def upsert_topic(self, topic: Topic) -> Topic:
        """Create or update a topic based on slug."""
        if not topic.slug:
            raise ValueError("Topic slug must be provided for upsert")

        with self.db.get_session() as session:
            try:
                model = session.query(TopicModel).filter(TopicModel.slug == topic.slug).first()
                now = datetime.now(timezone.utc)
                voice_settings = topic.voice_settings if topic.voice_settings is None else dict(topic.voice_settings)

                if model:
                    model.name = topic.name
                    model.description = topic.description
                    model.voice_id = topic.voice_id
                    model.voice_settings = voice_settings
                    model.is_active = topic.is_active
                    model.sort_order = topic.sort_order
                    model.updated_at = now
                    if topic.last_generated_at:
                        model.last_generated_at = topic.last_generated_at
                else:
                    model = TopicModel(
                        slug=topic.slug,
                        name=topic.name,
                        description=topic.description,
                        voice_id=topic.voice_id,
                        voice_settings=voice_settings,
                        is_active=topic.is_active,
                        sort_order=topic.sort_order,
                        instructions_md=topic.instructions_md,
                        last_generated_at=topic.last_generated_at,
                        created_at=topic.created_at or now,
                        updated_at=topic.updated_at or now,
                    )
                    session.add(model)

                if topic.instructions_md:
                    model.instructions_md = topic.instructions_md

                session.commit()
                session.refresh(model)
                return self._model_to_topic(model)
            except SQLAlchemyError as exc:
                session.rollback()
                logger.error(f"Failed to upsert topic {topic.slug}: {exc}")
                raise

    def record_generation(self, topic_id: int, generated_at: datetime | None = None):
        """Update topic metadata when a digest is generated."""
        with self.db.get_session() as session:
            try:
                topic_model = session.query(TopicModel).filter(TopicModel.id == topic_id).first()
                if topic_model is None:
                    return
                topic_model.last_generated_at = generated_at or datetime.now(timezone.utc)
                topic_model.updated_at = datetime.now(timezone.utc)
                session.commit()
            except SQLAlchemyError as exc:
                session.rollback()
                logger.error(f"Failed to record digest generation for topic {topic_id}: {exc}")

    def _safe_query_topics(self, active_only: bool) -> List[Topic]:
        with self.db.get_session() as session:
            try:
                query = session.query(TopicModel)
                if active_only:
                    query = query.filter(TopicModel.is_active == True)  # noqa: E712
                topic_models = query.order_by(TopicModel.sort_order.asc(), TopicModel.name.asc()).all()
                return [self._model_to_topic(model) for model in topic_models]
            except ProgrammingError as exc:
                # Table might not exist yet during migrations or local dev; log and fallback
                logger.debug(f"Topics table unavailable: {exc}")
                return []

    def _model_to_topic(self, model: TopicModel) -> Topic:
        return Topic(
            id=model.id,
            slug=model.slug,
            name=model.name,
            description=model.description,
            voice_id=model.voice_id,
            voice_settings=model.voice_settings,
            instructions_md=model.instructions_md,
            is_active=model.is_active,
            sort_order=model.sort_order,
            last_generated_at=model.last_generated_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
            use_dialogue_api=getattr(model, 'use_dialogue_api', False),
            dialogue_model=getattr(model, 'dialogue_model', 'eleven_turbo_v2_5'),
            voice_config=getattr(model, 'voice_config', None),
            enable_topic_tracking=getattr(model, 'enable_topic_tracking', False)
        )

    def _model_to_instruction_version(self, model: TopicInstructionModel) -> TopicInstructionVersion:
        return TopicInstructionVersion(
            id=model.id,
            topic_id=model.topic_id,
            version=model.version,
            instructions_md=model.instructions_md,
            change_note=model.change_note,
            created_at=model.created_at,
            created_by=model.created_by
        )


class DigestEpisodeLinkRepository:
    """Repository for digest ↔ episode relationship records."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def replace_links_for_digest(self, digest_id: int, links: List[DigestEpisodeLink]):
        """Replace episode links for a given digest in a single transaction."""
        with self.db.get_session() as session:
            try:
                session.query(DigestEpisodeLinkModel).filter(DigestEpisodeLinkModel.digest_id == digest_id).delete()
                for link in links:
                    session.add(DigestEpisodeLinkModel(
                        digest_id=digest_id,
                        episode_id=link.episode_id,
                        topic=link.topic,
                        score=link.score,
                        position=link.position,
                        created_at=link.created_at or datetime.now(timezone.utc)
                    ))
                session.commit()
            except SQLAlchemyError as exc:
                session.rollback()
                logger.error(f"Failed to replace digest links for digest {digest_id}: {exc}")
                raise

    def get_episode_ids_for_digest(self, digest_id: int) -> List[int]:
        """Get all episode IDs linked to a digest, ordered by position.

        This is the single source of truth for digest-episode relationships.
        Issue #10: Replaces usage of Digest.episode_ids JSON column.
        """
        with self.db.get_session() as session:
            links = session.query(DigestEpisodeLinkModel)\
                .filter(DigestEpisodeLinkModel.digest_id == digest_id)\
                .order_by(DigestEpisodeLinkModel.position.asc())\
                .all()
            return [link.episode_id for link in links]


class PipelineRunRepository:
    """Repository for pipeline run metadata used by hosted dashboard."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def upsert(self, run: PipelineRun):
        with self.db.get_session() as session:
            try:
                model = session.query(PipelineRunModel).filter(PipelineRunModel.id == run.id).first()
                if model:
                    for field in ("workflow_run_id", "workflow_name", "trigger", "status", "conclusion",
                                  "started_at", "finished_at", "phase", "notes"):
                        value = getattr(run, field)
                        if value is not None:
                            setattr(model, field, value)
                    model.updated_at = datetime.now(timezone.utc)
                else:
                    model = PipelineRunModel(
                        id=run.id,
                        workflow_run_id=run.workflow_run_id,
                        workflow_name=run.workflow_name,
                        trigger=run.trigger,
                        status=run.status,
                        conclusion=run.conclusion,
                        started_at=run.started_at,
                        finished_at=run.finished_at,
                        phase=run.phase,
                        notes=run.notes,
                        created_at=run.created_at or datetime.now(timezone.utc),
                        updated_at=run.updated_at or datetime.now(timezone.utc)
                    )
                    session.add(model)
                session.commit()
            except SQLAlchemyError as exc:
                session.rollback()
                logger.error(f"Failed to upsert pipeline run {run.id}: {exc}")
                raise

    def update_fields(self, run_id: str, **fields):
        with self.db.get_session() as session:
            try:
                model = session.query(PipelineRunModel).filter(PipelineRunModel.id == run_id).first()
                if not model:
                    return
                for key, value in fields.items():
                    if hasattr(model, key):
                        setattr(model, key, value)
                model.updated_at = datetime.now(timezone.utc)
                session.commit()
            except SQLAlchemyError as exc:
                session.rollback()
                logger.error(f"Failed to update pipeline run {run_id}: {exc}")


import threading

_database_manager_instance = None
_database_manager_lock = threading.Lock()

def get_database_manager() -> DatabaseManager:
    """Thread-safe factory function to get database manager singleton"""
    global _database_manager_instance
    if _database_manager_instance is None:
        with _database_manager_lock:
            # Double-check locking pattern
            if _database_manager_instance is None:
                _database_manager_instance = DatabaseManager()
    return _database_manager_instance


# Type variable for generic repository factory
# All repositories inherit from object and take DatabaseManager in __init__
T = TypeVar('T', FeedRepository, EpisodeRepository, DigestRepository,
            TopicRepository, DigestEpisodeLinkRepository, PipelineRunRepository,
            'PipelineLogRepository', 'WorkflowErrorRepository')


def get_repo(repo_class: Type[T], db_manager: DatabaseManager = None) -> T:
    """
    Generic factory function to get a repository instance.

    Usage:
        feed_repo = get_repo(FeedRepository)
        episode_repo = get_repo(EpisodeRepository)

        # With custom database manager:
        feed_repo = get_repo(FeedRepository, db_manager=custom_manager)

    Args:
        repo_class: The repository class to instantiate
        db_manager: Optional DatabaseManager instance. If None, uses singleton.

    Returns:
        Instance of the specified repository class
    """
    if db_manager is None:
        db_manager = get_database_manager()
    return repo_class(db_manager)


class PipelineLogRepository:
    """Repository for pipeline log storage and retrieval."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        # Table creation removed - pipeline_logs table is managed via Alembic migrations
        # The checkfirst=True query was hanging in GitHub Actions environment

    def bulk_insert(self, logs: List[PipelineLog]):
        if not logs:
            return
        with self.db.get_session() as session:
            try:
                orm_logs = [
                    PipelineLogModel(
                        run_id=log.run_id,
                        phase=log.phase,
                        timestamp=log.timestamp,
                        level=log.level,
                        logger_name=log.logger_name,
                        module=log.module,
                        function=log.function,
                        line=log.line,
                        message=log.message,
                        extra=log.extra,
                    )
                    for log in logs
                ]
                session.bulk_save_objects(orm_logs)
                session.commit()
            except SQLAlchemyError as exc:
                session.rollback()
                logger.error(f"Failed to insert pipeline logs: {exc}")
                raise

    def get_recent_logs(self, run_id: Optional[str] = None, phase: Optional[str] = None,
                         limit: int = 500) -> List[PipelineLog]:
        with self.db.get_session() as session:
            query = session.query(PipelineLogModel)
            if run_id:
                query = query.filter(PipelineLogModel.run_id == run_id)
            if phase:
                query = query.filter(PipelineLogModel.phase == phase)
            models = query.order_by(PipelineLogModel.timestamp.desc()).limit(limit).all()
            return [self._model_to_log(model) for model in models]

    def get_latest_run_logs(self, limit: int = 500) -> List[PipelineLog]:
        with self.db.get_session() as session:
            latest_run = session.query(PipelineLogModel.run_id)
            latest_run = latest_run.order_by(PipelineLogModel.timestamp.desc()).limit(1).scalar()
            if not latest_run:
                return []
            logs = session.query(PipelineLogModel).filter(
                PipelineLogModel.run_id == latest_run
            ).order_by(PipelineLogModel.timestamp.desc()).limit(limit).all()
            return [self._model_to_log(model) for model in logs]

    def _model_to_log(self, model: PipelineLogModel) -> PipelineLog:
        return PipelineLog(
            id=model.id,
            run_id=model.run_id,
            phase=model.phase,
            timestamp=model.timestamp,
            level=model.level,
            logger_name=model.logger_name,
            module=model.module,
            function=model.function,
            line=model.line,
            message=model.message,
            extra=model.extra,
        )


class WorkflowErrorRepository:
    """Repository for persistent workflow error tracking and pattern analysis."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def create(self, error: WorkflowError) -> int:
        """Create a single workflow error record and return ID."""
        with self.db.get_session() as session:
            try:
                model = WorkflowErrorModel(
                    error_date=error.error_date,
                    occurred_at=error.occurred_at,
                    run_id=error.run_id,
                    workflow_run_id=error.workflow_run_id,
                    error_category=error.error_category,
                    phase=error.phase,
                    severity=error.severity,
                    feed_id=error.feed_id,
                    feed_url=error.feed_url,
                    error_code=error.error_code,
                    error_message=error.error_message,
                    error_summary=error.error_summary,
                    extra=error.extra,
                    source_log_id=error.source_log_id,
                    resolved=error.resolved,
                    resolved_at=error.resolved_at,
                    resolution_notes=error.resolution_notes,
                )
                session.add(model)
                session.commit()
                session.refresh(model)
                return model.id
            except SQLAlchemyError as exc:
                session.rollback()
                logger.error(f"Failed to create workflow error: {exc}")
                raise

    def bulk_insert(self, errors: List[WorkflowError]) -> int:
        """Bulk insert workflow errors. Returns count of inserted records."""
        if not errors:
            return 0
        with self.db.get_session() as session:
            try:
                models = [
                    WorkflowErrorModel(
                        error_date=e.error_date,
                        occurred_at=e.occurred_at,
                        run_id=e.run_id,
                        workflow_run_id=e.workflow_run_id,
                        error_category=e.error_category,
                        phase=e.phase,
                        severity=e.severity,
                        feed_id=e.feed_id,
                        feed_url=e.feed_url,
                        error_code=e.error_code,
                        error_message=e.error_message,
                        error_summary=e.error_summary,
                        extra=e.extra,
                        source_log_id=e.source_log_id,
                        resolved=e.resolved,
                        resolved_at=e.resolved_at,
                        resolution_notes=e.resolution_notes,
                    )
                    for e in errors
                ]
                session.bulk_save_objects(models)
                session.commit()
                return len(models)
            except SQLAlchemyError as exc:
                session.rollback()
                logger.error(f"Failed to bulk insert workflow errors: {exc}")
                raise

    def get_by_date_range(self, start_date: date, end_date: date,
                          category: Optional[str] = None,
                          phase: Optional[str] = None,
                          feed_id: Optional[int] = None,
                          resolved: Optional[bool] = None) -> List[WorkflowError]:
        """Get errors within a date range with optional filters."""
        with self.db.get_session() as session:
            query = session.query(WorkflowErrorModel).filter(
                WorkflowErrorModel.error_date >= start_date,
                WorkflowErrorModel.error_date <= end_date
            )
            if category:
                query = query.filter(WorkflowErrorModel.error_category == category)
            if phase:
                query = query.filter(WorkflowErrorModel.phase == phase)
            if feed_id is not None:
                query = query.filter(WorkflowErrorModel.feed_id == feed_id)
            if resolved is not None:
                query = query.filter(WorkflowErrorModel.resolved == resolved)

            models = query.order_by(WorkflowErrorModel.occurred_at.desc()).all()
            return [self._model_to_error(m) for m in models]

    def get_error_counts_by_category(self, start_date: date, end_date: date) -> Dict[str, int]:
        """Get error counts grouped by category for a date range."""
        with self.db.get_session() as session:
            results = session.query(
                WorkflowErrorModel.error_category,
                func.count(WorkflowErrorModel.id)
            ).filter(
                WorkflowErrorModel.error_date >= start_date,
                WorkflowErrorModel.error_date <= end_date
            ).group_by(WorkflowErrorModel.error_category).all()

            return {category: count for category, count in results}

    def get_error_counts_by_phase(self, start_date: date, end_date: date) -> Dict[str, int]:
        """Get error counts grouped by phase for a date range."""
        with self.db.get_session() as session:
            results = session.query(
                WorkflowErrorModel.phase,
                func.count(WorkflowErrorModel.id)
            ).filter(
                WorkflowErrorModel.error_date >= start_date,
                WorkflowErrorModel.error_date <= end_date
            ).group_by(WorkflowErrorModel.phase).all()

            return {phase: count for phase, count in results}

    def get_feed_error_frequency(self, days_back: int = 30, min_errors: int = 1) -> List[Dict[str, Any]]:
        """Get feeds ranked by error frequency in the last N days."""
        start_date = date.today() - timedelta(days=days_back)
        with self.db.get_session() as session:
            results = session.query(
                WorkflowErrorModel.feed_id,
                WorkflowErrorModel.feed_url,
                func.count(WorkflowErrorModel.id).label('error_count'),
                func.max(WorkflowErrorModel.occurred_at).label('last_error')
            ).filter(
                WorkflowErrorModel.error_date >= start_date,
                WorkflowErrorModel.feed_id.isnot(None)
            ).group_by(
                WorkflowErrorModel.feed_id,
                WorkflowErrorModel.feed_url
            ).having(
                func.count(WorkflowErrorModel.id) >= min_errors
            ).order_by(
                func.count(WorkflowErrorModel.id).desc()
            ).all()

            return [
                {
                    'feed_id': r.feed_id,
                    'feed_url': r.feed_url,
                    'error_count': r.error_count,
                    'last_error': r.last_error
                }
                for r in results
            ]

    def get_by_run_id(self, run_id: str) -> List[WorkflowError]:
        """Get all errors for a specific workflow run."""
        with self.db.get_session() as session:
            models = session.query(WorkflowErrorModel).filter(
                WorkflowErrorModel.run_id == run_id
            ).order_by(WorkflowErrorModel.occurred_at.asc()).all()
            return [self._model_to_error(m) for m in models]

    def mark_resolved(self, error_id: int, resolution_notes: Optional[str] = None) -> bool:
        """Mark an error as resolved."""
        with self.db.get_session() as session:
            try:
                model = session.query(WorkflowErrorModel).filter(
                    WorkflowErrorModel.id == error_id
                ).first()
                if not model:
                    return False
                model.resolved = True
                model.resolved_at = datetime.now(timezone.utc)
                model.resolution_notes = resolution_notes
                model.updated_at = datetime.now(timezone.utc)
                session.commit()
                return True
            except SQLAlchemyError as exc:
                session.rollback()
                logger.error(f"Failed to mark error {error_id} as resolved: {exc}")
                raise

    def get_unresolved_errors(self, severity: Optional[str] = None,
                               limit: int = 100) -> List[WorkflowError]:
        """Get unresolved errors, optionally filtered by severity."""
        with self.db.get_session() as session:
            query = session.query(WorkflowErrorModel).filter(
                WorkflowErrorModel.resolved == False  # noqa: E712
            )
            if severity:
                query = query.filter(WorkflowErrorModel.severity == severity)
            models = query.order_by(
                WorkflowErrorModel.occurred_at.desc()
            ).limit(limit).all()
            return [self._model_to_error(m) for m in models]

    def get_error_trend(self, days_back: int = 14) -> List[Dict[str, Any]]:
        """Get daily error counts for trend analysis."""
        start_date = date.today() - timedelta(days=days_back)
        with self.db.get_session() as session:
            results = session.query(
                WorkflowErrorModel.error_date,
                WorkflowErrorModel.error_category,
                func.count(WorkflowErrorModel.id).label('count')
            ).filter(
                WorkflowErrorModel.error_date >= start_date
            ).group_by(
                WorkflowErrorModel.error_date,
                WorkflowErrorModel.error_category
            ).order_by(
                WorkflowErrorModel.error_date.asc()
            ).all()

            return [
                {
                    'date': r.error_date,
                    'category': r.error_category,
                    'count': r.count
                }
                for r in results
            ]

    def _model_to_error(self, model: WorkflowErrorModel) -> WorkflowError:
        """Convert SQLAlchemy model to dataclass."""
        return WorkflowError(
            id=model.id,
            error_date=model.error_date,
            occurred_at=model.occurred_at,
            run_id=model.run_id,
            workflow_run_id=model.workflow_run_id,
            error_category=model.error_category,
            phase=model.phase,
            severity=model.severity,
            feed_id=model.feed_id,
            feed_url=model.feed_url,
            error_code=model.error_code,
            error_message=model.error_message,
            error_summary=model.error_summary,
            extra=model.extra,
            source_log_id=model.source_log_id,
            resolved=model.resolved,
            resolved_at=model.resolved_at,
            resolution_notes=model.resolution_notes,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


def get_feed_repo(db_manager: DatabaseManager = None) -> FeedRepository:
    """Get feed repository.

    DEPRECATED: Use get_repo(FeedRepository) instead.
    """
    return get_repo(FeedRepository, db_manager)


def get_episode_repo(db_manager: DatabaseManager = None) -> EpisodeRepository:
    """Get episode repository.

    DEPRECATED: Use get_repo(EpisodeRepository) instead.
    """
    return get_repo(EpisodeRepository, db_manager)


def get_digest_repo(db_manager: DatabaseManager = None) -> DigestRepository:
    """Get digest repository.

    DEPRECATED: Use get_repo(DigestRepository) instead.
    """
    return get_repo(DigestRepository, db_manager)


def get_topic_repo(db_manager: DatabaseManager = None) -> TopicRepository:
    """Get topic repository.

    DEPRECATED: Use get_repo(TopicRepository) instead.
    """
    return get_repo(TopicRepository, db_manager)


def get_digest_episode_link_repo(db_manager: DatabaseManager = None) -> DigestEpisodeLinkRepository:
    """Get digest-episode link repository.

    DEPRECATED: Use get_repo(DigestEpisodeLinkRepository) instead.
    """
    return get_repo(DigestEpisodeLinkRepository, db_manager)


def get_pipeline_run_repo(db_manager: DatabaseManager = None) -> PipelineRunRepository:
    """Get pipeline run repository.

    DEPRECATED: Use get_repo(PipelineRunRepository) instead.
    """
    return get_repo(PipelineRunRepository, db_manager)


def get_pipeline_log_repo(db_manager: DatabaseManager = None) -> PipelineLogRepository:
    """Get pipeline log repository.

    DEPRECATED: Use get_repo(PipelineLogRepository) instead.
    """
    return get_repo(PipelineLogRepository, db_manager)


def get_workflow_error_repo(db_manager: DatabaseManager = None) -> WorkflowErrorRepository:
    """Get workflow error repository.

    DEPRECATED: Use get_repo(WorkflowErrorRepository) instead.
    """
    return get_repo(WorkflowErrorRepository, db_manager)
