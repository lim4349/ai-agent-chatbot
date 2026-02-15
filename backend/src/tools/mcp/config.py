"""MCP server configuration."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MCPServerConfig(BaseSettings):
    """Configuration for a single MCP server."""

    name: str
    url: str  # e.g. "http://localhost:3001"
    transport: str = "sse"  # "sse" or "stdio"
    api_key: str | None = None  # Optional auth token
    timeout: int = 30  # Request timeout in seconds
    enabled: bool = True  # Toggle individual servers
    tool_prefix: str | None = None  # e.g. "github" -> "github_list_repos"
    health_check_interval: int = 60  # Seconds between health checks

    # stdio-specific (future)
    command: str | None = None  # e.g. "npx @modelcontextprotocol/server-github"
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)


class MCPConfig(BaseSettings):
    """Top-level MCP configuration.

    Env vars:
        MCP_ENABLED=true
        MCP_SERVERS_JSON='[{"name":"github","url":"http://localhost:3001"}]'
    """

    enabled: bool = False
    servers_json: str = "[]"  # JSON array of MCPServerConfig
    default_timeout: int = 30
    health_check_enabled: bool = True

    model_config = SettingsConfigDict(env_prefix="MCP_")

    @property
    def servers(self) -> list[dict]:
        """Parse servers from JSON string."""
        import json

        try:
            raw = json.loads(self.servers_json)
            return raw if isinstance(raw, list) else []
        except json.JSONDecodeError:
            return []
