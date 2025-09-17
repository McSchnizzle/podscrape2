"""Tests for environment configuration utilities without requiring optional dependencies."""

import os
import sys
from pathlib import Path

import pytest

# Ensure the application source directory is importable without relying on repo-level conftest.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import env as env_config


@pytest.fixture(autouse=True)
def clear_relevant_env(monkeypatch):
    """Ensure database-related environment variables are cleared before each test."""
    keys = [
        "DATABASE_URL",
        "SUPABASE_DB_URL",
        "SUPABASE_URL",
        "SUPABASE_PASSWORD",
    ]
    for key in keys:
        monkeypatch.delenv(key, raising=False)


def test_require_env_missing(monkeypatch):
    """require_env should raise MissingEnvError when a key is absent or empty."""
    key = "TEST_REQUIRED_KEY"
    monkeypatch.delenv(key, raising=False)

    with pytest.raises(env_config.MissingEnvError) as exc:
        env_config.require_env([key])

    assert key in str(exc.value)


def test_require_env_present(monkeypatch):
    """require_env should succeed when the key is populated."""
    key = "TEST_PRESENT_KEY"
    monkeypatch.setenv(key, "value")

    # Should not raise
    env_config.require_env([key])


def test_require_database_url_direct(monkeypatch):
    """Direct DATABASE_URL values should be returned unchanged."""
    url = "postgresql+psycopg://user:pass@db.example.com:5432/main"
    monkeypatch.setenv("DATABASE_URL", url)

    resolved = env_config.require_database_url()

    assert resolved == url


def test_require_database_url_prefers_supabase_db_url(monkeypatch):
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
    # The helper normalizes DATABASE_URL for downstream code.
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


def test_require_database_url_rejects_missing_values():
    """Missing database configuration should raise MissingEnvError."""
    with pytest.raises(env_config.MissingEnvError):
        env_config.require_database_url()
