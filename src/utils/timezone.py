"""
Timezone utilities for the RSS Podcast Digest System.

All timestamps in the system use Pacific Time (US/Pacific) for consistency
with the user's local timezone.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

# Pacific timezone constant
PACIFIC_TZ = ZoneInfo("America/Los_Angeles")


def get_pacific_now() -> datetime:
    """
    Get the current time in Pacific timezone.
    
    Returns:
        datetime: Current datetime with Pacific timezone info
    """
    return datetime.now(PACIFIC_TZ)


def to_pacific(dt: datetime) -> datetime:
    """
    Convert a datetime to Pacific timezone.
    
    Args:
        dt: datetime to convert (can be naive or aware)
        
    Returns:
        datetime: datetime converted to Pacific timezone
    """
    if dt.tzinfo is None:
        # Assume UTC if naive
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(PACIFIC_TZ)


def format_pacific_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S %Z") -> str:
    """
    Format a datetime in Pacific timezone.
    
    Args:
        dt: datetime to format
        format_str: strftime format string
        
    Returns:
        str: Formatted datetime string in Pacific time
    """
    pacific_dt = to_pacific(dt)
    return pacific_dt.strftime(format_str)