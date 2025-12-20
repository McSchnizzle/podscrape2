"""
CommonAdsRepository: Data access for common_ads table.
Manages advertisement pattern storage and retrieval for filtering.
"""

from datetime import datetime, timezone
from typing import List, Dict, Optional

from src.database.sqlalchemy_models import CommonAd
from src.database.models import get_database_manager


class CommonAdsRepository:
    """Repository for common_ads table operations"""

    def __init__(self):
        self.db_manager = get_database_manager()

    def get_active_patterns(self) -> List[Dict]:
        """
        Get all active ad patterns for filtering.

        Returns:
            List of dictionaries with pattern data
        """
        with self.db_manager.get_session() as session:
            ads = (
                session.query(CommonAd)
                .filter(CommonAd.is_active == True)  # noqa: E712
                .all()
            )

            return [self._to_dict(ad) for ad in ads]

    def get_all_patterns(self) -> List[Dict]:
        """
        Get all ad patterns (active and inactive).

        Returns:
            List of dictionaries with pattern data
        """
        with self.db_manager.get_session() as session:
            ads = session.query(CommonAd).all()
            return [self._to_dict(ad) for ad in ads]

    def get_by_id(self, ad_id: int) -> Optional[Dict]:
        """
        Get ad pattern by ID.

        Args:
            ad_id: Ad database ID

        Returns:
            Dictionary with ad data or None
        """
        with self.db_manager.get_session() as session:
            ad = session.query(CommonAd).filter(CommonAd.id == ad_id).first()
            return self._to_dict(ad) if ad else None

    def get_by_advertiser(self, advertiser_name: str) -> Optional[Dict]:
        """
        Get ad pattern by advertiser name.

        Args:
            advertiser_name: Advertiser name (case-insensitive)

        Returns:
            Dictionary with ad data or None
        """
        with self.db_manager.get_session() as session:
            ad = (
                session.query(CommonAd)
                .filter(CommonAd.advertiser_name.ilike(advertiser_name))
                .first()
            )
            return self._to_dict(ad) if ad else None

    def create_pattern(
        self,
        advertiser_name: str,
        pattern_keywords: List[str],
        confidence_threshold: float = 0.8,
        is_active: bool = True,
    ) -> CommonAd:
        """
        Create a new ad pattern.

        Args:
            advertiser_name: Name of advertiser
            pattern_keywords: List of keywords/phrases to match
            confidence_threshold: Match confidence required (0.0-1.0)
            is_active: Whether pattern is active

        Returns:
            Created CommonAd instance
        """
        now = datetime.now(timezone.utc)

        with self.db_manager.get_session() as session:
            new_ad = CommonAd(
                advertiser_name=advertiser_name,
                pattern_keywords=pattern_keywords,
                confidence_threshold=confidence_threshold,
                is_active=is_active,
                first_detected_at=now,
                last_detected_at=now,
                detection_count=0,
            )
            session.add(new_ad)
            session.commit()
            session.refresh(new_ad)
            return new_ad

    def update_pattern(
        self,
        ad_id: int,
        pattern_keywords: Optional[List[str]] = None,
        confidence_threshold: Optional[float] = None,
        is_active: Optional[bool] = None,
    ) -> bool:
        """
        Update an existing ad pattern.

        Args:
            ad_id: Ad database ID
            pattern_keywords: New keywords (if provided)
            confidence_threshold: New threshold (if provided)
            is_active: New active status (if provided)

        Returns:
            True if updated, False if not found
        """
        with self.db_manager.get_session() as session:
            ad = session.query(CommonAd).filter(CommonAd.id == ad_id).first()

            if not ad:
                return False

            if pattern_keywords is not None:
                ad.pattern_keywords = pattern_keywords
            if confidence_threshold is not None:
                ad.confidence_threshold = confidence_threshold
            if is_active is not None:
                ad.is_active = is_active

            ad.updated_at = datetime.now(timezone.utc)
            session.commit()
            return True

    def increment_detection_count(self, ad_id: int) -> bool:
        """
        Increment detection count for an ad pattern.
        Called when ad is detected in content.

        Args:
            ad_id: Ad database ID

        Returns:
            True if updated, False if not found
        """
        now = datetime.now(timezone.utc)

        with self.db_manager.get_session() as session:
            ad = session.query(CommonAd).filter(CommonAd.id == ad_id).first()

            if not ad:
                return False

            ad.detection_count += 1
            ad.last_detected_at = now
            ad.updated_at = now
            session.commit()
            return True

    def delete_pattern(self, ad_id: int) -> bool:
        """
        Delete an ad pattern.

        Args:
            ad_id: Ad database ID

        Returns:
            True if deleted, False if not found
        """
        with self.db_manager.get_session() as session:
            result = (
                session.query(CommonAd)
                .filter(CommonAd.id == ad_id)
                .delete()
            )
            session.commit()
            return result > 0

    def get_detection_stats(self) -> Dict:
        """
        Get statistics about ad detection.

        Returns:
            Dictionary with statistics
        """
        with self.db_manager.get_session() as session:
            total_patterns = session.query(CommonAd).count()
            active_patterns = (
                session.query(CommonAd).filter(CommonAd.is_active == True).count()  # noqa: E712
            )

            # Top detected ads
            top_detected = (
                session.query(
                    CommonAd.advertiser_name,
                    CommonAd.detection_count,
                    CommonAd.last_detected_at,
                )
                .filter(CommonAd.detection_count > 0)
                .order_by(CommonAd.detection_count.desc())
                .limit(10)
                .all()
            )

            return {
                "total_patterns": total_patterns,
                "active_patterns": active_patterns,
                "top_detected": [
                    {
                        "advertiser": name,
                        "count": count,
                        "last_seen": last_seen,
                    }
                    for name, count, last_seen in top_detected
                ],
            }

    def _to_dict(self, ad: CommonAd) -> Dict:
        """Convert CommonAd model to dictionary"""
        return {
            "id": ad.id,
            "advertiser_name": ad.advertiser_name,
            "pattern_keywords": ad.pattern_keywords,
            "confidence_threshold": ad.confidence_threshold,
            "is_active": ad.is_active,
            "first_detected_at": ad.first_detected_at,
            "last_detected_at": ad.last_detected_at,
            "detection_count": ad.detection_count,
            "created_at": ad.created_at,
            "updated_at": ad.updated_at,
        }


# Factory function for consistency with existing repository pattern
def get_common_ads_repo() -> CommonAdsRepository:
    """Get CommonAdsRepository instance"""
    return CommonAdsRepository()
