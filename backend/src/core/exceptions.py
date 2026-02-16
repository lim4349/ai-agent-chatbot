"""Custom exception hierarchy."""

from typing import Any


class AppError(Exception):
    """Base application exception."""

    def __init__(self, message: str, code: str = "INTERNAL_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
            }
        }


class LLMError(AppError):
    """LLM communication error."""

    def __init__(self, message: str, provider: str):
        self.provider = provider
        super().__init__(message, code="LLM_ERROR")

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result["error"]["details"] = {"provider": self.provider}
        return result


class AgentError(AppError):
    """Agent execution error."""

    def __init__(self, message: str, agent_name: str):
        self.agent_name = agent_name
        super().__init__(message, code="AGENT_ERROR")

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result["error"]["details"] = {"agent": self.agent_name}
        return result


class ToolExecutionError(AppError):
    """Tool execution error."""

    def __init__(self, message: str, tool_name: str):
        self.tool_name = tool_name
        super().__init__(message, code="TOOL_ERROR")

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result["error"]["details"] = {"tool": self.tool_name}
        return result


class ConfigurationError(AppError):
    """Configuration error."""

    def __init__(self, message: str):
        super().__init__(message, code="CONFIG_ERROR")


class MCPError(AppError):
    """MCP server communication error."""

    def __init__(self, message: str, server_name: str):
        self.server_name = server_name
        super().__init__(message, code="MCP_ERROR")

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result["error"]["details"] = {"mcp_server": self.server_name}
        return result
