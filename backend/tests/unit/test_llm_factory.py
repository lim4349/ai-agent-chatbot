"""Tests for LLM Factory."""

import pytest

from src.core.config import LLMConfig
from src.core.exceptions import ConfigurationError
from src.llm.factory import LLMFactory


class TestLLMFactory:
    """Test cases for LLM Factory."""

    def test_available_providers(self):
        """Test that providers are registered."""
        providers = LLMFactory.available_providers()
        assert "openai" in providers
        assert "anthropic" in providers
        assert "ollama" in providers

    def test_create_openai_provider(self):
        """Test creating OpenAI provider."""
        config = LLMConfig(
            provider="openai",
            model="gpt-4o-mini",
            openai_api_key="test-key",
        )
        provider = LLMFactory.create(config)
        assert provider.__class__.__name__ == "OpenAIProvider"

    def test_create_ollama_provider(self):
        """Test creating Ollama provider."""
        config = LLMConfig(
            provider="ollama",
            model="llama3.1:8b",
            base_url="http://localhost:11434",
        )
        provider = LLMFactory.create(config)
        assert provider.__class__.__name__ == "OllamaProvider"

    def test_unknown_provider_raises(self):
        """Test that unknown provider raises error."""
        config = LLMConfig(provider="unknown", model="x")
        with pytest.raises(ConfigurationError) as exc_info:
            LLMFactory.create(config)
        assert "Unknown LLM provider" in str(exc_info.value.message)
