"""
Error classifier for workflow logs.

Classifies error messages into categories and extracts metadata
for pattern analysis.
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ClassifiedError:
    """Result of classifying an error message."""
    category: str
    phase: str
    severity: str
    error_code: Optional[str] = None
    feed_url: Optional[str] = None
    error_summary: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


# Error categories with their detection patterns
# Order matters - first match wins
ERROR_PATTERNS: List[Tuple[str, str, List[str]]] = [
    # (category, severity, patterns)

    # Feed errors - RSS feed access issues
    ('feed_error', 'warning', [
        r'403\s*(Forbidden)?',
        r'404\s*(Not Found)?',
        r'Feed.*?returned\s+\d{3}',
        r'RSS feed.*?(error|failed|timeout)',
        r'Failed to (fetch|parse|download).*?feed',
        r'Connection.*?refused.*?feed',
        r'Timeout.*?(fetching|downloading).*?feed',
        r'HTTP\s+\d{3}.*?feed',
    ]),

    # Transcription errors
    ('transcription_error', 'error', [
        r'Whisper.*?(error|failed)',
        r'Transcription.*?(error|failed)',
        r'ASR.*?(error|failed)',
        r'Audio.*?transcri(be|ption).*?(error|failed)',
        r'Failed to transcribe',
    ]),

    # TTS errors - ElevenLabs issues
    ('tts_error', 'error', [
        r'ElevenLabs.*?(error|failed)',
        r'TTS.*?(error|failed)',
        r'Text-to-speech.*?(error|failed)',
        r'Voice.*?generation.*?(error|failed)',
        r'Audio.*?generat.*?(error|failed)',
        r'Empty.*?response.*?ElevenLabs',
        r'dialogue.*?(error|failed)',
    ]),

    # API errors - OpenAI, other external APIs
    ('api_error', 'error', [
        r'OpenAI.*?(error|failed)',
        r'API.*?rate.*?limit',
        r'API.*?(error|failed)',
        r'429\s*(Too Many Requests)?',
        r'500\s*(Internal Server Error)?',
        r'502\s*(Bad Gateway)?',
        r'503\s*(Service Unavailable)?',
        r'504\s*(Gateway Timeout)?',
        r'GPT.*?(error|failed)',
        r'model.*?(error|failed|unavailable)',
    ]),

    # Scoring errors
    ('scoring_error', 'error', [
        r'Scor(e|ing).*?(error|failed)',
        r'Failed to score',
        r'Content.*?scoring.*?(error|failed)',
    ]),

    # Script generation errors
    ('script_error', 'error', [
        r'Script.*?(error|failed)',
        r'Generation.*?(error|failed)',
        r'Digest.*?generat.*?(error|failed)',
        r'Failed to generate.*?script',
    ]),

    # Publishing errors - GitHub, release issues
    ('publishing_error', 'error', [
        r'GitHub.*?(error|failed)',
        r'Publish.*?(error|failed)',
        r'Release.*?(error|failed)',
        r'Upload.*?(error|failed)',
        r'gh\s+.*?(error|failed)',
    ]),

    # Database errors
    ('database_error', 'critical', [
        r'Database.*?(error|failed)',
        r'SQL.*?(error|failed)',
        r'Connection.*?database.*?(error|failed)',
        r'Supabase.*?(error|failed)',
        r'PostgreSQL.*?(error|failed)',
        r'IntegrityError',
        r'OperationalError',
    ]),

    # System errors - infrastructure issues
    ('system_error', 'critical', [
        r'Out of memory',
        r'Disk.*?(full|space)',
        r'Permission denied',
        r'No such file',
        r'FileNotFoundError',
        r'MemoryError',
        r'OSError',
        r'IOError',
    ]),
]

# Phase detection patterns
PHASE_PATTERNS: Dict[str, List[str]] = {
    'discovery': [
        r'discover',
        r'RSS',
        r'feed.*?pars',
        r'episode.*?(found|fetch)',
    ],
    'audio': [
        r'audio',
        r'download',
        r'transcri',
        r'whisper',
        r'ASR',
        r'chunk',
    ],
    'digest': [
        r'digest',
        r'script.*?generat',
        r'GPT',
        r'OpenAI',
        r'scor(e|ing)',
    ],
    'tts': [
        r'TTS',
        r'ElevenLabs',
        r'voice',
        r'text-to-speech',
        r'audio.*?generat',
    ],
    'publishing': [
        r'publish',
        r'GitHub',
        r'release',
        r'upload',
    ],
    'retention': [
        r'retention',
        r'cleanup',
        r'delete.*?old',
        r'prun(e|ing)',
    ],
}

# URL extraction pattern
URL_PATTERN = re.compile(
    r'https?://[^\s<>"\']+(?:\.[a-zA-Z]{2,})+[^\s<>"\']*',
    re.IGNORECASE
)

# HTTP status code extraction
HTTP_STATUS_PATTERN = re.compile(
    r'\b(4\d{2}|5\d{2})\b'
)


class ErrorClassifier:
    """Classifies error messages for pattern analysis."""

    def __init__(self):
        # Compile patterns for efficiency
        self._error_patterns = [
            (cat, sev, [re.compile(p, re.IGNORECASE) for p in patterns])
            for cat, sev, patterns in ERROR_PATTERNS
        ]
        self._phase_patterns = {
            phase: [re.compile(p, re.IGNORECASE) for p in patterns]
            for phase, patterns in PHASE_PATTERNS.items()
        }

    def classify(self, message: str, level: str = 'ERROR',
                 phase_hint: Optional[str] = None) -> ClassifiedError:
        """
        Classify an error message.

        Args:
            message: The error message text
            level: Log level (ERROR, WARNING, etc.)
            phase_hint: Optional hint about which phase the error occurred in

        Returns:
            ClassifiedError with category, phase, severity, and extracted metadata
        """
        # Determine category and severity
        category, severity = self._classify_category(message, level)

        # Determine phase
        phase = phase_hint or self._detect_phase(message)

        # Extract error code (HTTP status, etc.)
        error_code = self._extract_error_code(message)

        # Extract feed URL if present
        feed_url = self._extract_feed_url(message)

        # Generate summary (first 200 chars, cleaned)
        error_summary = self._generate_summary(message)

        # Extract any extra structured data
        extra = self._extract_extra(message)

        return ClassifiedError(
            category=category,
            phase=phase,
            severity=severity,
            error_code=error_code,
            feed_url=feed_url,
            error_summary=error_summary,
            extra=extra if extra else None,
        )

    def _classify_category(self, message: str, level: str) -> Tuple[str, str]:
        """Determine error category and severity."""
        for category, default_severity, patterns in self._error_patterns:
            for pattern in patterns:
                if pattern.search(message):
                    return category, default_severity

        # Default category based on log level
        if level.upper() in ('CRITICAL', 'FATAL'):
            return 'system_error', 'critical'
        elif level.upper() == 'WARNING':
            return 'unknown', 'warning'
        else:
            return 'unknown', 'error'

    def _detect_phase(self, message: str) -> str:
        """Detect which pipeline phase the error occurred in."""
        for phase, patterns in self._phase_patterns.items():
            for pattern in patterns:
                if pattern.search(message):
                    return phase
        return 'unknown'

    def _extract_error_code(self, message: str) -> Optional[str]:
        """Extract HTTP status code or other error codes."""
        match = HTTP_STATUS_PATTERN.search(message)
        if match:
            return match.group(1)
        return None

    def _extract_feed_url(self, message: str) -> Optional[str]:
        """Extract feed URL from error message if present."""
        urls = URL_PATTERN.findall(message)
        for url in urls:
            # Prioritize RSS/feed URLs
            if any(x in url.lower() for x in ['rss', 'feed', 'xml', 'podcast']):
                return url[:2048]  # Limit URL length
        # Return first URL if no RSS-specific URL found
        if urls:
            return urls[0][:2048]
        return None

    def _generate_summary(self, message: str) -> str:
        """Generate a short summary of the error message."""
        # Clean up the message
        summary = message.strip()
        # Remove excessive whitespace
        summary = ' '.join(summary.split())
        # Truncate to 200 characters
        if len(summary) > 200:
            summary = summary[:197] + '...'
        return summary

    def _extract_extra(self, message: str) -> Optional[Dict[str, Any]]:
        """Extract any additional structured data from the message."""
        extra = {}

        # Extract all URLs found
        urls = URL_PATTERN.findall(message)
        if len(urls) > 1:
            extra['all_urls'] = urls[:10]  # Limit to 10 URLs

        # Extract all HTTP status codes found
        codes = HTTP_STATUS_PATTERN.findall(message)
        if len(codes) > 1:
            extra['status_codes'] = codes

        # Look for episode/feed IDs
        id_match = re.search(r'(?:episode|feed|digest)[\s_-]?id[:\s]+(\d+)',
                            message, re.IGNORECASE)
        if id_match:
            extra['mentioned_id'] = int(id_match.group(1))

        return extra if extra else None

    def classify_batch(self, messages: List[Dict[str, Any]],
                       phase_hint: Optional[str] = None) -> List[ClassifiedError]:
        """
        Classify a batch of error messages.

        Args:
            messages: List of dicts with 'message' and optional 'level' keys
            phase_hint: Optional phase hint to apply to all messages

        Returns:
            List of ClassifiedError objects
        """
        results = []
        for msg_data in messages:
            message = msg_data.get('message', str(msg_data))
            level = msg_data.get('level', 'ERROR')
            hint = msg_data.get('phase') or phase_hint
            results.append(self.classify(message, level, hint))
        return results
