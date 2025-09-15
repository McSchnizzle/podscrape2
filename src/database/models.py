"""
SQLAlchemy-based database models and repositories for RSS Podcast Transcript Digest System.
Migration from SQLite to PostgreSQL with comprehensive repository pattern.
"""

import json
import logging
from datetime import datetime, date, timedelta, UTC
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from .sqlalchemy_models import Base, Feed as FeedModel, Episode as EpisodeModel, Digest as DigestModel
from src.config.env import require_database_url

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
    transcript_generated_at: Optional[datetime] = None
    transcript_word_count: Optional[int] = None
    chunk_count: int = 0
    scores: Optional[Dict[str, float]] = None
    scored_at: Optional[datetime] = None
    status: str = 'pending'
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
    script_path: Optional[str] = None
    script_word_count: Optional[int] = None
    mp3_path: Optional[str] = None
    mp3_duration_seconds: Optional[int] = None
    mp3_title: Optional[str] = None
    mp3_summary: Optional[str] = None
    episode_ids: Optional[List[int]] = None
    episode_count: int = 0
    average_score: Optional[float] = None
    github_url: Optional[str] = None
    published_at: Optional[datetime] = None
    id: Optional[int] = None
    generated_at: Optional[datetime] = None

class DatabaseManager:
    """
    SQLAlchemy-based database manager for PostgreSQL.
    Provides session management, connection pooling, and transaction support.
    """

    def __init__(self, database_url: str = None):
        self.database_url = database_url or require_database_url()
        self.engine = create_engine(
            self.database_url,
            pool_pre_ping=True,
            pool_recycle=300,
            echo=False  # Set to True for SQL debugging
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        logger.info(f"Database manager initialized with PostgreSQL")

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
                    feed_model.updated_at = datetime.now(UTC)
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
                    feed_model.updated_at = datetime.now(UTC)
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
                    feed_model.updated_at = datetime.now(UTC)
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
                    feed_model.updated_at = datetime.now(UTC)
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
                    feed_model.updated_at = datetime.now(UTC)
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

    def get_scored_episodes_for_topic(self, topic: str, min_score: float = 0.65,
                                    start_date: date = None, end_date: date = None) -> List[Episode]:
        """Get episodes scored above threshold for specific topic"""
        with self.db.get_session() as session:
            # Use database-agnostic JSON filtering
            query = session.query(EpisodeModel)\
                .filter(EpisodeModel.status == 'scored')\
                .filter(EpisodeModel.scores.isnot(None))

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
                    episode_model.updated_at = datetime.now(UTC)
                    session.commit()
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to update episode status {episode_guid}: {e}")
                raise

    def update_transcript(self, episode_guid: str, transcript_path: str, word_count: int):
        """Update transcript information"""
        with self.db.get_session() as session:
            try:
                episode_model = session.query(EpisodeModel)\
                    .filter(EpisodeModel.episode_guid == episode_guid).first()
                if episode_model:
                    episode_model.transcript_path = transcript_path
                    episode_model.transcript_generated_at = datetime.now(UTC)
                    episode_model.transcript_word_count = word_count
                    episode_model.status = 'transcribed'
                    episode_model.updated_at = datetime.now(UTC)
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
                    episode_model.scored_at = datetime.now(UTC)
                    episode_model.status = 'scored'
                    episode_model.updated_at = datetime.now(UTC)
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
                    episode_model.last_failure_at = datetime.now(UTC)
                    if episode_model.failure_count >= 3:
                        episode_model.status = 'failed'
                    episode_model.updated_at = datetime.now(UTC)
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

    def get_failed_episodes(self) -> List[Episode]:
        """Get episodes that have failed processing"""
        with self.db.get_session() as session:
            episode_models = session.query(EpisodeModel)\
                .filter(EpisodeModel.status == 'failed')\
                .order_by(EpisodeModel.last_failure_at.desc())\
                .all()
            return [self._model_to_episode(model) for model in episode_models]

    def cleanup_old_episodes(self, days_old: int = 14):
        """Delete episodes older than specified days"""
        with self.db.get_session() as session:
            try:
                cutoff_date = datetime.now(UTC) - timedelta(days=days_old)
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
                    episode_model.updated_at = datetime.now(UTC)
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
                    episode_model.updated_at = datetime.now(UTC)
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
                    episode_model.updated_at = datetime.now(UTC)
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
        """Create new digest and return ID"""
        with self.db.get_session() as session:
            try:
                digest_model = DigestModel(
                    topic=digest.topic,
                    digest_date=digest.digest_date,
                    episode_ids=digest.episode_ids,
                    episode_count=digest.episode_count,
                    script_path=digest.script_path,
                    script_word_count=digest.script_word_count,
                    mp3_path=digest.mp3_path,
                    mp3_duration_seconds=digest.mp3_duration_seconds,
                    mp3_title=digest.mp3_title,
                    mp3_summary=digest.mp3_summary,
                    average_score=digest.average_score,
                    github_url=digest.github_url,
                    published_at=digest.published_at
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

    def update_script(self, digest_id: int, script_path: str, word_count: int):
        """Update script information"""
        with self.db.get_session() as session:
            try:
                digest_model = session.query(DigestModel).filter(DigestModel.id == digest_id).first()
                if digest_model:
                    digest_model.script_path = script_path
                    digest_model.script_word_count = word_count
                    session.commit()
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to update script for digest {digest_id}: {e}")
                raise

    def update_audio(self, digest_id: int, mp3_path: str, duration_seconds: int,
                    title: str, summary: str):
        """Update audio information"""
        with self.db.get_session() as session:
            try:
                digest_model = session.query(DigestModel).filter(DigestModel.id == digest_id).first()
                if digest_model:
                    digest_model.mp3_path = mp3_path
                    digest_model.mp3_duration_seconds = duration_seconds
                    digest_model.mp3_title = title
                    digest_model.mp3_summary = summary
                    session.commit()
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to update audio for digest {digest_id}: {e}")
                raise

    def update_published(self, digest_id: int, github_url: str):
        """Update publishing information"""
        with self.db.get_session() as session:
            try:
                digest_model = session.query(DigestModel).filter(DigestModel.id == digest_id).first()
                if digest_model:
                    digest_model.github_url = github_url
                    digest_model.published_at = datetime.now(UTC)
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

    def _model_to_digest(self, model: DigestModel) -> Digest:
        """Convert SQLAlchemy model to dataclass"""
        return Digest(
            id=model.id,
            topic=model.topic,
            digest_date=model.digest_date,
            script_path=model.script_path,
            script_word_count=model.script_word_count,
            mp3_path=model.mp3_path,
            mp3_duration_seconds=model.mp3_duration_seconds,
            mp3_title=model.mp3_title,
            mp3_summary=model.mp3_summary,
            episode_ids=model.episode_ids,
            episode_count=model.episode_count,
            average_score=model.average_score,
            github_url=model.github_url,
            published_at=model.published_at,
            generated_at=model.generated_at
        )

def get_database_manager() -> DatabaseManager:
    """Factory function to get database manager"""
    return DatabaseManager()

def get_feed_repo(db_manager: DatabaseManager = None) -> FeedRepository:
    """Get feed repository"""
    if db_manager is None:
        db_manager = get_database_manager()
    return FeedRepository(db_manager)

def get_episode_repo(db_manager: DatabaseManager = None) -> EpisodeRepository:
    """Get episode repository"""
    if db_manager is None:
        db_manager = get_database_manager()
    return EpisodeRepository(db_manager)

def get_digest_repo(db_manager: DatabaseManager = None) -> DigestRepository:
    """Get digest repository"""
    if db_manager is None:
        db_manager = get_database_manager()
    return DigestRepository(db_manager)