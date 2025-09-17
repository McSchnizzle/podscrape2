"""Comprehensive tests for environment configuration utilities.

Consolidated from multiple reviewer contributions to eliminate duplication
while preserving unique test coverage.
"""

import importlib
import os
import sys
import types
from pathlib import Path

import pytest

from src.config import env as env_config
from src.utils import config as config_module


@pytest.fixture(autouse=True)
def clear_env_vars(monkeypatch):
    """Clear relevant environment variables before each test for isolation."""
    # Database-related variables
    database_keys = [
        "DATABASE_URL",
        "SUPABASE_DB_URL",
        "SUPABASE_URL",
        "SUPABASE_PASSWORD"
    ]
    # API keys
    api_keys = [
        "OPENAI_API_KEY",
        "ELEVENLABS_API_KEY",
        "GITHUB_TOKEN",
        "GITHUB_REPOSITORY"
    ]

    # Store originals for restoration
    original_values = {}
    for key in database_keys + api_keys:
        original_values[key] = os.getenv(key)
        monkeypatch.delenv(key, raising=False)

    yield

    # Restore original values
    for key, value in original_values.items():
        if value is not None:
            monkeypatch.setenv(key, value)


# =============================================================================
# Core Environment Variable Validation Tests
# =============================================================================

def test_require_env_missing():
    """require_env should raise MissingEnvError when a key is absent."""
    key = "TEST_REQUIRED_KEY"

    with pytest.raises(env_config.MissingEnvError) as exc:
        env_config.require_env([key])

    assert key in str(exc.value)


def test_require_env_present(monkeypatch):
    """require_env should succeed when the key is populated."""
    key = "TEST_PRESENT_KEY"
    monkeypatch.setenv(key, "value")

    # Should not raise
    env_config.require_env([key])


def test_require_env_multiple_missing():
    """require_env should list all missing variables in error."""
    with pytest.raises(env_config.MissingEnvError) as exc:
        env_config.require_env(["MISSING_A", "MISSING_B"])

    message = str(exc.value)
    assert "MISSING_A" in message
    assert "MISSING_B" in message


# =============================================================================
# Database URL Configuration Tests
# =============================================================================

def test_require_database_url_direct(monkeypatch):
    """Direct DATABASE_URL values should be returned unchanged."""
    url = "postgresql+psycopg://user:pass@db.example.com:5432/main"
    monkeypatch.setenv("DATABASE_URL", url)

    resolved = env_config.require_database_url()

    assert resolved == url


def test_require_database_url_prefers_database_url(monkeypatch):
    """DATABASE_URL should take precedence over SUPABASE_DB_URL."""
    direct_url = "postgresql+psycopg://user:pass@host:5432/db"
    monkeypatch.setenv("DATABASE_URL", direct_url)
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql+psycopg://ignored")

    result = env_config.require_database_url()

    assert result == direct_url


def test_require_database_url_uses_supabase_db_url(monkeypatch):
    """SUPABASE_DB_URL should be used when DATABASE_URL is absent."""
    url = "postgresql+psycopg://user:pass@db.supabase.co:5432/postgres"
    monkeypatch.setenv("SUPABASE_DB_URL", url)

    resolved = env_config.require_database_url()

    assert resolved == url


def test_require_database_url_constructs_from_supabase_env(monkeypatch):
    """SUPABASE_URL and SUPABASE_PASSWORD should build a valid DATABASE_URL."""
    monkeypatch.setenv("SUPABASE_URL", "https://project-ref.supabase.co")
    monkeypatch.setenv("SUPABASE_PASSWORD", "super-secret")

    resolved = env_config.require_database_url()

    expected = (
        "postgresql+psycopg://postgres:super-secret@db.project-ref.supabase.co:5432/postgres?sslmode=require"
    )
    assert resolved == expected
    # The helper normalizes DATABASE_URL for downstream code
    assert os.environ["DATABASE_URL"] == expected


