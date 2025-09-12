#!/usr/bin/env python3
"""
RSS Podcast Feed Models
Database models for RSS podcast feeds, episodes, and transcription tracking.
"""

import sqlite3
import json
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from ..database.models import DatabaseManager
from ..utils.logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class PodcastFeed:
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
class PodcastEpisode:
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

class PodcastFeedRepository:
    """Repository for RSS Podcast Feed database operations"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def create(self, feed: PodcastFeed) -> int:
        """Create new feed and return ID"""
        query = """
        INSERT INTO feeds (feed_url, title, description, active)
        VALUES (?, ?, ?, ?)
        """
        return self.db.get_last_insert_id(
            query, 
            (feed.feed_url, feed.title, feed.description, feed.active)
        )
    
    def get_by_url(self, feed_url: str) -> Optional[PodcastFeed]:
        """Get feed by URL"""
        query = "SELECT * FROM feeds WHERE feed_url = ?"
        rows = self.db.execute_query(query, (feed_url,))
        return self._row_to_feed(rows[0]) if rows else None
    
    def get_by_id(self, feed_id: int) -> Optional[PodcastFeed]:
        """Get feed by ID"""
        query = "SELECT * FROM feeds WHERE id = ?"
        rows = self.db.execute_query(query, (feed_id,))
        return self._row_to_feed(rows[0]) if rows else None
    
    def get_all_active(self) -> List[PodcastFeed]:
        """Get all active feeds"""
        query = "SELECT * FROM feeds WHERE active = 1 ORDER BY title"
        rows = self.db.execute_query(query)
        return [self._row_to_feed(row) for row in rows]
    
    def update_last_checked(self, feed_id: int, last_checked: datetime = None):
        """Update last_checked timestamp"""
        if last_checked is None:
            last_checked = datetime.now()
        
        query = "UPDATE feeds SET last_checked = ? WHERE id = ?"
        self.db.execute_update(query, (last_checked.isoformat(), feed_id))
    
    def increment_failures(self, feed_id: int):
        """Increment failure count for feed health monitoring"""
        query = """
        UPDATE feeds 
        SET consecutive_failures = consecutive_failures + 1,
            total_episodes_failed = total_episodes_failed + 1
        WHERE id = ?
        """
        self.db.execute_update(query, (feed_id,))
    
    def reset_failures(self, feed_id: int):
        """Reset failure count after successful processing"""
        query = "UPDATE feeds SET consecutive_failures = 0 WHERE id = ?"
        self.db.execute_update(query, (feed_id,))
    
    def deactivate(self, feed_id: int):
        """Deactivate a feed"""
        query = "UPDATE feeds SET active = 0 WHERE id = ?"
        self.db.execute_update(query, (feed_id,))
    
    def delete(self, feed_id: int):
        """Delete feed and all associated episodes"""
        query = "DELETE FROM feeds WHERE id = ?"
        return self.db.execute_update(query, (feed_id,))
    
    def _row_to_feed(self, row: sqlite3.Row) -> PodcastFeed:
        """Convert database row to PodcastFeed object"""
        return PodcastFeed(
            id=row['id'],
            feed_url=row['feed_url'],
            title=row['title'],
            description=row['description'],
            active=bool(row['active']),
            consecutive_failures=row['consecutive_failures'],
            last_checked=datetime.fromisoformat(row['last_checked']) if row['last_checked'] else None,
            last_episode_date=datetime.fromisoformat(row['last_episode_date']) if row['last_episode_date'] else None,
            total_episodes_processed=row['total_episodes_processed'],
            total_episodes_failed=row['total_episodes_failed'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
        )

class PodcastEpisodeRepository:
    """Repository for RSS Podcast Episode database operations"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def create(self, episode: PodcastEpisode) -> int:
        """Create new episode and return ID"""
        query = """
        INSERT INTO episodes (
            episode_guid, feed_id, title, published_date, duration_seconds, 
            description, audio_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        return self.db.get_last_insert_id(
            query, 
            (episode.episode_guid, episode.feed_id, episode.title, 
             episode.published_date.isoformat(), episode.duration_seconds, 
             episode.description, episode.audio_url)
        )
    
    def get_by_guid(self, episode_guid: str) -> Optional[PodcastEpisode]:
        """Get episode by GUID"""
        query = "SELECT * FROM episodes WHERE episode_guid = ?"
        rows = self.db.execute_query(query, (episode_guid,))
        return self._row_to_episode(rows[0]) if rows else None
    
    def get_by_status(self, status: str) -> List[PodcastEpisode]:
        """Get all episodes with specific status"""
        query = "SELECT * FROM episodes WHERE status = ? ORDER BY published_date DESC"
        rows = self.db.execute_query(query, (status,))
        return [self._row_to_episode(row) for row in rows]
    
    def get_by_feed_id(self, feed_id: int, limit: int = None) -> List[PodcastEpisode]:
        """Get episodes for a specific feed"""
        query = "SELECT * FROM episodes WHERE feed_id = ? ORDER BY published_date DESC"
        if limit:
            query += f" LIMIT {limit}"
        rows = self.db.execute_query(query, (feed_id,))
        return [self._row_to_episode(row) for row in rows]

    def get_scored_episodes_for_topic(self, topic: str, min_score: float = 0.65,
                                      start_date: date = None, end_date: date = None) -> List[PodcastEpisode]:
        """Get episodes scored above threshold for a specific topic (RSS pipeline).

        Uses SQLite JSON extraction on the scores JSON column.
        """
        json_path = f'$."{topic}"'
        query = (
            "SELECT * FROM episodes "
            "WHERE status = 'scored' "
            "AND scores IS NOT NULL "
            "AND json_extract(scores, ?) >= ?"
        )
        params: List[Any] = [json_path, min_score]
        if start_date:
            query += " AND date(published_date) >= ?"
            params.append(start_date.isoformat())
        if end_date:
            query += " AND date(published_date) <= ?"
            params.append(end_date.isoformat())
        query += " ORDER BY json_extract(scores, ?) DESC, published_date DESC"
        params.append(json_path)
        rows = self.db.execute_query(query, tuple(params))
        return [self._row_to_episode(row) for row in rows]
    
    def update_status(self, episode_guid: str, status: str):
        """Update episode status"""
        query = "UPDATE episodes SET status = ? WHERE episode_guid = ?"
        self.db.execute_update(query, (status, episode_guid))
    
    def update_audio_path(self, episode_guid: str, audio_path: str):
        """Update audio file path"""
        query = """
        UPDATE episodes 
        SET audio_path = ?, audio_downloaded_at = ?, status = 'downloading'
        WHERE episode_guid = ?
        """
        self.db.execute_update(query, (audio_path, datetime.now().isoformat(), episode_guid))
    
    def update_transcript(self, episode_guid: str, transcript_path: str, word_count: int, chunk_count: int = 0):
        """Update transcript information"""
        query = """
        UPDATE episodes 
        SET transcript_path = ?, transcript_generated_at = ?, transcript_word_count = ?, 
            chunk_count = ?, status = 'transcribed'
        WHERE episode_guid = ?
        """
        self.db.execute_update(query, (transcript_path, datetime.now().isoformat(), 
                                     word_count, chunk_count, episode_guid))
    
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
    
    def get_recent_episodes(self, days: int = 7) -> List[PodcastEpisode]:
        """Get episodes from recent days"""
        query = """
        SELECT * FROM episodes 
        WHERE published_date > date('now', '-' || ? || ' days')
        ORDER BY published_date DESC
        """
        rows = self.db.execute_query(query, (days,))
        return [self._row_to_episode(row) for row in rows]
    
    def cleanup_old_episodes(self, days_old: int = 14):
        """Delete episodes older than specified days"""
        query = "DELETE FROM episodes WHERE published_date < date('now', '-' || ? || ' days')"
        return self.db.execute_update(query, (days_old,))
    
    def _row_to_episode(self, row: sqlite3.Row) -> PodcastEpisode:
        """Convert database row to PodcastEpisode object"""
        scores = json.loads(row['scores']) if row['scores'] else None
        
        return PodcastEpisode(
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

# Factory functions
def get_feed_repo(db_manager: DatabaseManager = None) -> PodcastFeedRepository:
    """Get podcast feed repository"""
    if db_manager is None:
        from ..database.models import get_database_manager
        db_manager = get_database_manager()
    return PodcastFeedRepository(db_manager)

def get_podcast_episode_repo(db_manager: DatabaseManager = None) -> PodcastEpisodeRepository:
    """Get podcast episode repository"""
    if db_manager is None:
        from ..database.models import get_database_manager
        db_manager = get_database_manager()
    return PodcastEpisodeRepository(db_manager)
