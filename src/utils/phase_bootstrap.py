"""
Phase Bootstrap Helper - Common initialization logic for all phase scripts.
Provides consistent environment setup, path management, and configuration loading.
"""

import sys
from pathlib import Path

def bootstrap_phase():
    """
    Bootstrap common phase script initialization.

    Handles:
    - Environment variable loading from .env
    - Database URL requirement verification

    Note: sys.path setup should be done before calling this function
    """
    # Set up environment variables via centralized entry point
    from src.config.env import load_env, require_database_url
    load_env()

    # Verify database URL is configured
    require_database_url()