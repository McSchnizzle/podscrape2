"""
Database models and connection management for RSS Podcast Transcript Digest System.
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
class Feed:
    """RSS Podcast Feed model"""
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
    """RSS Podcast Episode model"""
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

# FeedRepository temporarily commented out for Phase 4 focus on Episodes
# Will implement complete RSS feed management in later phases

class EpisodeRepository:
    """Repository for Episode database operations"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def create(self, episode: Episode) -> int:
        """Create new episode and return ID"""
        query = """
        INSERT INTO episodes (
            episode_guid, feed_id, title, published_date, audio_url, duration_seconds, description
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        return self.db.get_last_insert_id(
            query, 
            (episode.episode_guid, episode.feed_id, episode.title, 
             episode.published_date.isoformat(), episode.audio_url, episode.duration_seconds, episode.description)
        )
    
    def get_by_episode_guid(self, episode_guid: str) -> Optional[Episode]:
        """Get episode by episode_guid"""
        query = "SELECT * FROM episodes WHERE episode_guid = ?"
        rows = self.db.execute_query(query, (episode_guid,))
        return self._row_to_episode(rows[0]) if rows else None
    
    def get_by_status(self, status: str) -> List[Episode]:
        """Get all episodes with specific status"""
        query = "SELECT * FROM episodes WHERE status = ? ORDER BY published_date DESC"
        rows = self.db.execute_query(query, (status,))
        return [self._row_to_episode(row) for row in rows]
    
    def get_scored_episodes_for_topic(self, topic: str, min_score: float = 0.65, 
                                    start_date: date = None, end_date: date = None) -> List[Episode]:
        """Get episodes scored above threshold for specific topic"""
        # Build JSON path for SQLite json_extract
        json_path = f'$."{topic}"'
        
        query = f"""
        SELECT * FROM episodes 
        WHERE status IN ('scored', 'digested') 
        AND scores IS NOT NULL
        AND json_extract(scores, ?) >= ?
        """
        params = [json_path, min_score]
        
        if start_date:
            query += " AND date(published_date) >= ?"
            params.append(start_date.isoformat())
        
        if end_date:
            query += " AND date(published_date) <= ?"
            params.append(end_date.isoformat())
        
        query += f" ORDER BY json_extract(scores, ?) DESC, published_date DESC"
        params.append(json_path)
        
        rows = self.db.execute_query(query, tuple(params))
        return [self._row_to_episode(row) for row in rows]
    
    def update_status(self, episode_guid: str, status: str):
        """Update episode status"""
        query = "UPDATE episodes SET status = ? WHERE episode_guid = ?"
        self.db.execute_update(query, (status, episode_guid))
    
    def update_transcript(self, episode_guid: str, transcript_path: str, word_count: int):
        """Update transcript information"""
        query = """
        UPDATE episodes 
        SET transcript_path = ?, transcript_generated_at = ?, transcript_word_count = ?, status = 'transcribed'
        WHERE episode_guid = ?
        """
        self.db.execute_update(query, (transcript_path, datetime.now().isoformat(), word_count, episode_guid))
    
    def update_scores(self, episode_guid: str, scores: Dict[str, float]):
        """Update AI scores for episode"""
        query = """
        UPDATE episodes 
        SET scores = ?, scored_at = ?, status = 'scored'
        WHERE episode_guid = ?
        """
        self.db.execute_update(query, (json.dumps(scores), datetime.now().isoformat(), episode_guid))
    
    def mark_failure(self, episode_guid: str, failure_reason: str):
        """Mark episode as failed and increment failure count"""
        query = """
        UPDATE episodes 
        SET failure_count = failure_count + 1, 
            failure_reason = ?, 
            last_failure_at = ?,
            status = CASE WHEN failure_count >= 2 THEN 'failed' ELSE status END
        WHERE episode_guid = ?
        """
        self.db.execute_update(query, (failure_reason, datetime.now().isoformat(), episode_guid))
    
    def cleanup_old_episodes(self, days_old: int = 14):
        """Delete episodes older than specified days"""
        query = "DELETE FROM episodes WHERE published_date < date('now', '-' || ? || ' days')"
        return self.db.execute_update(query, (days_old,))
    
    def get_undigested_episodes(self, start_date: date = None, end_date: date = None, 
                               limit: int = 5) -> List[Episode]:
        """Get episodes that haven't been used in digests"""
        query = """
        SELECT * FROM episodes 
        WHERE status != 'digested'
        AND status NOT IN ('pending', 'failed') 
        """
        params = []
        
        if start_date:
            query += " AND date(published_date) >= ?"
            params.append(start_date.isoformat())
        
        if end_date:
            query += " AND date(published_date) <= ?"
            params.append(end_date.isoformat())
        
        query += " ORDER BY published_date DESC LIMIT ?"
        params.append(limit)
        
        rows = self.db.execute_query(query, tuple(params))
        return [self._row_to_episode(row) for row in rows]
    
    def update_status_by_id(self, episode_id: int, status: str):
        """Update episode status by ID"""
        query = "UPDATE episodes SET status = ? WHERE id = ?"
        self.db.execute_update(query, (status, episode_id))
    
    def update_transcript_path(self, episode_id: int, transcript_path: str):
        """Update transcript path by ID"""
        query = "UPDATE episodes SET transcript_path = ? WHERE id = ?"
        self.db.execute_update(query, (transcript_path, episode_id))
    
    def get_by_id(self, episode_id: int) -> Optional[Episode]:
        """Get episode by ID"""
        query = "SELECT * FROM episodes WHERE id = ?"
        rows = self.db.execute_query(query, (episode_id,))
        return self._row_to_episode(rows[0]) if rows else None
    
    def _row_to_episode(self, row: sqlite3.Row) -> Episode:
        """Convert database row to Episode object"""
        scores = json.loads(row['scores']) if row['scores'] else None
        
        return Episode(
            id=row['id'],
            episode_guid=row['episode_guid'],
            feed_id=row['feed_id'],
            title=row['title'],
            published_date=datetime.fromisoformat(row['published_date']),
            audio_url=row['audio_url'],
            duration_seconds=row['duration_seconds'],
            description=row['description'],
            audio_path=row['audio_path'],
            audio_downloaded_at=datetime.fromisoformat(row['audio_downloaded_at']) if row['audio_downloaded_at'] else None,
            transcript_path=row['transcript_path'],
            transcript_generated_at=datetime.fromisoformat(row['transcript_generated_at']) if row['transcript_generated_at'] else None,
            transcript_word_count=row['transcript_word_count'],
            chunk_count=row['chunk_count'],
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
    
    def get_by_date(self, digest_date: date) -> List[Digest]:
        """Get all digests for a specific date"""
        query = "SELECT * FROM digests WHERE digest_date = ?"
        rows = self.db.execute_query(query, (digest_date.isoformat(),))
        return [self._row_to_digest(row) for row in rows]
    
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
# get_feed_repo temporarily commented out for Phase 4

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