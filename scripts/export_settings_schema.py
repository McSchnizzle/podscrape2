#!/usr/bin/env python3
"""Export web_settings schema for API consumption.

This script exports the DEFAULTS and AI_MODELS from web_config.py as JSON,
allowing the web UI to consume the single source of truth for settings defaults.
"""
import json
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config.web_config import DEFAULTS, AI_MODELS


def export_schema():
    """Export settings schema as JSON.

    Returns a dictionary with:
    - settings: Grouped by category, with type, default, min, max for each setting
    - ai_models: Available AI models and their limits
    """
    schema = {}
    for (category, key), meta in DEFAULTS.items():
        if category not in schema:
            schema[category] = {}
        schema[category][key] = {
            "type": meta["type"],
            "default": meta["default"],
            "min": meta.get("min"),
            "max": meta.get("max")
        }
    return {"settings": schema, "ai_models": AI_MODELS}


if __name__ == "__main__":
    print(json.dumps(export_schema()))
