"""Tests for environment configuration utilities using provided env variables."""

import sys
import os
from pathlib import Path

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import src.config.env as env_module

from src.config.env import MissingEnvError, require_database_url, load_env
from src.utils.config import validate_environment, load_api_keys


def _clear_database_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove database-related environment variables to isolate scenarios."""
    for key in ["DATABASE_URL", "SUPABASE_DB_URL", "SUPABASE_URL", "SUPABASE_PASSWORD"]:
        monkeypatch.delenv(key, raising=False)


def test_require_database_url_prefers_database_url(monkeypatch):
    _clear_database_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://example/db")

    assert require_database_url() == "postgresql+psycopg://example/db"


def test_require_database_url_uses_supabase_db_url(monkeypatch):
    _clear_database_env(monkeypatch)
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql+psycopg://supabase/db")

    result = require_database_url()
    assert result == "postgresql+psycopg://supabase/db"


def test_require_database_url_constructs_from_supabase(monkeypatch):
    _clear_database_env(monkeypatch)
    monkeypatch.setenv("SUPABASE_URL", "https://abc123.supabase.co")
    monkeypatch.setenv("SUPABASE_PASSWORD", "secret")

    expected = "postgresql+psycopg://postgres:secret@db.abc123.supabase.co:5432/postgres?sslmode=require"
    assert require_database_url() == expected
    assert os.environ["DATABASE_URL"] == expected


def test_require_database_url_missing(monkeypatch):
    _clear_database_env(monkeypatch)

    with pytest.raises(MissingEnvError):
        require_database_url()


def test_load_env_invokes_dotenv(monkeypatch):
    called = {}

    def fake_load_dotenv(*args, **kwargs):
        called['invoked'] = True
        os.environ['TEST_ENV_VAR'] = 'value'
        return True

    monkeypatch.setattr(env_module, 'load_dotenv', fake_load_dotenv)

    load_env()

    assert called.get('invoked') is True
    assert os.environ['TEST_ENV_VAR'] == 'value'


def test_validate_environment_success(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-test")
    monkeypatch.setenv("GITHUB_TOKEN", "gh-test")

    assert validate_environment() is True


def test_validate_environment_missing(monkeypatch):
    for key in ["OPENAI_API_KEY", "ELEVENLABS_API_KEY", "GITHUB_TOKEN"]:
        monkeypatch.delenv(key, raising=False)

    assert validate_environment() is False


def test_load_api_keys_defaults(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-test")
    monkeypatch.setenv("GITHUB_TOKEN", "gh-test")
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)

    keys = load_api_keys()
    assert keys["openai_api_key"] == "sk-test"
    assert keys["elevenlabs_api_key"] == "el-test"
    assert keys["github_token"] == "gh-test"
    assert keys["github_repository"] == "McSchnizzle/podscrape2"