def test_require_database_url_handles_quoted_supabase_url(monkeypatch):
    """Quotes around SUPABASE_URL should be stripped before constructing the URL."""
    monkeypatch.setenv("SUPABASE_URL", '"https://quoted.supabase.co"')
    monkeypatch.setenv("SUPABASE_PASSWORD", "secret")

    resolved = env_config.require_database_url()

    expected = (
        "postgresql+psycopg://postgres:secret@db.quoted.supabase.co:5432/postgres?sslmode=require"
    )
    assert resolved == expected


def test_require_database_url_from_postgres_url(monkeypatch):
    """A direct Postgres URL in SUPABASE_URL should be normalized to psycopg with sslmode."""
    monkeypatch.setenv(
        "SUPABASE_URL",
        "postgresql://postgres:secret@db.project.supabase.co:5432/postgres",
    )
    monkeypatch.setenv("SUPABASE_PASSWORD", "unused")

    result = env_config.require_database_url()

    assert result == (
        "postgresql+psycopg://postgres:secret@db.project.supabase.co:5432/postgres?sslmode=require"
    )


def test_require_database_url_requires_values():
    """Missing database configuration should raise MissingEnvError."""
    with pytest.raises(env_config.MissingEnvError):
        env_config.require_database_url()


def test_build_from_supabase_env_handles_invalid_host(monkeypatch):
    """Invalid SUPABASE_URL values should return None."""
    monkeypatch.setenv("SUPABASE_URL", "https://example.com")
    monkeypatch.setenv("SUPABASE_PASSWORD", "pw")

    helper = getattr(env_config, "_build_from_supabase_env")
    assert helper() is None


# =============================================================================
# Environment Loading and Validation Tests
# =============================================================================

def test_load_env_invokes_dotenv(monkeypatch):
    """load_env should invoke dotenv loading functionality."""
    called = {}

    def fake_load_dotenv(*args, **kwargs):
        called['invoked'] = True
        os.environ['TEST_ENV_VAR'] = 'value'
        return True

    # Mock the dotenv loading in env_config module
    import src.config.env as env_module
    monkeypatch.setattr(env_module, 'load_dotenv', fake_load_dotenv)

    env_config.load_env()

    assert called.get('invoked') is True
    assert os.environ['TEST_ENV_VAR'] == 'value'


def test_validate_environment_success(monkeypatch):
    """validate_environment should return True when all required vars are set."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-test")
    monkeypatch.setenv("GITHUB_TOKEN", "gh-test")

    importlib.reload(config_module)
    assert config_module.validate_environment() is True


def test_validate_environment_missing(monkeypatch, caplog):
    """validate_environment should return False and log missing vars."""
    for key in ["OPENAI_API_KEY", "ELEVENLABS_API_KEY", "GITHUB_TOKEN"]:
        monkeypatch.delenv(key, raising=False)

    importlib.reload(config_module)
    with caplog.at_level("ERROR"):
        assert config_module.validate_environment() is False
    assert "Missing required environment variables" in caplog.text


# =============================================================================
# API Key Loading Tests
# =============================================================================

def test_load_api_keys_defaults(monkeypatch):
    """load_api_keys should handle missing GITHUB_REPOSITORY with default."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-test")
    monkeypatch.setenv("GITHUB_TOKEN", "gh-test")
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)

    from src.utils.config import load_api_keys
    keys = load_api_keys()

    assert keys["openai_api_key"] == "sk-test"
    assert keys["elevenlabs_api_key"] == "el-test"
    assert keys["github_token"] == "gh-test"
    assert keys["github_repository"] == "McSchnizzle/podscrape2"


# =============================================================================
# Utility Function Tests
# =============================================================================

def test_strip_quotes_handles_edges():
    """Ensure quotes and stray trailing characters are removed consistently."""
    cases = {
        '"quoted"': "quoted",
        "'single'": "single",
        'trailing"': "trailing",
        " spaced ": "spaced",
    }
    for raw, expected in cases.items():
        assert env_config._strip_quotes(raw) == expected