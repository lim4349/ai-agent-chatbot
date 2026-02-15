"""MCPClientManager -- orchestrates MCP server connections and tool discovery."""

import asyncio

from src.core.logging import get_logger
from src.tools.mcp.client import MCPClient
from src.tools.mcp.config import MCPConfig, MCPServerConfig
from src.tools.mcp.tool import MCPTool

logger = get_logger(__name__)


class MCPClientManager:
    """Manages multiple MCP server connections.

    Responsibilities:
    - Create MCPClient instances from config
    - Run health checks
    - Discover tools from all servers
    - Create MCPTool wrappers
    - Graceful shutdown
    """

    def __init__(self, config: MCPConfig):
        self.config = config
        self._clients: dict[str, MCPClient] = {}

    def _create_client(self, server: MCPServerConfig) -> MCPClient:
        """Create an MCPClient from server config."""
        return MCPClient(
            name=server.get("name", "unknown"),
            url=server.get("url", ""),
            api_key=server.get("api_key"),
            timeout=server.get("timeout", self.config.default_timeout),
            tool_prefix=server.get("tool_prefix"),
        )

    async def initialize(self) -> None:
        """Initialize all configured MCP clients and run initial health checks.

        This is called once during Container initialization.
        Servers that fail health check are logged but not removed --
        they may become available later.
        """
        if not self.config.enabled:
            logger.info("mcp_disabled")
            return

        servers = self.config.servers
        if not servers:
            logger.info("mcp_no_servers_configured")
            return

        logger.info("mcp_initializing", server_count=len(servers))

        for server_config in servers:
            if server_config.get("enabled", True):
                client = self._create_client(server_config)
                self._clients[server_config.get("name")] = client

        # Run health checks in parallel
        if self.config.health_check_enabled:
            await self._run_health_checks()

    async def _run_health_checks(self) -> None:
        """Health check all servers concurrently."""
        tasks = {
            name: asyncio.create_task(client.health_check())
            for name, client in self._clients.items()
        }

        results = {}
        for name, task in tasks.items():
            try:
                results[name] = await task
            except Exception as e:
                results[name] = False
                logger.error("mcp_health_check_exception", server=name, error=str(e))

        healthy = [n for n, ok in results.items() if ok]
        unhealthy = [n for n, ok in results.items() if not ok]

        logger.info(
            "mcp_health_check_complete",
            healthy_count=len(healthy),
            unhealthy_count=len(unhealthy),
        )

    async def discover_tools(self) -> list[MCPTool]:
        """Discover tools from all healthy MCP servers.

        Returns:
            List of MCPTool wrappers ready for registration.
            Servers that fail discovery are skipped (graceful degradation).
        """
        all_tools: list[MCPTool] = []

        for name, client in self._clients.items():
            if not client.is_healthy:
                logger.warning("mcp_skipping_unhealthy_server", server=name)
                continue

            try:
                raw_tools = await client.list_tools()

                for tool_def in raw_tools:
                    mcp_tool = MCPTool(
                        client=client,
                        tool_name=tool_def.get("name", ""),
                        tool_description=tool_def.get("description", ""),
                        input_schema=tool_def.get("inputSchema", {}),
                        prefix=client.tool_prefix,
                    )
                    all_tools.append(mcp_tool)

            except Exception as e:
                logger.error(
                    "mcp_tool_discovery_failed",
                    server=name,
                    error=str(e),
                )
                # Continue with other servers (graceful degradation)
                continue

        logger.info(
            "mcp_discovery_complete",
            total_tools=len(all_tools),
            tool_names=[t.name for t in all_tools],
        )
        return all_tools

    async def refresh_tools(self) -> list[MCPTool]:
        """Re-discover tools from all servers (invalidate caches first).

        Useful for runtime refresh if MCP servers add/remove tools.
        """
        for client in self._clients.values():
            client.invalidate_cache()

        # Re-run health checks before discovery
        await self._run_health_checks()
        return await self.discover_tools()

    def get_client(self, server_name: str) -> MCPClient | None:
        """Get a specific MCP client by server name."""
        return self._clients.get(server_name)

    @property
    def server_names(self) -> list[str]:
        """List all configured server names."""
        return list(self._clients.keys())

    @property
    def healthy_servers(self) -> list[str]:
        """List servers that passed health check."""
        return [name for name, client in self._clients.items() if client.is_healthy]

    async def close(self) -> None:
        """Close all MCP clients. Called during application shutdown."""
        for name, client in self._clients.items():
            try:
                await client.close()
            except Exception as e:
                logger.error("mcp_client_close_error", server=name, error=str(e))
        self._clients.clear()
        logger.info("mcp_manager_closed")
