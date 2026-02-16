"""MCP HTTP/SSE client for communicating with MCP servers."""

from typing import Any

from src.core.logging import get_logger

logger = get_logger(__name__)


class MCPClient:
    """Client for a single MCP server over HTTP/SSE transport.

    Handles:
    - Tool discovery via tools/list
    - Tool execution via tools/call
    - Health checking
    - Connection lifecycle
    """

    def __init__(
        self,
        name: str,
        url: str,
        api_key: str | None = None,
        timeout: int = 30,
        tool_prefix: str | None = None,
    ):
        self.name = name
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.tool_prefix = tool_prefix
        self._client: Any | None = None
        self._healthy: bool = False
        self._tools_cache: list[dict] | None = None

    @property
    def is_healthy(self) -> bool:
        return self._healthy

    async def health_check(self) -> bool:
        """Check if MCP server is reachable.

        Returns:
            True if server responds, False otherwise.
        """
        try:
            # For HTTP/SSE, tools/list serves as health check
            await self.list_tools()
            self._healthy = True
            logger.debug("mcp_health_check_success", server=self.name, url=self.url)
            return True
        except Exception as e:
            self._healthy = False
            logger.warning(
                "mcp_health_check_failed",
                server=self.name,
                url=self.url,
                error=str(e),
            )
            return False

    async def list_tools(self) -> list[dict]:
        """Discover available tools from MCP server.

        Returns:
            List of tool descriptors: [{"name": str, "description": str, "inputSchema": dict}]

        Raises:
            RuntimeError: If server is unreachable or returns invalid data.
        """
        if self._tools_cache is not None:
            return self._tools_cache

        try:
            # Simple HTTP client using urllib (avoid extra dependency)
            import json
            import urllib.request

            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            data = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
            encoded_data = json.dumps(data).encode("utf-8")

            req = urllib.request.Request(
                f"{self.url}/mcp/v1/tools/list",
                data=encoded_data,
                headers=headers,
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                response_data = json.load(response)

            tools = response_data.get("result", {}).get("tools", [])
            self._tools_cache = tools

            logger.info(
                "mcp_tools_discovered",
                server=self.name,
                tool_count=len(tools),
                tool_names=[t.get("name") for t in tools],
            )
            return tools

        except Exception as e:
            logger.error("mcp_list_tools_failed", server=self.name, error=str(e))
            raise RuntimeError(
                f"Failed to discover tools from MCP server '{self.name}': {e}"
            ) from e

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool on the MCP server.

        Args:
            tool_name: The tool name (without prefix, as MCP server knows it)
            arguments: Tool arguments matching tool's inputSchema

        Returns:
            Tool result as a string.

        Raises:
            RuntimeError: If execution fails.
        """
        logger.info(
            "mcp_tool_calling",
            server=self.name,
            tool=tool_name,
            arguments_keys=list(arguments.keys()),
        )

        try:
            import json
            import urllib.request

            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            data = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            }
            encoded_data = json.dumps(data).encode("utf-8")

            req = urllib.request.Request(
                f"{self.url}/mcp/v1/tools/call",
                data=encoded_data,
                headers=headers,
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                response_data = json.load(response)

            # MCP tools/call returns {"result": {"content": [{"type":"text","text":"..."}]}}
            result = response_data.get("result", {})
            content_parts = result.get("content", [])

            # Concatenate all text content parts
            text_parts = [
                part.get("text", "") for part in content_parts if part.get("type") == "text"
            ]
            result_text = "\n".join(text_parts)

            is_error = result.get("isError", False)
            if is_error:
                logger.warning(
                    "mcp_tool_returned_error",
                    server=self.name,
                    tool=tool_name,
                    result=result_text[:200],
                )
            else:
                logger.info(
                    "mcp_tool_completed",
                    server=self.name,
                    tool=tool_name,
                    result_length=len(result_text),
                )

            return result_text

        except Exception as e:
            logger.error("mcp_tool_call_failed", server=self.name, tool=tool_name, error=str(e))
            raise RuntimeError(f"MCP tool '{tool_name}' on server '{self.name}' failed: {e}") from e

    def invalidate_cache(self) -> None:
        """Clear cached tool list (force re-discovery on next call)."""
        self._tools_cache = None

    async def close(self) -> None:
        """Close HTTP client (no-op for urllib)."""
        self._client = None
        logger.debug("mcp_client_closed", server=self.name)
