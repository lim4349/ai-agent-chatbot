"""Factory for creating memory store instances."""

from src.core.config import MemoryConfig
from src.core.protocols import MemoryStore


class MemoryStoreFactory:
    """Factory for creating memory store instances using registry pattern."""

    _registry: dict[str, type[MemoryStore]] = {}

    @classmethod
    def register(cls, backend: str):
        """Decorator to register a memory store implementation.

        Usage:
            @MemoryStoreFactory.register("redis")
            class RedisStore(MemoryStore):
                ...
        """

        def decorator(store_cls: type) -> type:
            cls._registry[backend] = store_cls
            return store_cls

        return decorator

    @classmethod
    def create(cls, config: MemoryConfig) -> MemoryStore:
        """Create memory store from configuration.

        Args:
            config: Memory configuration

        Returns:
            MemoryStore instance

        Raises:
            ValueError: If backend is not registered
        """
        store_cls = cls._registry.get(config.backend)
        if store_cls is None:
            raise ValueError(
                f"Unknown memory backend: {config.backend}. Available: {list(cls._registry.keys())}"
            )

        # Create instance based on backend type
        if config.backend == "redis":
            return store_cls(config.redis_url, config.ttl_seconds)
        return store_cls()

    @classmethod
    def available_backends(cls) -> list[str]:
        """Get list of available backend names."""
        return list(cls._registry.keys())
