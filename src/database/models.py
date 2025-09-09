"""
Database models and connection management for YouTube Transcript Digest System.
Provides SQLite database operations with proper error handling and connection pooling.
"""

import sqlite3
import json
import os
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Union
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class Channel:
    """YouTube Channel model"""
    channel_id: str
    channel_name: str
    channel_url: Optional[str] = None
    active: bool = True
    consecutive_failures: int = 0
    last_checked: Optional[datetime] = None
    last_video_date: Optional[datetime] = None
    total_videos_processed: int = 0
    total_videos_failed: int = 0
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass 
class Episode:
    """YouTube Episode/Video model"""
    video_id: str
    channel_id: str
    title: str
    published_date: datetime
    duration_seconds: Optional[int] = None
    description: Optional[str] = None
    transcript_path: Optional[str] = None
    transcript_fetched_at: Optional[datetime] = None
    transcript_word_count: Optional[int] = None
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
    """Topic-based digest model"""
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
    Manages SQLite database connections and operations.
    Provides connection pooling, error handling, and migration support.
    """
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_database_exists()
    
    def _ensure_database_exists(self):
        """Initialize database with schema if it doesn't exist"""
        try:
            with self.get_connection() as conn:
                # Read and execute schema
                schema_path = Path(__file__).parent / 'schema.sql'
                with open(schema_path, 'r') as f:
                    schema_sql = f.read()
                
                # Use executescript for better handling of multiple statements
                conn.executescript(schema_sql)
                logger.info(f"Database initialized at {self.db_path}")
                
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """Get database connection with proper error handling and cleanup"""
        conn = None
        try:
            conn = sqlite3.connect(
                self.db_path,
                timeout=30.0,
                check_same_thread=False
            )
            
            # Configure connection
            conn.row_factory = sqlite3.Row  # Enable column access by name
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")  # Better concurrency
            conn.execute("PRAGMA synchronous = NORMAL")  # Good balance of safety/speed
            
            yield conn
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def execute_query(self, query: str, params: tuple = ()) -> List[sqlite3.Row]:
        """Execute SELECT query and return results"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchall()
    
    def execute_update(self, query: str, params: tuple = ()) -> int:
        """Execute INSERT/UPDATE/DELETE query and return affected rows"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor.rowcount
    
    def get_last_insert_id(self, query: str, params: tuple = ()) -> int:
        """Execute INSERT and return the new row ID"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor.lastrowid

class ChannelRepository:
    """Repository for Channel database operations"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def create(self, channel: Channel) -> int:
        """Create new channel and return ID"""
        query = """
        INSERT INTO channels (channel_id, channel_name, channel_url, active)
        VALUES (?, ?, ?, ?)
        """
        return self.db.get_last_insert_id(
            query, 
            (channel.channel_id, channel.channel_name, channel.channel_url, channel.active)
        )
    
    def get_by_id(self, channel_id: str) -> Optional[Channel]:
        """Get channel by channel_id"""
        query = "SELECT * FROM channels WHERE channel_id = ?"
        rows = self.db.execute_query(query, (channel_id,))
        return self._row_to_channel(rows[0]) if rows else None
    
    def get_all_active(self) -> List[Channel]:
        """Get all active channels"""
        query = "SELECT * FROM channels WHERE active = 1 ORDER BY channel_name"
        rows = self.db.execute_query(query)
        return [self._row_to_channel(row) for row in rows]
    
    def update_last_checked(self, channel_id: str, last_checked: datetime = None):
        """Update last_checked timestamp"""
        if last_checked is None:
            last_checked = datetime.now()
        
        query = "UPDATE channels SET last_checked = ? WHERE channel_id = ?"
        self.db.execute_update(query, (last_checked.isoformat(), channel_id))
    
    def increment_failures(self, channel_id: str, failure_reason: str = None):
        """Increment failure count for channel health monitoring"""
        query = """
        UPDATE channels 
        SET consecutive_failures = consecutive_failures + 1,
            total_videos_failed = total_videos_failed + 1
        WHERE channel_id = ?
        """
        self.db.execute_update(query, (channel_id,))
    
    def reset_failures(self, channel_id: str):
        """Reset failure count after successful processing"""
        query = "UPDATE channels SET consecutive_failures = 0 WHERE channel_id = ?"
        self.db.execute_update(query, (channel_id,))
    
    def get_unhealthy_channels(self, failure_threshold: int = 3) -> List[Channel]:
        """Get channels with consecutive failures above threshold"""
        query = "SELECT * FROM channels WHERE consecutive_failures >= ? AND active = 1"
        rows = self.db.execute_query(query, (failure_threshold,))
        return [self._row_to_channel(row) for row in rows]
    
    def deactivate(self, channel_id: str):
        """Deactivate a channel"""
        query = "UPDATE channels SET active = 0 WHERE channel_id = ?"
        self.db.execute_update(query, (channel_id,))
    
    def delete(self, channel_id: str):
        """Delete channel and all associated episodes"""
        query = "DELETE FROM channels WHERE channel_id = ?"
        return self.db.execute_update(query, (channel_id,))
    
    def _row_to_channel(self, row: sqlite3.Row) -> Channel:
        """Convert database row to Channel object"""
        return Channel(
            id=row['id'],
            channel_id=row['channel_id'],
            channel_name=row['channel_name'],
            channel_url=row['channel_url'],
            active=bool(row['active']),
            consecutive_failures=row['consecutive_failures'],
            last_checked=datetime.fromisoformat(row['last_checked']) if row['last_checked'] else None,
            last_video_date=datetime.fromisoformat(row['last_video_date']) if row['last_video_date'] else None,
            total_videos_processed=row['total_videos_processed'],
            total_videos_failed=row['total_videos_failed'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
        )

class EpisodeRepository:
    """Repository for Episode database operations"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def create(self, episode: Episode) -> int:
        """Create new episode and return ID"""
        query = """
        INSERT INTO episodes (
            video_id, channel_id, title, published_date, duration_seconds, description
        ) VALUES (?, ?, ?, ?, ?, ?)
        """
        return self.db.get_last_insert_id(
            query, 
            (episode.video_id, episode.channel_id, episode.title, 
             episode.published_date.isoformat(), episode.duration_seconds, episode.description)
        )
    
    def get_by_video_id(self, video_id: str) -> Optional[Episode]:
        """Get episode by video_id"""
        query = "SELECT * FROM episodes WHERE video_id = ?"
        rows = self.db.execute_query(query, (video_id,))
        return self._row_to_episode(rows[0]) if rows else None
    
    def get_by_status(self, status: str) -> List[Episode]:
        """Get all episodes with specific status"""
        query = "SELECT * FROM episodes WHERE status = ? ORDER BY published_date DESC"
        rows = self.db.execute_query(query, (status,))
        return [self._row_to_episode(row) for row in rows]
    
    def get_scored_episodes_for_topic(self, topic: str, min_score: float = 0.65, 
                                    start_date: date = None, end_date: date = None) -> List[Episode]:
        """Get episodes scored above threshold for specific topic"""
        query = """
        SELECT * FROM episodes 
        WHERE status = 'scored' 
        AND scores IS NOT NULL
        AND json_extract(scores, '$." + topic + "') >= ?
        """
        params = [min_score]
        
        if start_date:
            query += " AND date(published_date) >= ?"
            params.append(start_date.isoformat())
        
        if end_date:
            query += " AND date(published_date) <= ?"
            params.append(end_date.isoformat())
        
        query += " ORDER BY json_extract(scores, '$." + topic + "') DESC, published_date DESC"
        
        rows = self.db.execute_query(query, tuple(params))
        return [self._row_to_episode(row) for row in rows]
    
    def update_status(self, video_id: str, status: str):
        """Update episode status"""
        query = "UPDATE episodes SET status = ? WHERE video_id = ?"
        self.db.execute_update(query, (status, video_id))
    
    def update_transcript(self, video_id: str, transcript_path: str, word_count: int):
        """Update transcript information"""
        query = """
        UPDATE episodes 
        SET transcript_path = ?, transcript_fetched_at = ?, transcript_word_count = ?, status = 'transcribed'
        WHERE video_id = ?
        """
        self.db.execute_update(query, (transcript_path, datetime.now().isoformat(), word_count, video_id))
    
    def update_scores(self, video_id: str, scores: Dict[str, float]):
        """Update AI scores for episode"""
        query = """
        UPDATE episodes 
        SET scores = ?, scored_at = ?, status = 'scored'
        WHERE video_id = ?
        """
        self.db.execute_update(query, (json.dumps(scores), datetime.now().isoformat(), video_id))
    
    def mark_failure(self, video_id: str, failure_reason: str):
        """Mark episode as failed and increment failure count"""
        query = """
        UPDATE episodes 
        SET failure_count = failure_count + 1, 
            failure_reason = ?, 
            last_failure_at = ?,
            status = CASE WHEN failure_count >= 2 THEN 'failed' ELSE status END
        WHERE video_id = ?
        """
        self.db.execute_update(query, (failure_reason, datetime.now().isoformat(), video_id))
    
    def cleanup_old_episodes(self, days_old: int = 14):
        """Delete episodes older than specified days"""
        query = "DELETE FROM episodes WHERE published_date < date('now', '-' || ? || ' days')"
        return self.db.execute_update(query, (days_old,))
    
    def _row_to_episode(self, row: sqlite3.Row) -> Episode:
        """Convert database row to Episode object"""
        scores = json.loads(row['scores']) if row['scores'] else None
        
        return Episode(
            id=row['id'],
            video_id=row['video_id'],
            channel_id=row['channel_id'],
            title=row['title'],
            published_date=datetime.fromisoformat(row['published_date']),
            duration_seconds=row['duration_seconds'],
            description=row['description'],
            transcript_path=row['transcript_path'],
            transcript_fetched_at=datetime.fromisoformat(row['transcript_fetched_at']) if row['transcript_fetched_at'] else None,
            transcript_word_count=row['transcript_word_count'],
            scores=scores,
            scored_at=datetime.fromisoformat(row['scored_at']) if row['scored_at'] else None,
            status=row['status'],
            failure_count=row['failure_count'],
            failure_reason=row['failure_reason'],
            last_failure_at=datetime.fromisoformat(row['last_failure_at']) if row['last_failure_at'] else None,
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
        )

class DigestRepository:
    """Repository for Digest database operations"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def create(self, digest: Digest) -> int:
        """Create new digest and return ID"""
        query = """
        INSERT INTO digests (topic, digest_date, episode_ids, episode_count)
        VALUES (?, ?, ?, ?)
        """
        episode_ids_json = json.dumps(digest.episode_ids) if digest.episode_ids else None
        return self.db.get_last_insert_id(
            query, 
            (digest.topic, digest.digest_date.isoformat(), episode_ids_json, digest.episode_count)
        )
    
    def get_by_topic_date(self, topic: str, digest_date: date) -> Optional[Digest]:
        """Get digest by topic and date"""
        query = "SELECT * FROM digests WHERE topic = ? AND digest_date = ?"
        rows = self.db.execute_query(query, (topic, digest_date.isoformat()))
        return self._row_to_digest(rows[0]) if rows else None
    
    def update_script(self, digest_id: int, script_path: str, word_count: int):
        """Update script information"""
        query = "UPDATE digests SET script_path = ?, script_word_count = ? WHERE id = ?"
        self.db.execute_update(query, (script_path, word_count, digest_id))
    
    def update_audio(self, digest_id: int, mp3_path: str, duration_seconds: int, 
                    title: str, summary: str):
        """Update audio information"""
        query = """
        UPDATE digests 
        SET mp3_path = ?, mp3_duration_seconds = ?, mp3_title = ?, mp3_summary = ?
        WHERE id = ?
        """
        self.db.execute_update(query, (mp3_path, duration_seconds, title, summary, digest_id))
    
    def update_published(self, digest_id: int, github_url: str):
        """Update publishing information"""
        query = "UPDATE digests SET github_url = ?, published_at = ? WHERE id = ?"
        self.db.execute_update(query, (github_url, datetime.now().isoformat(), digest_id))
    
    def get_recent_digests(self, days: int = 7) -> List[Digest]:
        """Get recent digests for RSS feed generation"""
        query = """
        SELECT * FROM digests 
        WHERE digest_date >= date('now', '-' || ? || ' days')
        AND mp3_path IS NOT NULL
        ORDER BY digest_date DESC, topic
        """
        rows = self.db.execute_query(query, (days,))
        return [self._row_to_digest(row) for row in rows]
    
    def cleanup_old_digests(self, days_old: int = 14):
        """Delete digests older than specified days"""
        query = "DELETE FROM digests WHERE digest_date < date('now', '-' || ? || ' days')"
        return self.db.execute_update(query, (days_old,))
    
    def _row_to_digest(self, row: sqlite3.Row) -> Digest:
        """Convert database row to Digest object"""
        episode_ids = json.loads(row['episode_ids']) if row['episode_ids'] else None
        
        return Digest(
            id=row['id'],
            topic=row['topic'],
            digest_date=date.fromisoformat(row['digest_date']),
            script_path=row['script_path'],
            script_word_count=row['script_word_count'],
            mp3_path=row['mp3_path'],
            mp3_duration_seconds=row['mp3_duration_seconds'],
            mp3_title=row['mp3_title'],
            mp3_summary=row['mp3_summary'],
            episode_ids=episode_ids,
            episode_count=row['episode_count'],
            average_score=row['average_score'],
            github_url=row['github_url'],
            published_at=datetime.fromisoformat(row['published_at']) if row['published_at'] else None,
            generated_at=datetime.fromisoformat(row['generated_at']) if row['generated_at'] else None
        )

def get_database_manager(db_path: str = None) -> DatabaseManager:
    """Factory function to get database manager with default path"""
    if db_path is None:
        # Default to data/database/digest.db relative to project root
        project_root = Path(__file__).parent.parent.parent
        db_path = project_root / 'data' / 'database' / 'digest.db'
    
    return DatabaseManager(str(db_path))

# Repository factory functions
def get_channel_repo(db_manager: DatabaseManager = None) -> ChannelRepository:
    """Get channel repository"""
    if db_manager is None:
        db_manager = get_database_manager()
    return ChannelRepository(db_manager)

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