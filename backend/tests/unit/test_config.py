"""Tests for configuration parsing."""

from src.core.config import DEFAULT_LLM_MODEL, AppConfig
from src.utils.token_counter import DEFAULT_TOKEN_MODEL


def test_default_model_policy_uses_nvidia_free_model(monkeypatch):
    """App and token-counting defaults should use the same baseline model."""
    monkeypatch.delenv("LLM_MODEL", raising=False)
    config = AppConfig()

    assert config.llm.model == DEFAULT_LLM_MODEL
    assert DEFAULT_TOKEN_MODEL == DEFAULT_LLM_MODEL


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
