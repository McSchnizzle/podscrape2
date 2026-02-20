"""
WebConfigManager: DB-backed settings for the Web UI.
Provides typed get/set with basic validation and integrates with the pipeline optionally.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path
from sqlalchemy import text, Column, Integer, String, DateTime, UniqueConstraint
from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.postgresql import insert

# Lazy import to avoid circular dependency when database logging is enabled
# from src.database.models import get_database_manager


class SettingsKeys:
    """Centralized constants for web_settings keys to prevent typos."""

    class ContentFiltering:
        CATEGORY = "content_filtering"
        SCORE_THRESHOLD = "score_threshold"
        MAX_EPISODES_PER_DIGEST = "max_episodes_per_digest"
        MIN_EPISODES_PER_DIGEST = "min_episodes_per_digest"

    class AudioProcessing:
        CATEGORY = "audio_processing"
        CHUNK_DURATION_MINUTES = "chunk_duration_minutes"
        TRANSCRIBE_ALL_CHUNKS = "transcribe_all_chunks"
        MAX_CHUNKS_PER_EPISODE = "max_chunks_per_episode"

    class Pipeline:
        CATEGORY = "pipeline"
        MAX_EPISODES_PER_RUN = "max_episodes_per_run"
        DISCOVERY_LOOKBACK_DAYS = "discovery_lookback_days"

    class Retention:
        CATEGORY = "retention"
        LOCAL_MP3_DAYS = "local_mp3_days"
        AUDIO_CACHE_DAYS = "audio_cache_days"
        AUDIO_CHUNKS_DAYS = "audio_chunks_days"
        LOGS_DAYS = "logs_days"
        EPISODE_RETENTION_DAYS = "episode_retention_days"
        DIGEST_RETENTION_DAYS = "digest_retention_days"
        GITHUB_RELEASES_DAYS = "github_releases_days"

    class TopicTracking:
        CATEGORY = "topic_tracking"
        MIN_SCORE_FOR_EXTRACTION = "min_score_for_extraction"
        MAX_TOPICS_PER_EPISODE = "max_topics_per_episode"
        RETENTION_DAYS = "retention_days"
        EXTRACTION_MODEL = "extraction_model"
        RECONCILIATION_MODEL = "reconciliation_model"
        RECONCILIATION_LOOKBACK = "reconciliation_lookback"
        RECONCILIATION_MIN_OCCURRENCES = "reconciliation_min_occurrences"

    class AdFiltering:
        CATEGORY = "ad_filtering"
        ENABLED = "enabled"
        CONFIDENCE_THRESHOLD = "confidence_threshold"

    class TopicEvolution:
        CATEGORY = "topic_evolution"
        ENABLE_NOVELTY_DETECTION = "enable_novelty_detection"
        NOVELTY_THRESHOLD = "novelty_threshold"
        EMBEDDING_MODEL = "embedding_model"
        SIMILARITY_THRESHOLD = "similarity_threshold"

    class AIContentScoring:
        CATEGORY = "ai_content_scoring"
        MODEL = "model"
        MAX_TOKENS = "max_tokens"
        MAX_EPISODES_PER_BATCH = "max_episodes_per_batch"
        MAX_INPUT_TOKENS = "max_input_tokens"
        PROMPT_MAX_CHARS = "prompt_max_chars"

    class AIDigestGeneration:
        CATEGORY = "ai_digest_generation"
        MODEL = "model"
        MAX_OUTPUT_TOKENS = "max_output_tokens"
        MAX_INPUT_TOKENS = "max_input_tokens"
        TRANSCRIPT_BUFFER_PERCENT = "transcript_buffer_percent"
        TRANSCRIPT_MIN_CHARS = "transcript_min_chars"
        TRANSCRIPT_MAX_CHARS = "transcript_max_chars"

    class AIMetadataGeneration:
        CATEGORY = "ai_metadata_generation"
        MODEL = "model"
        MAX_INPUT_TOKENS = "max_input_tokens"
        MAX_TITLE_TOKENS = "max_title_tokens"
        MAX_SUMMARY_TOKENS = "max_summary_tokens"
        MAX_DESCRIPTION_TOKENS = "max_description_tokens"

    class AITTSGeneration:
        CATEGORY = "ai_tts_generation"
        MODEL = "model"
        MAX_CHARACTERS = "max_characters"

    class AISTTTranscription:
        CATEGORY = "ai_stt_transcription"
        MODEL = "model"
        MAX_FILE_SIZE_MB = "max_file_size_mb"

    class TranscriptProcessing:
        CATEGORY = "transcript_processing"
        AD_TRIM_ENABLED = "ad_trim_enabled"
        AD_TRIM_START_PERCENT = "ad_trim_start_percent"
        AD_TRIM_END_PERCENT = "ad_trim_end_percent"

    class Database:
        CATEGORY = "database"
        POOL_SIZE = "pool_size"
        MAX_OVERFLOW = "max_overflow"
        POOL_RECYCLE_SECONDS = "pool_recycle_seconds"

    class ApiTimeouts:
        CATEGORY = "api_timeouts"
        OPENAI_TIMEOUT = "openai_timeout"
        ELEVENLABS_TIMEOUT = "elevenlabs_timeout"
        ELEVENLABS_DIALOGUE_TIMEOUT = "elevenlabs_dialogue_timeout"
        GITHUB_TIMEOUT = "github_timeout"
        GITHUB_UPLOAD_TIMEOUT = "github_upload_timeout"
        HTTP_DEFAULT_TIMEOUT = "http_default_timeout"
        FFMPEG_TIMEOUT = "ffmpeg_timeout"
        AUDIO_DOWNLOAD_TIMEOUT = "audio_download_timeout"

    class Tts:
        CATEGORY = "tts"
        RATE_LIMIT_DELAY = "rate_limit_delay"

    class Discovery:
        CATEGORY = "discovery"
        MAX_ENTRIES_PER_FEED = "max_entries_per_feed"
        MAX_STORY_ARCS_CONTEXT = "max_story_arcs_context"


# AI Model Definitions and Limits
AI_MODELS = {
    'openai': {
        'gpt-5.2': {'max_output': 128000, 'max_input': 400000, 'display_name': 'GPT-5.2 Thinking'},
        'gpt-5.2-chat-latest': {'max_output': 128000, 'max_input': 400000, 'display_name': 'GPT-5.2 Instant'},
        'gpt-5.2-pro': {'max_output': 128000, 'max_input': 400000, 'display_name': 'GPT-5.2 Pro'},
        'gpt-5.1': {'max_output': 128000, 'max_input': 400000, 'display_name': 'GPT-5.1'},
        'gpt-5': {'max_output': 128000, 'max_input': 272000, 'display_name': 'GPT-5'},
        'gpt-5-mini': {'max_output': 128000, 'max_input': 400000, 'display_name': 'GPT-5 Mini'},
        'gpt-5-nano': {'max_output': 64000, 'max_input': 128000, 'display_name': 'GPT-5 Nano'},
    },
    'elevenlabs': {
        'eleven_v3': {'max_characters': 5000, 'display_name': 'v3 (5k chars, highest quality)'},
        'eleven_turbo_v2_5': {'max_characters': 40000, 'display_name': 'Turbo v2.5 (40k chars)'},
        'eleven_turbo_v2': {'max_characters': 30000, 'display_name': 'Turbo v2 (30k chars)'},
        'eleven_flash_v2_5': {'max_characters': 40000, 'display_name': 'Flash v2.5 (40k chars, low latency)'},
        'eleven_flash_v2': {'max_characters': 30000, 'display_name': 'Flash v2 (30k chars, low latency)'},
        'eleven_multilingual_v2': {'max_characters': 10000, 'display_name': 'Multilingual v2 (10k chars)'},
        'eleven_multilingual_v1': {'max_characters': 10000, 'display_name': 'Multilingual v1 (10k chars)'}
    },
    'whisper': {
        'whisper-1': {'max_file_size_mb': 25, 'display_name': 'Whisper-1 (25MB limit)'}
    },
    'anthropic': {
        'claude-opus-4-5-20250220': {'max_output': 32000, 'max_input': 200000, 'display_name': 'Claude Opus 4.5'},
        'claude-sonnet-4-6-20250514': {'max_output': 16000, 'max_input': 200000, 'display_name': 'Claude Sonnet 4.6'},
        'claude-haiku-4-5-20251001': {'max_output': 8192, 'max_input': 200000, 'display_name': 'Claude Haiku 4.5'},
    }
}

Base = declarative_base()

class WebSettingModel(Base):
    __tablename__ = 'web_settings'

    id = Column(Integer, primary_key=True)
    category = Column(String, nullable=False)
    setting_key = Column(String, nullable=False)
    setting_value = Column(String, nullable=False)
    value_type = Column(String, nullable=False, default='string')
    description = Column(String)
    updated_at = Column(DateTime, default=datetime.now)

    __table_args__ = (UniqueConstraint('category', 'setting_key', name='unique_category_setting'),)


DEFAULTS = {
    # Content Filtering
    (SettingsKeys.ContentFiltering.CATEGORY, SettingsKeys.ContentFiltering.SCORE_THRESHOLD): {"type": "float", "default": 0.65, "min": 0.0, "max": 1.0},
    (SettingsKeys.ContentFiltering.CATEGORY, SettingsKeys.ContentFiltering.MAX_EPISODES_PER_DIGEST): {"type": "int", "default": 5, "min": 1, "max": 20},
    (SettingsKeys.ContentFiltering.CATEGORY, SettingsKeys.ContentFiltering.MIN_EPISODES_PER_DIGEST): {"type": "int", "default": 1, "min": 0, "max": 10},

    # Audio Processing
    (SettingsKeys.AudioProcessing.CATEGORY, SettingsKeys.AudioProcessing.CHUNK_DURATION_MINUTES): {"type": "int", "default": 10, "min": 1, "max": 30},
    (SettingsKeys.AudioProcessing.CATEGORY, SettingsKeys.AudioProcessing.TRANSCRIBE_ALL_CHUNKS): {"type": "bool", "default": True},
    (SettingsKeys.AudioProcessing.CATEGORY, SettingsKeys.AudioProcessing.MAX_CHUNKS_PER_EPISODE): {"type": "int", "default": 3, "min": 1, "max": 50},

    # Pipeline
    (SettingsKeys.Pipeline.CATEGORY, SettingsKeys.Pipeline.MAX_EPISODES_PER_RUN): {"type": "int", "default": 3, "min": 1, "max": 20},
    (SettingsKeys.Pipeline.CATEGORY, SettingsKeys.Pipeline.DISCOVERY_LOOKBACK_DAYS): {"type": "int", "default": 3, "min": 1, "max": 30},

    # Retention policies (days)
    (SettingsKeys.Retention.CATEGORY, SettingsKeys.Retention.LOCAL_MP3_DAYS): {"type": "int", "default": 14, "min": 0, "max": 365},
    (SettingsKeys.Retention.CATEGORY, SettingsKeys.Retention.AUDIO_CACHE_DAYS): {"type": "int", "default": 3, "min": 0, "max": 30},
    (SettingsKeys.Retention.CATEGORY, SettingsKeys.Retention.AUDIO_CHUNKS_DAYS): {"type": "int", "default": 3, "min": 0, "max": 30},
    (SettingsKeys.Retention.CATEGORY, SettingsKeys.Retention.LOGS_DAYS): {"type": "int", "default": 3, "min": 0, "max": 365},
    (SettingsKeys.Retention.CATEGORY, SettingsKeys.Retention.EPISODE_RETENTION_DAYS): {"type": "int", "default": 14, "min": 8, "max": 365},
    (SettingsKeys.Retention.CATEGORY, SettingsKeys.Retention.DIGEST_RETENTION_DAYS): {"type": "int", "default": 14, "min": 8, "max": 365},
    (SettingsKeys.Retention.CATEGORY, SettingsKeys.Retention.GITHUB_RELEASES_DAYS): {"type": "int", "default": 14, "min": 0, "max": 365},

    # Topic Tracking Configuration
    (SettingsKeys.TopicTracking.CATEGORY, SettingsKeys.TopicTracking.MIN_SCORE_FOR_EXTRACTION): {"type": "float", "default": 0.70, "min": 0.0, "max": 1.0},
    (SettingsKeys.TopicTracking.CATEGORY, SettingsKeys.TopicTracking.MAX_TOPICS_PER_EPISODE): {"type": "int", "default": 15, "min": 3, "max": 20},
    (SettingsKeys.TopicTracking.CATEGORY, SettingsKeys.TopicTracking.RETENTION_DAYS): {"type": "int", "default": 14, "min": 7, "max": 90},
    (SettingsKeys.TopicTracking.CATEGORY, SettingsKeys.TopicTracking.EXTRACTION_MODEL): {"type": "string", "default": "gpt-5-mini"},
    (SettingsKeys.TopicTracking.CATEGORY, SettingsKeys.TopicTracking.RECONCILIATION_MODEL): {"type": "string", "default": "gpt-5-mini"},
    (SettingsKeys.TopicTracking.CATEGORY, SettingsKeys.TopicTracking.RECONCILIATION_LOOKBACK): {"type": "int", "default": 7, "min": 3, "max": 15},
    (SettingsKeys.TopicTracking.CATEGORY, SettingsKeys.TopicTracking.RECONCILIATION_MIN_OCCURRENCES): {"type": "int", "default": 2, "min": 2, "max": 5},

    # Ad Filtering Configuration
    (SettingsKeys.AdFiltering.CATEGORY, SettingsKeys.AdFiltering.ENABLED): {"type": "bool", "default": True},
    (SettingsKeys.AdFiltering.CATEGORY, SettingsKeys.AdFiltering.CONFIDENCE_THRESHOLD): {"type": "float", "default": 0.7, "min": 0.0, "max": 1.0},

    # Topic Evolution Configuration (v2.01+)
    (SettingsKeys.TopicEvolution.CATEGORY, SettingsKeys.TopicEvolution.ENABLE_NOVELTY_DETECTION): {"type": "bool", "default": True},
    (SettingsKeys.TopicEvolution.CATEGORY, SettingsKeys.TopicEvolution.NOVELTY_THRESHOLD): {"type": "float", "default": 0.30, "min": 0.0, "max": 1.0},
    (SettingsKeys.TopicEvolution.CATEGORY, SettingsKeys.TopicEvolution.EMBEDDING_MODEL): {"type": "string", "default": "text-embedding-3-small"},
    (SettingsKeys.TopicEvolution.CATEGORY, SettingsKeys.TopicEvolution.SIMILARITY_THRESHOLD): {"type": "float", "default": 0.75, "min": 0.5, "max": 1.0},

    # AI Configuration - Content Scoring Phase
    (SettingsKeys.AIContentScoring.CATEGORY, SettingsKeys.AIContentScoring.MODEL): {"type": "string", "default": "gpt-5-mini"},
    (SettingsKeys.AIContentScoring.CATEGORY, SettingsKeys.AIContentScoring.MAX_TOKENS): {"type": "int", "default": 1000, "min": 100, "max": 128000},
    (SettingsKeys.AIContentScoring.CATEGORY, SettingsKeys.AIContentScoring.MAX_EPISODES_PER_BATCH): {"type": "int", "default": 10, "min": 1, "max": 50},
    (SettingsKeys.AIContentScoring.CATEGORY, SettingsKeys.AIContentScoring.MAX_INPUT_TOKENS): {"type": "int", "default": 120000, "min": 1000, "max": 272000},
    (SettingsKeys.AIContentScoring.CATEGORY, SettingsKeys.AIContentScoring.PROMPT_MAX_CHARS): {"type": "int", "default": 4000, "min": 0, "max": 200000},

    # AI Configuration - Digest Generation Phase
    (SettingsKeys.AIDigestGeneration.CATEGORY, SettingsKeys.AIDigestGeneration.MODEL): {"type": "string", "default": "gpt-5"},
    (SettingsKeys.AIDigestGeneration.CATEGORY, SettingsKeys.AIDigestGeneration.MAX_OUTPUT_TOKENS): {"type": "int", "default": 25000, "min": 1000, "max": 128000},
    (SettingsKeys.AIDigestGeneration.CATEGORY, SettingsKeys.AIDigestGeneration.MAX_INPUT_TOKENS): {"type": "int", "default": 150000, "min": 10000, "max": 272000},
    (SettingsKeys.AIDigestGeneration.CATEGORY, SettingsKeys.AIDigestGeneration.TRANSCRIPT_BUFFER_PERCENT): {"type": "float", "default": 20.0, "min": 0.0, "max": 95.0},
    (SettingsKeys.AIDigestGeneration.CATEGORY, SettingsKeys.AIDigestGeneration.TRANSCRIPT_MIN_CHARS): {"type": "int", "default": 2000, "min": 0, "max": 500000},
    (SettingsKeys.AIDigestGeneration.CATEGORY, SettingsKeys.AIDigestGeneration.TRANSCRIPT_MAX_CHARS): {"type": "int", "default": 200000, "min": 0, "max": 1000000},

    # AI Configuration - Metadata Generation Phase
    (SettingsKeys.AIMetadataGeneration.CATEGORY, SettingsKeys.AIMetadataGeneration.MODEL): {"type": "string", "default": "gpt-5-mini"},
    (SettingsKeys.AIMetadataGeneration.CATEGORY, SettingsKeys.AIMetadataGeneration.MAX_INPUT_TOKENS): {"type": "int", "default": 60000, "min": 1000, "max": 128000},
    (SettingsKeys.AIMetadataGeneration.CATEGORY, SettingsKeys.AIMetadataGeneration.MAX_TITLE_TOKENS): {"type": "int", "default": 50, "min": 10, "max": 200},
    (SettingsKeys.AIMetadataGeneration.CATEGORY, SettingsKeys.AIMetadataGeneration.MAX_SUMMARY_TOKENS): {"type": "int", "default": 200, "min": 50, "max": 1000},
    (SettingsKeys.AIMetadataGeneration.CATEGORY, SettingsKeys.AIMetadataGeneration.MAX_DESCRIPTION_TOKENS): {"type": "int", "default": 500, "min": 100, "max": 2000},

    # AI Configuration - TTS Generation Phase
    (SettingsKeys.AITTSGeneration.CATEGORY, SettingsKeys.AITTSGeneration.MODEL): {"type": "string", "default": "eleven_turbo_v2_5"},
    (SettingsKeys.AITTSGeneration.CATEGORY, SettingsKeys.AITTSGeneration.MAX_CHARACTERS): {"type": "int", "default": 35000, "min": 1000, "max": 40000},

    # AI Configuration - Speech-to-Text Phase
    (SettingsKeys.AISTTTranscription.CATEGORY, SettingsKeys.AISTTTranscription.MODEL): {"type": "string", "default": "whisper-1"},
    (SettingsKeys.AISTTTranscription.CATEGORY, SettingsKeys.AISTTTranscription.MAX_FILE_SIZE_MB): {"type": "int", "default": 20, "min": 1, "max": 25},

    # Transcript Processing Controls (scoring + digest ingestion)
    (SettingsKeys.TranscriptProcessing.CATEGORY, SettingsKeys.TranscriptProcessing.AD_TRIM_ENABLED): {"type": "bool", "default": True},
    (SettingsKeys.TranscriptProcessing.CATEGORY, SettingsKeys.TranscriptProcessing.AD_TRIM_START_PERCENT): {"type": "float", "default": 5.0, "min": 0.0, "max": 50.0},
    (SettingsKeys.TranscriptProcessing.CATEGORY, SettingsKeys.TranscriptProcessing.AD_TRIM_END_PERCENT): {"type": "float", "default": 5.0, "min": 0.0, "max": 50.0},

    # Database Connection Pool Settings
    (SettingsKeys.Database.CATEGORY, SettingsKeys.Database.POOL_SIZE): {"type": "int", "default": 5, "min": 1, "max": 20},
    (SettingsKeys.Database.CATEGORY, SettingsKeys.Database.MAX_OVERFLOW): {"type": "int", "default": 10, "min": 0, "max": 50},
    (SettingsKeys.Database.CATEGORY, SettingsKeys.Database.POOL_RECYCLE_SECONDS): {"type": "int", "default": 3600, "min": 300, "max": 86400},

    # API Timeout Settings (seconds)
    (SettingsKeys.ApiTimeouts.CATEGORY, SettingsKeys.ApiTimeouts.OPENAI_TIMEOUT): {"type": "int", "default": 120, "min": 10, "max": 600},
    (SettingsKeys.ApiTimeouts.CATEGORY, SettingsKeys.ApiTimeouts.ELEVENLABS_TIMEOUT): {"type": "int", "default": 60, "min": 10, "max": 300},
    (SettingsKeys.ApiTimeouts.CATEGORY, SettingsKeys.ApiTimeouts.ELEVENLABS_DIALOGUE_TIMEOUT): {"type": "int", "default": 300, "min": 60, "max": 600},
    (SettingsKeys.ApiTimeouts.CATEGORY, SettingsKeys.ApiTimeouts.GITHUB_TIMEOUT): {"type": "int", "default": 180, "min": 30, "max": 600},
    (SettingsKeys.ApiTimeouts.CATEGORY, SettingsKeys.ApiTimeouts.GITHUB_UPLOAD_TIMEOUT): {"type": "int", "default": 180, "min": 60, "max": 600},
    (SettingsKeys.ApiTimeouts.CATEGORY, SettingsKeys.ApiTimeouts.HTTP_DEFAULT_TIMEOUT): {"type": "int", "default": 30, "min": 5, "max": 120},
    (SettingsKeys.ApiTimeouts.CATEGORY, SettingsKeys.ApiTimeouts.FFMPEG_TIMEOUT): {"type": "int", "default": 300, "min": 60, "max": 1800},
    (SettingsKeys.ApiTimeouts.CATEGORY, SettingsKeys.ApiTimeouts.AUDIO_DOWNLOAD_TIMEOUT): {"type": "int", "default": 300, "min": 60, "max": 1800},

    # TTS Settings
    (SettingsKeys.Tts.CATEGORY, SettingsKeys.Tts.RATE_LIMIT_DELAY): {"type": "float", "default": 1.0, "min": 0.0, "max": 10.0},

    # Discovery Settings
    (SettingsKeys.Discovery.CATEGORY, SettingsKeys.Discovery.MAX_ENTRIES_PER_FEED): {"type": "int", "default": 50, "min": 10, "max": 200},
    (SettingsKeys.Discovery.CATEGORY, SettingsKeys.Discovery.MAX_STORY_ARCS_CONTEXT): {"type": "int", "default": 20, "min": 5, "max": 50},
}


class WebConfigManager:
    def __init__(self):
        # Lazy import to avoid circular dependency
        from src.database.models import get_database_manager
        self.db_manager = get_database_manager()
        self._ensure_table()
        self._seed_defaults()

    def _ensure_table(self):
        # Table creation removed - web_settings table is managed via Alembic migrations
        # The create_all() query was hanging when database logging was enabled
        pass

    def _seed_defaults(self):
        with self.db_manager.get_session() as session:
            for (cat, key), meta in DEFAULTS.items():
                existing = session.query(WebSettingModel).filter(
                    WebSettingModel.category == cat,
                    WebSettingModel.setting_key == key
                ).first()
                if existing is None:
                    new_setting = WebSettingModel(
                        category=cat,
                        setting_key=key,
                        setting_value=str(meta["default"]),
                        value_type=meta["type"]
                    )
                    session.add(new_setting)
            session.commit()

    def get_setting(self, category: str, key: str, default: Any = None) -> Any:
        with self.db_manager.get_session() as session:
            setting = session.query(WebSettingModel).filter(
                WebSettingModel.category == category,
                WebSettingModel.setting_key == key
            ).first()
            if not setting:
                return default
            return self._cast_value(setting.setting_value, setting.value_type)

    def set_setting(self, category: str, key: str, value: Any) -> None:
        # Validate if we have a definition
        meta = DEFAULTS.get((category, key))
        vtype = meta["type"] if meta else self._infer_type(value)
        casted = self._coerce_and_validate(value, vtype, meta)

        with self.db_manager.get_session() as session:
            # Use upsert for PostgreSQL
            stmt = insert(WebSettingModel).values(
                category=category,
                setting_key=key,
                setting_value=str(casted),
                value_type=vtype,
                updated_at=datetime.now()
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=['category', 'setting_key'],
                set_={
                    'setting_value': stmt.excluded.setting_value,
                    'value_type': stmt.excluded.value_type,
                    'updated_at': stmt.excluded.updated_at
                }
            )
            session.execute(stmt)
            session.commit()

    def get_category(self, category: str) -> Dict[str, Any]:
        with self.db_manager.get_session() as session:
            settings = session.query(WebSettingModel).filter(
                WebSettingModel.category == category
            ).all()
            result = {}
            for setting in settings:
                result[setting.setting_key] = self._cast_value(setting.setting_value, setting.value_type)
            return result

    def _cast_value(self, raw: str, vtype: str) -> Any:
        try:
            if vtype == "int":
                return int(raw)
            if vtype == "float":
                return float(raw)
            if vtype == "bool":
                return str(raw).lower() in ("1", "true", "yes", "on")
            if vtype == "json":
                import json
                return json.loads(raw)
            return raw
        except Exception:
            return raw

    def _infer_type(self, value: Any) -> str:
        if isinstance(value, bool):
            return "bool"
        if isinstance(value, int):
            return "int"
        if isinstance(value, float):
            return "float"
        return "string"

    def _coerce_and_validate(self, value: Any, vtype: str, meta: Optional[Dict]) -> Any:
        # Coerce
        if vtype == "int":
            value = int(value)
        elif vtype == "float":
            value = float(value)
        elif vtype == "bool":
            value = bool(value)
        # Validate constraints
        if meta:
            mn = meta.get("min")
            mx = meta.get("max")
            if isinstance(value, (int, float)):
                if mn is not None and value < mn:
                    raise ValueError(f"{value} < min {mn}")
                if mx is not None and value > mx:
                    raise ValueError(f"{value} > max {mx}")
        return value

    def get_ai_models(self) -> Dict[str, Dict]:
        """Get available AI models and their limits"""
        return AI_MODELS

    def validate_model_limit(self, provider: str, model: str, limit_type: str, value: int) -> bool:
        """Validate if a limit value is within the model's capabilities"""
        if provider not in AI_MODELS or model not in AI_MODELS[provider]:
            return False

        model_info = AI_MODELS[provider][model]

        if provider in ('openai', 'anthropic'):
            if limit_type == 'max_output':
                return value <= model_info.get('max_output', 4096)
            elif limit_type == 'max_input':
                return value <= model_info.get('max_input', 16385)
        elif provider == 'elevenlabs':
            if limit_type == 'max_characters':
                return value <= model_info.get('max_characters', 10000)
        elif provider == 'whisper':
            if limit_type == 'max_file_size_mb':
                return value <= model_info.get('max_file_size_mb', 25)

        return True

    def get_model_limit(self, provider: str, model: str, limit_type: str) -> int:
        """Get the maximum limit for a specific model and limit type"""
        if provider not in AI_MODELS or model not in AI_MODELS[provider]:
            return 0

        model_info = AI_MODELS[provider][model]

        if provider in ('openai', 'anthropic'):
            if limit_type == 'max_output':
                return model_info.get('max_output', 4096)
            elif limit_type == 'max_input':
                return model_info.get('max_input', 16385)
        elif provider == 'elevenlabs':
            if limit_type == 'max_characters':
                return model_info.get('max_characters', 10000)
        elif provider == 'whisper':
            if limit_type == 'max_file_size_mb':
                return model_info.get('max_file_size_mb', 25)

        return 0

    def adjust_limit_for_model(self, category: str, model_key: str, limit_key: str, current_value: int) -> int:
        """Adjust a limit value when switching models to ensure it doesn't exceed new model's capabilities"""
        model_name = self.get_setting(category, model_key)
        if not model_name:
            return current_value

        # Determine provider based on category
        provider = None
        limit_type = None

        if 'content_scoring' in category or 'digest_generation' in category or 'metadata_generation' in category:
            # Determine provider from model name
            provider = 'anthropic' if model_name and model_name.startswith('claude-') else 'openai'
            if 'output' in limit_key:
                limit_type = 'max_output'
            else:
                limit_type = 'max_input'
        elif 'tts_generation' in category:
            provider = 'elevenlabs'
            limit_type = 'max_characters'
        elif 'stt_transcription' in category:
            provider = 'whisper'
            limit_type = 'max_file_size_mb'

        if provider and limit_type:
            max_limit = self.get_model_limit(provider, model_name, limit_type)
            return min(current_value, max_limit) if max_limit > 0 else current_value

        return current_value


