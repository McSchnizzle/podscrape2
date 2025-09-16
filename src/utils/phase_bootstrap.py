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
    # Set up environment variables
    from dotenv import load_dotenv
    load_dotenv()

    # Verify database URL is configured
    from src.config.env import require_database_url
    require_database_url()