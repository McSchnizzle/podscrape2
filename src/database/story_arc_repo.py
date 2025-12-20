"""
StoryArcRepository: Data access for story_arcs and story_arc_events tables.
Manages story arc creation, event tracking, and timeline management.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from src.database.sqlalchemy_models import StoryArc, StoryArcEvent, Feed
from src.database.models import get_database_manager


class StoryArcRepository:
    """Repository for story_arcs and story_arc_events table operations"""

    def __init__(self):
        self.db_manager = get_database_manager()

    def create_story_arc(
        self,
        arc_name: str,
        digest_topic: str,
        functional_category: str = 'other',
        initial_event: Optional[Dict] = None
    ) -> Dict:
        """
        Create a new story arc with optional initial event.

        Args:
            arc_name: Human-readable arc name
            digest_topic: Parent topic (e.g., "AI and Technology")
            functional_category: Category (model_release, company_strategy, etc.)
            initial_event: Optional dict with event details

        Returns:
            Dict representation of created arc
        """
        arc_slug = self._normalize_arc_name(arc_name)
        now = datetime.now(timezone.utc)

        with self.db_manager.get_session() as session:
            # Check if arc already exists
            existing = session.query(StoryArc).filter(
                StoryArc.arc_slug == arc_slug
            ).first()

            if existing:
                return self._arc_to_dict(existing)

            # Create new arc
            new_arc = StoryArc(
                arc_name=arc_name,
                arc_slug=arc_slug,
                functional_category=functional_category,
                digest_topic=digest_topic,
                started_at=now,
                last_updated_at=now,
                event_count=0,
                source_count=0,
            )
            session.add(new_arc)
            session.flush()  # Get the ID

            # Add initial event if provided
            if initial_event:
                event = StoryArcEvent(
                    story_arc_id=new_arc.id,
                    event_date=initial_event.get('event_date', now),
                    event_summary=initial_event.get('event_summary', ''),
                    key_points=initial_event.get('key_points', []),
                    source_feed_id=initial_event.get('source_feed_id'),
                    source_episode_id=initial_event.get('source_episode_id'),
                    source_episode_guid=initial_event.get('source_episode_guid'),
                    source_name=initial_event.get('source_name'),
                    perspective=initial_event.get('perspective'),
                    relevance_score=initial_event.get('relevance_score'),
                    extracted_at=now,
                )
                session.add(event)
                new_arc.event_count = 1
                new_arc.source_count = 1

            session.commit()
            session.refresh(new_arc)
            return self._arc_to_dict(new_arc)

    def get_or_create_story_arc(
        self,
        arc_name: str,
        digest_topic: str,
        functional_category: str = 'other'
    ) -> Dict:
        """
        Find existing arc by slug or create new one.

        Args:
            arc_name: Arc name to find or create
            digest_topic: Parent topic
            functional_category: Category for new arcs

        Returns:
            Dict representation of arc
        """
        arc_slug = self._normalize_arc_name(arc_name)

        with self.db_manager.get_session() as session:
            existing = session.query(StoryArc).filter(
                StoryArc.arc_slug == arc_slug
            ).first()

            if existing:
                return self._arc_to_dict(existing)

        # Create new arc if not found
        return self.create_story_arc(
            arc_name=arc_name,
            digest_topic=digest_topic,
            functional_category=functional_category
        )

    def add_story_arc_event(
        self,
        story_arc_id: int,
        event_date: datetime,
        event_summary: str,
        key_points: List[str],
        source_feed_id: Optional[int],
        source_episode_id: Optional[int],
        source_episode_guid: Optional[str],
        source_name: Optional[str],
        perspective: Optional[str],
        relevance_score: Optional[float]
    ) -> Dict:
        """
        Add a new event to an existing story arc.

        Args:
            story_arc_id: ID of the arc to add event to
            event_date: When the event occurred
            event_summary: 1-2 sentence summary
            key_points: List of key details
            source_feed_id: Feed ID
            source_episode_id: Episode ID
            source_episode_guid: Episode GUID
            source_name: Source name (e.g., podcast title)
            perspective: positive, negative, neutral, analytical
            relevance_score: Episode relevance score

        Returns:
            Dict representation of created event
        """
        now = datetime.now(timezone.utc)

        with self.db_manager.get_session() as session:
            # Get the arc
            arc = session.query(StoryArc).filter(
                StoryArc.id == story_arc_id
            ).first()

            if not arc:
                raise ValueError(f"Story arc not found: {story_arc_id}")

            # Create the event
            event = StoryArcEvent(
                story_arc_id=story_arc_id,
                event_date=event_date,
                event_summary=event_summary,
                key_points=key_points or [],
                source_feed_id=source_feed_id,
                source_episode_id=source_episode_id,
                source_episode_guid=source_episode_guid,
                source_name=source_name,
                perspective=perspective,
                relevance_score=relevance_score,
                extracted_at=now,
            )
            session.add(event)

            # Update arc metadata
            arc.event_count += 1
            arc.last_updated_at = now
            arc.updated_at = now

            # Count unique sources
            unique_feeds = session.query(func.count(func.distinct(StoryArcEvent.source_feed_id))).filter(
                StoryArcEvent.story_arc_id == story_arc_id,
                StoryArcEvent.source_feed_id.isnot(None)
            ).scalar()
            arc.source_count = unique_feeds or 1

            session.commit()
            session.refresh(event)
            return self._event_to_dict(event)

    def get_active_story_arcs(
        self,
        digest_topic: str,
        days: int = 14
    ) -> List[Dict]:
        """
        Get story arcs active within the retention window.

        Args:
            digest_topic: Filter by parent topic
            days: Lookback period in days

        Returns:
            List of arc dictionaries with events
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        with self.db_manager.get_session() as session:
            arcs = session.query(StoryArc).options(
                joinedload(StoryArc.events)
            ).filter(
                StoryArc.digest_topic == digest_topic,
                StoryArc.last_updated_at >= cutoff_date
            ).order_by(
                StoryArc.last_updated_at.desc()
            ).all()

            return [self._arc_to_dict(arc, include_events=True) for arc in arcs]

    def get_story_arcs_for_prompt(
        self,
        digest_topic: str,
        max_arcs: int = 15,
        max_events_per_arc: int = 5
    ) -> str:
        """
        Format active story arcs for GPT prompt context.

        Args:
            digest_topic: Filter by parent topic
            max_arcs: Maximum arcs to include
            max_events_per_arc: Maximum events per arc

        Returns:
            Formatted string for prompt inclusion
        """
        arcs = self.get_active_story_arcs(digest_topic, days=14)

        if not arcs:
            return ""

        lines = []
        for arc in arcs[:max_arcs]:
            lines.append(f"\nSTORY ARC: {arc['arc_name']}")
            lines.append(f"Category: {arc['functional_category']}")
            lines.append(f"Events: {arc['event_count']} from {arc['source_count']} sources")

            events = arc.get('events', [])[:max_events_per_arc]
            if events:
                lines.append("Recent timeline:")
                for event in events:
                    date_str = event['event_date'].strftime('%b %d') if isinstance(event['event_date'], datetime) else str(event['event_date'])[:10]
                    lines.append(f"  - [{date_str}] {event['event_summary']}")

        return "\n".join(lines)

    def get_story_arcs_for_digest(
        self,
        digest_topic: str,
        min_events: int = 2,
        exclude_included: bool = True
    ) -> List[Dict]:
        """
        Get story arcs ready for digest generation.

        Args:
            digest_topic: Parent topic
            min_events: Minimum events to be considered a "story"
            exclude_included: Exclude already-included arcs

        Returns:
            List of arc dictionaries with events
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=14)

        with self.db_manager.get_session() as session:
            query = session.query(StoryArc).options(
                joinedload(StoryArc.events)
            ).filter(
                StoryArc.digest_topic == digest_topic,
                StoryArc.last_updated_at >= cutoff_date,
                StoryArc.event_count >= min_events
            )

            if exclude_included:
                query = query.filter(StoryArc.included_in_digest_id.is_(None))

            arcs = query.order_by(
                StoryArc.event_count.desc(),
                StoryArc.last_updated_at.desc()
            ).all()

            return [self._arc_to_dict(arc, include_events=True) for arc in arcs]

    def mark_story_arc_included(
        self,
        story_arc_id: int,
        digest_id: int
    ) -> None:
        """
        Mark a story arc as included in a digest.

        Args:
            story_arc_id: Arc ID
            digest_id: Digest ID
        """
        now = datetime.now(timezone.utc)

        with self.db_manager.get_session() as session:
            arc = session.query(StoryArc).filter(
                StoryArc.id == story_arc_id
            ).first()

            if arc:
                arc.included_in_digest_id = digest_id
                arc.included_at = now
                arc.updated_at = now
                session.commit()

    def cleanup_old_story_arcs(self, days: int = 14) -> int:
        """
        Delete story arcs older than specified days.

        Args:
            days: Delete arcs not updated in this many days

        Returns:
            Number of arcs deleted
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        with self.db_manager.get_session() as session:
            # Events are cascade deleted
            result = session.query(StoryArc).filter(
                StoryArc.last_updated_at < cutoff_date
            ).delete()
            session.commit()
            return result

    def get_story_arc_by_id(self, arc_id: int) -> Optional[Dict]:
        """
        Get a story arc by ID with all events.

        Args:
            arc_id: Arc ID

        Returns:
            Arc dictionary with events, or None
        """
        with self.db_manager.get_session() as session:
            arc = session.query(StoryArc).options(
                joinedload(StoryArc.events)
            ).filter(
                StoryArc.id == arc_id
            ).first()

            if arc:
                return self._arc_to_dict(arc, include_events=True)
            return None

    def get_all_story_arcs(
        self,
        digest_topic: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get all story arcs with optional filters.

        Args:
            digest_topic: Filter by parent topic
            category: Filter by functional category
            limit: Maximum arcs to return

        Returns:
            List of arc dictionaries
        """
        with self.db_manager.get_session() as session:
            query = session.query(StoryArc).options(
                joinedload(StoryArc.events)
            )

            if digest_topic:
                query = query.filter(StoryArc.digest_topic == digest_topic)
            if category:
                query = query.filter(StoryArc.functional_category == category)

            arcs = query.order_by(
                StoryArc.last_updated_at.desc()
            ).limit(limit).all()

            return [self._arc_to_dict(arc, include_events=True) for arc in arcs]

    def delete_story_arc(self, arc_id: int) -> bool:
        """
        Delete a story arc and its events.

        Args:
            arc_id: Arc ID to delete

        Returns:
            True if deleted, False if not found
        """
        with self.db_manager.get_session() as session:
            arc = session.query(StoryArc).filter(
                StoryArc.id == arc_id
            ).first()

            if arc:
                session.delete(arc)
                session.commit()
                return True
            return False

    def get_story_arc_stats(self, days: int = 14) -> Dict:
        """
        Get statistics about story arcs.

        Args:
            days: Time window for statistics

        Returns:
            Dictionary with statistics
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        with self.db_manager.get_session() as session:
            total_arcs = session.query(StoryArc).filter(
                StoryArc.last_updated_at >= cutoff_date
            ).count()

            # Arcs by category
            category_counts = session.query(
                StoryArc.functional_category,
                func.count(StoryArc.id)
            ).filter(
                StoryArc.last_updated_at >= cutoff_date
            ).group_by(
                StoryArc.functional_category
            ).all()

            # Arcs by digest topic
            topic_counts = session.query(
                StoryArc.digest_topic,
                func.count(StoryArc.id)
            ).filter(
                StoryArc.last_updated_at >= cutoff_date
            ).group_by(
                StoryArc.digest_topic
            ).all()

            # Average events per arc
            avg_events = session.query(
                func.avg(StoryArc.event_count)
            ).filter(
                StoryArc.last_updated_at >= cutoff_date
            ).scalar() or 0

            return {
                'total_arcs': total_arcs,
                'arcs_by_category': {cat: count for cat, count in category_counts},
                'arcs_by_topic': {topic: count for topic, count in topic_counts},
                'avg_events_per_arc': float(avg_events),
            }

    def _normalize_arc_name(self, arc_name: str) -> str:
        """
        Normalize arc name to slug for deduplication.

        Args:
            arc_name: Original arc name

        Returns:
            Normalized slug
        """
        slug = arc_name.lower()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[-\s]+", "-", slug)
        slug = slug.strip("-")
        return slug

    def _arc_to_dict(self, arc: StoryArc, include_events: bool = False) -> Dict:
        """Convert StoryArc model to dictionary"""
        result = {
            'id': arc.id,
            'arc_name': arc.arc_name,
            'arc_slug': arc.arc_slug,
            'functional_category': arc.functional_category,
            'digest_topic': arc.digest_topic,
            'summary': arc.summary,
            'started_at': arc.started_at,
            'last_updated_at': arc.last_updated_at,
            'event_count': arc.event_count,
            'source_count': arc.source_count,
            'included_in_digest_id': arc.included_in_digest_id,
            'included_at': arc.included_at,
            'created_at': arc.created_at,
            'updated_at': arc.updated_at,
        }

        if include_events and arc.events:
            # Sort events by date descending (most recent first)
            sorted_events = sorted(arc.events, key=lambda e: e.event_date, reverse=True)
            result['events'] = [self._event_to_dict(e) for e in sorted_events]

        return result

    def _event_to_dict(self, event: StoryArcEvent) -> Dict:
        """Convert StoryArcEvent model to dictionary"""
        return {
            'id': event.id,
            'story_arc_id': event.story_arc_id,
            'event_date': event.event_date,
            'event_summary': event.event_summary,
            'key_points': event.key_points or [],
            'source_feed_id': event.source_feed_id,
            'source_episode_id': event.source_episode_id,
            'source_episode_guid': event.source_episode_guid,
            'source_name': event.source_name,
            'perspective': event.perspective,
            'relevance_score': event.relevance_score,
            'extracted_at': event.extracted_at,
            'created_at': event.created_at,
        }


def get_story_arc_repo() -> StoryArcRepository:
    """Get StoryArcRepository instance"""
    return StoryArcRepository()
