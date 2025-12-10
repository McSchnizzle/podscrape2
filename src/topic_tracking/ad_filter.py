"""
AdFilter: Filters common advertisements from transcript content.
Uses pattern matching against known advertiser signatures.
"""

import logging
from typing import Tuple, List, Optional

from src.config.web_config import WebConfigManager
from src.database.common_ads_repo import get_common_ads_repo


logger = logging.getLogger(__name__)


class AdFilter:
    """
    Filters common advertisements from transcript content.
    Uses pattern matching against known advertiser signatures.
    """

    def __init__(self):
        self.web_config = WebConfigManager()
        self.ad_repo = get_common_ads_repo()

        self.enabled = self.web_config.get_setting("ad_filtering", "enabled", True)
        self.confidence_threshold = self.web_config.get_setting(
            "ad_filtering", "confidence_threshold", 0.7
        )

        # Cache active ad patterns
        self._load_ad_patterns()

    def _load_ad_patterns(self):
        """Load active ad patterns from database"""
        try:
            self.ad_patterns = self.ad_repo.get_active_patterns()
            logger.info(f"Loaded {len(self.ad_patterns)} active ad patterns")
        except Exception as e:
            logger.warning(f"Failed to load ad patterns: {e}")
            self.ad_patterns = []

    def filter_transcript(self, transcript: str) -> Tuple[str, List[str]]:
        """
        Remove ad segments from transcript.

        Args:
            transcript: Original transcript text

        Returns:
            Tuple of (filtered_transcript, detected_ads)
        """
        if not self.enabled:
            return transcript, []

        if not self.ad_patterns:
            logger.debug("No ad patterns loaded, returning original transcript")
            return transcript, []

        detected_ads = []
        filtered_lines = []

        lines = transcript.split("\n")

        for line in lines:
            ad_match = self._detect_ad_in_line(line)

            if ad_match:
                if ad_match not in detected_ads:
                    detected_ads.append(ad_match)
                # Skip this line (it's an ad)
                continue
            else:
                filtered_lines.append(line)

        filtered_transcript = "\n".join(filtered_lines)

        if detected_ads:
            logger.info(
                f"Filtered {len(detected_ads)} ad types: {', '.join(detected_ads)}"
            )

        return filtered_transcript, detected_ads

    def _detect_ad_in_line(self, line: str) -> Optional[str]:
        """
        Check if line contains advertisement content.

        Args:
            line: Single line of transcript

        Returns:
            Advertiser name if detected, None otherwise
        """
        line_lower = line.lower()

        for pattern in self.ad_patterns:
            keywords = pattern["pattern_keywords"]
            matches = sum(1 for kw in keywords if kw.lower() in line_lower)

            # Calculate match confidence
            confidence = matches / len(keywords) if keywords else 0

            # Use pattern-specific threshold if available, otherwise use global
            threshold = pattern.get("confidence_threshold", self.confidence_threshold)

            if confidence >= threshold:
                return pattern["advertiser_name"]

        return None

    def reload_patterns(self):
        """Reload ad patterns from database (for testing or config changes)"""
        self._load_ad_patterns()
