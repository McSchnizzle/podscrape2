"""
WebConfigManager: DB-backed settings for the Web UI.
Provides typed get/set with basic validation and integrates with the pipeline optionally.
"""

import sqlite3
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path

from database.models import get_database_manager


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
    def __init__(self, db_path: Optional[str] = None):
        self.db_manager = get_database_manager(db_path)
        self._ensure_table()
        self._seed_defaults()

    def _ensure_table(self):
        with self.db_manager.get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS web_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    setting_key TEXT NOT NULL,
                    setting_value TEXT NOT NULL,
                    value_type TEXT NOT NULL DEFAULT 'string',
                    description TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(category, setting_key)
                )
                """
            )

    def _seed_defaults(self):
        with self.db_manager.get_connection() as conn:
            for (cat, key), meta in DEFAULTS.items():
                cur = conn.execute(
                    "SELECT setting_value FROM web_settings WHERE category=? AND setting_key=?",
                    (cat, key),
                )
                if cur.fetchone() is None:
                    conn.execute(
                        "INSERT INTO web_settings (category, setting_key, setting_value, value_type) VALUES (?,?,?,?)",
                        (cat, key, str(meta["default"]), meta["type"]),
                    )
                    conn.commit()

    def get_setting(self, category: str, key: str, default: Any = None) -> Any:
        with self.db_manager.get_connection() as conn:
            cur = conn.execute(
                "SELECT setting_value, value_type FROM web_settings WHERE category=? AND setting_key=?",
                (category, key),
            )
            row = cur.fetchone()
            if not row:
                return default
            raw, vtype = row[0], row[1]
            return self._cast_value(raw, vtype)

    def set_setting(self, category: str, key: str, value: Any) -> None:
        # Validate if we have a definition
        meta = DEFAULTS.get((category, key))
        vtype = meta["type"] if meta else self._infer_type(value)
        casted = self._coerce_and_validate(value, vtype, meta)
        with self.db_manager.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO web_settings (category, setting_key, setting_value, value_type, updated_at)
                VALUES (?,?,?,?,?)
                ON CONFLICT(category, setting_key)
                DO UPDATE SET setting_value=excluded.setting_value, value_type=excluded.value_type, updated_at=excluded.updated_at
                """,
                (category, key, str(casted), vtype, datetime.now().isoformat()),
            )
            conn.commit()

    def get_category(self, category: str) -> Dict[str, Any]:
        with self.db_manager.get_connection() as conn:
            cur = conn.execute(
                "SELECT setting_key, setting_value, value_type FROM web_settings WHERE category=?",
                (category,),
            )
            result = {}
            for key, val, vtype in cur.fetchall():
                result[key] = self._cast_value(val, vtype)
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
