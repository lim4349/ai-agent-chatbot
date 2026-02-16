"""Tool registry for managing agent tools."""

from typing import Any

from src.core.logging import get_logger

logger = get_logger(__name__)


class ToolRegistry:
    """Registry for managing tools by name."""

    def __init__(self) -> None:
        self._tools: dict[str, Any] = {}

    def register(self, tool: Any) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
        logger.debug("tool_registered", name=tool.name)

    def get(self, name: str) -> Any:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def has_tool(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    def unregister(self, name: str) -> bool:
        """Unregister a tool by name."""
        if name in self._tools:
            del self._tools[name]
            logger.debug("tool_unregistered", name=name)
            return True
        return False
