"""
WebConfigManager: DB-backed settings for the Web UI.
Provides typed get/set with basic validation and integrates with the pipeline optionally.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path
from sqlalchemy import text, Column, Integer, String, DateTime, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import insert

from database.models import get_database_manager

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
    ("audio_processing", "chunk_duration_minutes"): {"type": "int", "default": 10, "min": 1, "max": 30},
    ("audio_processing", "transcribe_all_chunks"): {"type": "bool", "default": True},
    ("audio_processing", "max_chunks_per_episode"): {"type": "int", "default": 3, "min": 1, "max": 50},
    ("pipeline", "max_episodes_per_run"): {"type": "int", "default": 3, "min": 1, "max": 20},
    # Retention policies (days)
    ("retention", "local_mp3_days"): {"type": "int", "default": 7, "min": 0, "max": 365},
    ("retention", "audio_cache_days"): {"type": "int", "default": 3, "min": 0, "max": 365},
    ("retention", "audio_chunks_days"): {"type": "int", "default": 1, "min": 0, "max": 365},
    ("retention", "logs_days"): {"type": "int", "default": 30, "min": 0, "max": 365},
    ("retention", "scripts_days"): {"type": "int", "default": 14, "min": 0, "max": 365},
    ("retention", "github_releases_days"): {"type": "int", "default": 14, "min": 0, "max": 365},
}


class WebConfigManager:
    def __init__(self):
        self.db_manager = get_database_manager()
        self._ensure_table()
        self._seed_defaults()

    def _ensure_table(self):
        # Create table using SQLAlchemy
        Base.metadata.create_all(self.db_manager.engine)

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
