"""FastAPI dependencies for DI."""

from src.core.config import AppConfig, get_config
from src.core.di_container import DIContainer, container

__all__ = ["get_config", "AppConfig", "DIContainer", "container"]
