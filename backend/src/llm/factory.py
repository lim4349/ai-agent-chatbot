"""LLM Provider factory with decorator-based registration."""

from src.core.config import LLMConfig
from src.core.exceptions import ConfigurationError


class LLMFactory:
    """Decorator-based auto-registration factory.

    To add a new provider:
    1. Create llm/new_provider.py
    2. Apply @LLMFactory.register("new_name") decorator
    3. Set LLM_PROVIDER=new_name in .env

    No existing code modification needed.
    """

    _registry: dict[str, type] = {}

    @classmethod
    def register(cls, name: str):
        """Decorator to register a provider class."""

        def decorator(provider_cls: type) -> type:
            cls._registry[name] = provider_cls
            return provider_cls

        return decorator

    @classmethod
    def create(cls, config: LLMConfig):
        """Create a provider instance from configuration."""
        provider_cls = cls._registry.get(config.provider)
        if provider_cls is None:
            available = ", ".join(cls._registry.keys()) or "none registered"
            raise ConfigurationError(
                f"Unknown LLM provider: '{config.provider}'. Available: {available}"
            )
        return provider_cls(config)

    @classmethod
    def available_providers(cls) -> list[str]:
        """List all registered providers."""
        return list(cls._registry.keys())
