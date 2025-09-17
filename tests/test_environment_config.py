"""Tests for configuration environment validation."""

import importlib
import os

import pytest

from src.utils import config as config_module


def test_validate_environment_success(monkeypatch):
    """validate_environment should return True when all required vars are set."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-eleven")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

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


@pytest.fixture(autouse=True)
def restore_env(monkeypatch):
    """Restore environment variables after each test."""
    original = {key: os.getenv(key) for key in ["OPENAI_API_KEY", "ELEVENLABS_API_KEY", "GITHUB_TOKEN"]}
    yield
    for key, value in original.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
