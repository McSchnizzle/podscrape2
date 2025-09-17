"""Tests for environment configuration utilities.
These tests validate environment variable handling without external dependencies.
"""

from __future__ import annotations

import importlib
import os
import sys
import types
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _restore_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure environment variables related to database config are cleared before each test."""
    for key in ("DATABASE_URL", "SUPABASE_DB_URL", "SUPABASE_URL", "SUPABASE_PASSWORD"):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def env_module(monkeypatch: pytest.MonkeyPatch):
    """Import the env module with a stubbed dotenv dependency."""
    stub = types.ModuleType("dotenv")
    stub.load_dotenv = lambda *args, **kwargs: None  # type: ignore[assignment]
    monkeypatch.setitem(sys.modules, "dotenv", stub)

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]))

    if "src.config.env" in sys.modules:
        module = importlib.reload(sys.modules["src.config.env"])
    else:
        module = importlib.import_module("src.config.env")
    return module


def test_require_env_success(monkeypatch: pytest.MonkeyPatch, env_module) -> None:
    """require_env should pass when all variables are set."""
    monkeypatch.setenv("EXAMPLE_KEY", "value")

    env_module.require_env(["EXAMPLE_KEY"])


def test_require_env_failure(env_module) -> None:
    """require_env should raise MissingEnvError listing the missing variables."""
    with pytest.raises(env_module.MissingEnvError) as exc:
        env_module.require_env(["A", "B"])

    message = str(exc.value)
    assert "A" in message
    assert "B" in message


def test_require_database_url_prefers_direct_value(monkeypatch: pytest.MonkeyPatch, env_module) -> None:
    """DATABASE_URL should take precedence over other variables."""
    direct_url = "postgresql+psycopg://user:pass@host:5432/db"
    monkeypatch.setenv("DATABASE_URL", direct_url)
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql+psycopg://ignored")

    result = env_module.require_database_url()

    assert result == direct_url


def test_require_database_url_uses_supabase_db_url(monkeypatch: pytest.MonkeyPatch, env_module) -> None:
    """SUPABASE_DB_URL should be used when DATABASE_URL is absent."""
    supabase_direct = "postgresql+psycopg://postgres:pw@db.example.supabase.co:5432/postgres?sslmode=require"
    monkeypatch.setenv("SUPABASE_DB_URL", supabase_direct)

    result = env_module.require_database_url()

    assert result == supabase_direct


def test_require_database_url_constructs_from_supabase(monkeypatch: pytest.MonkeyPatch, env_module) -> None:
    """SUPABASE_URL and SUPABASE_PASSWORD should build a pooled connection string."""
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_PASSWORD", "secret")

    result = env_module.require_database_url()

    expected = (
        "postgresql+psycopg://postgres:secret@db.project.supabase.co:5432/postgres?sslmode=require"
    )
    assert result == expected
    assert os.getenv("DATABASE_URL") == expected


def test_require_database_url_from_postgres_url(monkeypatch: pytest.MonkeyPatch, env_module) -> None:
    """A direct Postgres URL in SUPABASE_URL should be normalized to psycopg with sslmode."""
    monkeypatch.setenv(
        "SUPABASE_URL",
        "postgresql://postgres:secret@db.project.supabase.co:5432/postgres",
    )
    monkeypatch.setenv("SUPABASE_PASSWORD", "unused")

    result = env_module.require_database_url()

    assert result == (
        "postgresql+psycopg://postgres:secret@db.project.supabase.co:5432/postgres?sslmode=require"
    )


def test_require_database_url_requires_values(env_module) -> None:
    """Missing configuration should raise MissingEnvError."""
    with pytest.raises(env_module.MissingEnvError):
        env_module.require_database_url()


def test_strip_quotes_handles_edges(env_module) -> None:
    """Ensure quotes and stray trailing characters are removed consistently."""
    cases = {
        '"quoted"': "quoted",
        "'single'": "single",
        'trailing"': "trailing",
        " spaced ": "spaced",
    }
    for raw, expected in cases.items():
        assert env_module._strip_quotes(raw) == expected


def test_build_from_supabase_env_handles_invalid_host(monkeypatch: pytest.MonkeyPatch, env_module) -> None:
    """Invalid SUPABASE_URL values should return None."""
    monkeypatch.setenv("SUPABASE_URL", "https://example.com")
    monkeypatch.setenv("SUPABASE_PASSWORD", "pw")

    helper = getattr(env_module, "_build_from_supabase_env")
    assert helper() is None