class WebConfigReader:
    """
    Simple database configuration reader for pipeline scripts.
    Provides a lightweight interface to read web_settings without complex initialization.
    """

    def __init__(self):
        """Initialize with database connection"""
        self.web_config = WebConfigManager()

    def get_ai_scoring_config(self) -> Dict[str, Any]:
        """Get AI content scoring configuration for run_scoring.py"""
        return {
            'model': self.web_config.get_setting(SettingsKeys.AIContentScoring.CATEGORY, SettingsKeys.AIContentScoring.MODEL, 'gpt-5-mini'),
            'max_tokens': self.web_config.get_setting(SettingsKeys.AIContentScoring.CATEGORY, SettingsKeys.AIContentScoring.MAX_TOKENS, 1000),
            'max_episodes_per_batch': self.web_config.get_setting(SettingsKeys.AIContentScoring.CATEGORY, SettingsKeys.AIContentScoring.MAX_EPISODES_PER_BATCH, 10),
            'max_input_tokens': self.web_config.get_setting(SettingsKeys.AIContentScoring.CATEGORY, SettingsKeys.AIContentScoring.MAX_INPUT_TOKENS, 120000),
            'prompt_max_chars': self.web_config.get_setting(SettingsKeys.AIContentScoring.CATEGORY, SettingsKeys.AIContentScoring.PROMPT_MAX_CHARS, 4000)
        }

    def get_score_threshold(self) -> float:
        """Get content filtering score threshold"""
        return self.web_config.get_setting(SettingsKeys.ContentFiltering.CATEGORY, SettingsKeys.ContentFiltering.SCORE_THRESHOLD, 0.65)

    def get_min_episodes_per_digest(self) -> int:
        """Get minimum episodes required to generate a digest"""
        return self.web_config.get_setting(SettingsKeys.ContentFiltering.CATEGORY, SettingsKeys.ContentFiltering.MIN_EPISODES_PER_DIGEST, 1)

    def get_ai_digest_config(self) -> Dict[str, Any]:
        """Get AI digest generation configuration for run_digest.py"""
        return {
            'model': self.web_config.get_setting(SettingsKeys.AIDigestGeneration.CATEGORY, SettingsKeys.AIDigestGeneration.MODEL, 'gpt-5'),
            'max_output_tokens': self.web_config.get_setting(SettingsKeys.AIDigestGeneration.CATEGORY, SettingsKeys.AIDigestGeneration.MAX_OUTPUT_TOKENS, 25000),
            'max_input_tokens': self.web_config.get_setting(SettingsKeys.AIDigestGeneration.CATEGORY, SettingsKeys.AIDigestGeneration.MAX_INPUT_TOKENS, 150000),
            'transcript_buffer_percent': self.web_config.get_setting(SettingsKeys.AIDigestGeneration.CATEGORY, SettingsKeys.AIDigestGeneration.TRANSCRIPT_BUFFER_PERCENT, 20.0),
            'transcript_min_chars': self.web_config.get_setting(SettingsKeys.AIDigestGeneration.CATEGORY, SettingsKeys.AIDigestGeneration.TRANSCRIPT_MIN_CHARS, 2000),
            'transcript_max_chars': self.web_config.get_setting(SettingsKeys.AIDigestGeneration.CATEGORY, SettingsKeys.AIDigestGeneration.TRANSCRIPT_MAX_CHARS, 20000)
        }

    def get_ai_tts_config(self) -> Dict[str, Any]:
        """Get AI TTS generation configuration for run_tts.py"""
        return {
            'model': self.web_config.get_setting(SettingsKeys.AITTSGeneration.CATEGORY, SettingsKeys.AITTSGeneration.MODEL, 'eleven_turbo_v2_5'),
            'max_characters': self.web_config.get_setting(SettingsKeys.AITTSGeneration.CATEGORY, SettingsKeys.AITTSGeneration.MAX_CHARACTERS, 35000)
        }

    def get_audio_processing_config(self) -> Dict[str, Any]:
        """Get audio processing configuration for run_audio.py"""
        return {
            'chunk_duration_minutes': self.web_config.get_setting(SettingsKeys.AudioProcessing.CATEGORY, SettingsKeys.AudioProcessing.CHUNK_DURATION_MINUTES, 10),
            'transcribe_all_chunks': self.web_config.get_setting(SettingsKeys.AudioProcessing.CATEGORY, SettingsKeys.AudioProcessing.TRANSCRIBE_ALL_CHUNKS, True),
            'max_chunks_per_episode': self.web_config.get_setting(SettingsKeys.AudioProcessing.CATEGORY, SettingsKeys.AudioProcessing.MAX_CHUNKS_PER_EPISODE, 3),
            'stt_model': self.web_config.get_setting(SettingsKeys.AISTTTranscription.CATEGORY, SettingsKeys.AISTTTranscription.MODEL, 'whisper-1'),
            'max_file_size_mb': self.web_config.get_setting(SettingsKeys.AISTTTranscription.CATEGORY, SettingsKeys.AISTTTranscription.MAX_FILE_SIZE_MB, 20)
        }

    def get_pipeline_config(self) -> Dict[str, Any]:
        """Get general pipeline configuration"""
        return {
            'max_episodes_per_run': self.web_config.get_setting(SettingsKeys.Pipeline.CATEGORY, SettingsKeys.Pipeline.MAX_EPISODES_PER_RUN, 3),
            'discovery_lookback_days': self.web_config.get_setting(SettingsKeys.Pipeline.CATEGORY, SettingsKeys.Pipeline.DISCOVERY_LOOKBACK_DAYS, 3),
            'max_episodes_per_digest': self.web_config.get_setting(SettingsKeys.ContentFiltering.CATEGORY, SettingsKeys.ContentFiltering.MAX_EPISODES_PER_DIGEST, 5)
        }

    def get_transcript_processing_config(self) -> Dict[str, Any]:
        """Get transcript processing configuration"""
        return {
            'ad_trim_enabled': self.web_config.get_setting(SettingsKeys.TranscriptProcessing.CATEGORY, SettingsKeys.TranscriptProcessing.AD_TRIM_ENABLED, True),
            'ad_trim_start_percent': self.web_config.get_setting(SettingsKeys.TranscriptProcessing.CATEGORY, SettingsKeys.TranscriptProcessing.AD_TRIM_START_PERCENT, 5.0),
            'ad_trim_end_percent': self.web_config.get_setting(SettingsKeys.TranscriptProcessing.CATEGORY, SettingsKeys.TranscriptProcessing.AD_TRIM_END_PERCENT, 5.0)
        }
