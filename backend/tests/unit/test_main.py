"""Tests for application startup helpers."""

import os

import pytest
from langsmith import utils as langsmith_utils

from src.core.config import AppConfig, ObservabilityConfig
from src.main import _setup_langsmith_tracing

_LANGSMITH_ENV_KEYS = (
    "LANGSMITH_TRACING",
    "LANGSMITH_API_KEY",
    "LANGSMITH_PROJECT",
    "LANGCHAIN_TRACING_V2",
    "LANGCHAIN_API_KEY",
    "LANGCHAIN_PROJECT",
)


@pytest.fixture(autouse=True)
def clear_langsmith_env_cache():
    """Prevent cached LangSmith env lookups from leaking across tests."""
    langsmith_utils.get_env_var.cache_clear()
    langsmith_utils.get_tracer_project.cache_clear()
    yield
    langsmith_utils.get_env_var.cache_clear()
    langsmith_utils.get_tracer_project.cache_clear()


def test_setup_langsmith_tracing_sets_current_and_legacy_env(monkeypatch):
    """Startup should configure LangSmith using both current and legacy env names."""
    for key in _LANGSMITH_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    config = AppConfig(
        observability=ObservabilityConfig(
            langsmith_tracing=True,
            langsmith_api_key="test-key",
            langsmith_project="test-project",
        )
    )

    _setup_langsmith_tracing(config)

    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_API_KEY"] == "test-key"
    assert os.environ["LANGSMITH_PROJECT"] == "test-project"
    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
    assert os.environ["LANGCHAIN_API_KEY"] == "test-key"
    assert os.environ["LANGCHAIN_PROJECT"] == "test-project"
    assert langsmith_utils.tracing_is_enabled() is True


def test_setup_langsmith_tracing_clears_cached_disabled_env(monkeypatch):
    """A stale disabled lookup should not keep tracing off after startup setup."""
    for key in _LANGSMITH_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    assert langsmith_utils.tracing_is_enabled() is False

    config = AppConfig(
        observability=ObservabilityConfig(
            langsmith_tracing=True,
            langsmith_api_key="test-key",
            langsmith_project="test-project",
        )
    )

    _setup_langsmith_tracing(config)

    assert langsmith_utils.tracing_is_enabled() is True
