"""FastAPI dependencies for DI."""

from functools import lru_cache

from src.core.config import AppConfig, get_config
from src.core.container import Container


@lru_cache
def get_cached_config() -> AppConfig:
    """Get cached application config."""
    return get_config()


@lru_cache
def get_container() -> Container:
    """Get cached DI container."""
    return Container(config=get_cached_config())


# For testing - allows overriding the container
_container_override: Container | None = None


def set_container_override(container: Container | None) -> None:
    """Set container override (for testing)."""
    global _container_override
    _container_override = container


def clear_container_override() -> None:
    """Clear container override (for testing cleanup)."""
    global _container_override
    _container_override = None


def get_container_dependency() -> Container:
    """FastAPI dependency to get the container."""
    if _container_override:
        return _container_override
    return get_container()
