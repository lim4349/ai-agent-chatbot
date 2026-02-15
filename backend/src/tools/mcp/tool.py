"""MCPTool wrapper that adapts MCP server tools to local Tool protocol."""

from typing import Any

from src.core.logging import get_logger

logger = get_logger(__name__)


class MCPTool:
    """Wraps a single MCP server tool to satisfy the Tool Protocol.

    The existing Tool Protocol requires:
        - name: str (property)
        - description: str (property)
        - execute(**kwargs) -> str (async method)

    MCPTool delegates execute() to MCPClient.call_tool().
    """

    def __init__(
        self,
        client,  # MCPClient instance
        tool_name: str,
        tool_description: str,
        input_schema: dict[str, Any] | None = None,
        prefix: str | None = None,
    ):
        # The registered name may be prefixed to avoid collisions:
        # e.g. "github_list_repos" if prefix="github" and tool_name="list_repos"
        self._registered_name = f"{prefix}_{tool_name}" if prefix else tool_name
        self._remote_name = tool_name  # Name as MCP server knows it
        self._description = tool_description
        self._input_schema = input_schema or {}
        self._client = client
        self._server_name = client.name

    @property
    def name(self) -> str:
        """Tool name as registered in ToolRegistry."""
        return self._registered_name

    @property
    def description(self) -> str:
        """Tool description from MCP server."""
        return self._description

    @property
    def input_schema(self) -> dict[str, Any]:
        """JSON Schema for tool input (from MCP server).

        Not part of the Tool Protocol, but useful for agents
        that want to validate arguments before calling.
        """
        return self._input_schema

    @property
    def server_name(self) -> str:
        """Name of the MCP server this tool belongs to."""
        return self._server_name

    async def execute(self, **kwargs) -> str:
        """Execute the tool by delegating to the MCP server.

        Args:
            **kwargs: Tool arguments (must match input_schema)

        Returns:
            Tool result as string.

        Raises:
            RuntimeError: If the MCP server call fails.
        """
        if not self._client.is_healthy:
            logger.warning(
                "mcp_tool_server_unhealthy",
                tool=self._registered_name,
                server=self._server_name,
            )
            return f"[MCP Error] Server '{self._server_name}' is currently unavailable."

        try:
            return await self._client.call_tool(self._remote_name, kwargs)
        except Exception as e:
            logger.error(
                "mcp_tool_execute_failed",
                tool=self._registered_name,
                server=self._server_name,
                error=str(e),
            )
            raise RuntimeError(f"MCP tool '{self._registered_name}' failed: {e}") from e
