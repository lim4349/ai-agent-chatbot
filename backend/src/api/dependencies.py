"""FastAPI dependencies for DI."""

from functools import lru_cache

from src.core.config import AppConfig, get_config
from src.core.di_container import DIContainer, container

__all__ = ["get_config", "get_cached_config", "get_container_dependency", "AppConfig", "DIContainer", "container"]


@lru_cache
def get_cached_config() -> AppConfig:
    """Get cached application config."""
    return get_config()


def get_container_dependency() -> DIContainer:
    """Get the DI container instance for FastAPI dependency injection."""
    return container
