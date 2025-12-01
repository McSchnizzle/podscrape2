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

# AI Model Definitions and Limits
AI_MODELS = {
    'openai': {
        'gpt-5.1': {'max_output': 128000, 'max_input': 400000, 'display_name': 'GPT-5.1'},
        'gpt-5': {'max_output': 128000, 'max_input': 272000, 'display_name': 'GPT-5'},
        'gpt-5-mini': {'max_output': 128000, 'max_input': 400000, 'display_name': 'GPT-5 Mini'},
        'gpt-5-nano': {'max_output': 64000, 'max_input': 128000, 'display_name': 'GPT-5 Nano'},
        'gpt-4-turbo-preview': {'max_output': 4096, 'max_input': 128000, 'display_name': 'GPT-4 Turbo'},
        'gpt-4o': {'max_output': 16384, 'max_input': 128000, 'display_name': 'GPT-4o'},
        'gpt-4o-mini': {'max_output': 16384, 'max_input': 128000, 'display_name': 'GPT-4o Mini'},
        'gpt-3.5-turbo': {'max_output': 4096, 'max_input': 16385, 'display_name': 'GPT-3.5 Turbo'}
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
    ("content_filtering", "score_threshold"): {"type": "float", "default": 0.65, "min": 0.0, "max": 1.0},
    ("content_filtering", "max_episodes_per_digest"): {"type": "int", "default": 5, "min": 1, "max": 20},
    ("content_filtering", "min_episodes_per_digest"): {"type": "int", "default": 1, "min": 0, "max": 10},
    ("audio_processing", "chunk_duration_minutes"): {"type": "int", "default": 10, "min": 1, "max": 30},
    ("audio_processing", "transcribe_all_chunks"): {"type": "bool", "default": True},
    ("audio_processing", "max_chunks_per_episode"): {"type": "int", "default": 3, "min": 1, "max": 50},
    ("pipeline", "max_episodes_per_run"): {"type": "int", "default": 3, "min": 1, "max": 20},
    ("pipeline", "discovery_lookback_days"): {"type": "int", "default": 3, "min": 1, "max": 30},
    # Retention policies (days)
    ("retention", "local_mp3_days"): {"type": "int", "default": 14, "min": 0, "max": 365},
    ("retention", "audio_cache_days"): {"type": "int", "default": 3, "min": 0, "max": 30},
    ("retention", "logs_days"): {"type": "int", "default": 3, "min": 0, "max": 365},
    ("retention", "episode_retention_days"): {"type": "int", "default": 14, "min": 8, "max": 365},
    ("retention", "digest_retention_days"): {"type": "int", "default": 14, "min": 8, "max": 365},
    ("retention", "github_releases_days"): {"type": "int", "default": 14, "min": 0, "max": 365},

    # AI Configuration - Content Scoring Phase
    ("ai_content_scoring", "model"): {"type": "string", "default": "gpt-5-mini"},
    ("ai_content_scoring", "max_tokens"): {"type": "int", "default": 1000, "min": 100, "max": 128000},
    ("ai_content_scoring", "max_episodes_per_batch"): {"type": "int", "default": 10, "min": 1, "max": 50},
    ("ai_content_scoring", "max_input_tokens"): {"type": "int", "default": 120000, "min": 1000, "max": 272000},
    ("ai_content_scoring", "prompt_max_chars"): {"type": "int", "default": 4000, "min": 0, "max": 200000},

    # AI Configuration - Digest Generation Phase
    ("ai_digest_generation", "model"): {"type": "string", "default": "gpt-5"},
    ("ai_digest_generation", "max_output_tokens"): {"type": "int", "default": 25000, "min": 1000, "max": 128000},
    ("ai_digest_generation", "max_input_tokens"): {"type": "int", "default": 150000, "min": 10000, "max": 272000},
    ("ai_digest_generation", "transcript_buffer_percent"): {"type": "float", "default": 20.0, "min": 0.0, "max": 95.0},
    ("ai_digest_generation", "transcript_min_chars"): {"type": "int", "default": 2000, "min": 0, "max": 500000},
    ("ai_digest_generation", "transcript_max_chars"): {"type": "int", "default": 20000, "min": 0, "max": 1000000},

    # AI Configuration - Metadata Generation Phase
    ("ai_metadata_generation", "model"): {"type": "string", "default": "gpt-5-mini"},
    ("ai_metadata_generation", "max_input_tokens"): {"type": "int", "default": 60000, "min": 1000, "max": 128000},
    ("ai_metadata_generation", "max_title_tokens"): {"type": "int", "default": 50, "min": 10, "max": 200},
    ("ai_metadata_generation", "max_summary_tokens"): {"type": "int", "default": 200, "min": 50, "max": 1000},
    ("ai_metadata_generation", "max_description_tokens"): {"type": "int", "default": 500, "min": 100, "max": 2000},

    # AI Configuration - TTS Generation Phase
    ("ai_tts_generation", "model"): {"type": "string", "default": "eleven_turbo_v2_5"},
    ("ai_tts_generation", "max_characters"): {"type": "int", "default": 35000, "min": 1000, "max": 40000},

    # AI Configuration - Speech-to-Text Phase
    ("ai_stt_transcription", "model"): {"type": "string", "default": "whisper-1"},
    ("ai_stt_transcription", "max_file_size_mb"): {"type": "int", "default": 20, "min": 1, "max": 25},

    # Transcript Processing Controls (scoring + digest ingestion)
    ("transcript_processing", "ad_trim_enabled"): {"type": "bool", "default": True},
    ("transcript_processing", "ad_trim_start_percent"): {"type": "float", "default": 5.0, "min": 0.0, "max": 50.0},
    ("transcript_processing", "ad_trim_end_percent"): {"type": "float", "default": 5.0, "min": 0.0, "max": 50.0},
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

        if provider == 'openai':
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

        if provider == 'openai':
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
            provider = 'openai'
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
            'model': self.web_config.get_setting('ai_content_scoring', 'model', 'gpt-5-mini'),
            'max_tokens': self.web_config.get_setting('ai_content_scoring', 'max_tokens', 1000),
            'max_episodes_per_batch': self.web_config.get_setting('ai_content_scoring', 'max_episodes_per_batch', 10),
            'max_input_tokens': self.web_config.get_setting('ai_content_scoring', 'max_input_tokens', 120000),
            'prompt_max_chars': self.web_config.get_setting('ai_content_scoring', 'prompt_max_chars', 4000)
        }

    def get_score_threshold(self) -> float:
        """Get content filtering score threshold"""
        return self.web_config.get_setting('content_filtering', 'score_threshold', 0.65)

    def get_min_episodes_per_digest(self) -> int:
        """Get minimum episodes required to generate a digest"""
        return self.web_config.get_setting('content_filtering', 'min_episodes_per_digest', 1)

    def get_ai_digest_config(self) -> Dict[str, Any]:
        """Get AI digest generation configuration for run_digest.py"""
        return {
            'model': self.web_config.get_setting('ai_digest_generation', 'model', 'gpt-5'),
            'max_output_tokens': self.web_config.get_setting('ai_digest_generation', 'max_output_tokens', 25000),
            'max_input_tokens': self.web_config.get_setting('ai_digest_generation', 'max_input_tokens', 150000),
            'transcript_buffer_percent': self.web_config.get_setting('ai_digest_generation', 'transcript_buffer_percent', 20.0),
            'transcript_min_chars': self.web_config.get_setting('ai_digest_generation', 'transcript_min_chars', 2000),
            'transcript_max_chars': self.web_config.get_setting('ai_digest_generation', 'transcript_max_chars', 20000)
        }

    def get_ai_tts_config(self) -> Dict[str, Any]:
        """Get AI TTS generation configuration for run_tts.py"""
        return {
            'model': self.web_config.get_setting('ai_tts_generation', 'model', 'eleven_turbo_v2_5'),
            'max_characters': self.web_config.get_setting('ai_tts_generation', 'max_characters', 35000)
        }

    def get_audio_processing_config(self) -> Dict[str, Any]:
        """Get audio processing configuration for run_audio.py"""
        return {
            'chunk_duration_minutes': self.web_config.get_setting('audio_processing', 'chunk_duration_minutes', 10),
            'transcribe_all_chunks': self.web_config.get_setting('audio_processing', 'transcribe_all_chunks', True),
            'max_chunks_per_episode': self.web_config.get_setting('audio_processing', 'max_chunks_per_episode', 3),
            'stt_model': self.web_config.get_setting('ai_stt_transcription', 'model', 'whisper-1'),
            'max_file_size_mb': self.web_config.get_setting('ai_stt_transcription', 'max_file_size_mb', 20)
        }

    def get_pipeline_config(self) -> Dict[str, Any]:
        """Get general pipeline configuration"""
        return {
            'max_episodes_per_run': self.web_config.get_setting('pipeline', 'max_episodes_per_run', 3),
            'discovery_lookback_days': self.web_config.get_setting('pipeline', 'discovery_lookback_days', 3),
            'max_episodes_per_digest': self.web_config.get_setting('content_filtering', 'max_episodes_per_digest', 5)
        }

    def get_transcript_processing_config(self) -> Dict[str, Any]:
        """Get transcript processing configuration"""
        return {
            'ad_trim_enabled': self.web_config.get_setting('transcript_processing', 'ad_trim_enabled', True),
            'ad_trim_start_percent': self.web_config.get_setting('transcript_processing', 'ad_trim_start_percent', 5.0),
            'ad_trim_end_percent': self.web_config.get_setting('transcript_processing', 'ad_trim_end_percent', 5.0)
        }
