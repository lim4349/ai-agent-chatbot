"""Tests for configuration parsing."""

from src.core.config import AppConfig


def test_debug_accepts_release_string(monkeypatch):
    """Hosting environments may expose DEBUG=release."""
    monkeypatch.setenv("DEBUG", "release")

    config = AppConfig()

    assert config.debug is False


def test_debug_accepts_development_string(monkeypatch):
    """Development-style string values should map to debug mode."""
    monkeypatch.setenv("DEBUG", "development")

    config = AppConfig()

    assert config.debug is True
