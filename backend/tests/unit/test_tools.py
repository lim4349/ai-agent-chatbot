"""Tests for tool implementations."""

import pytest

from src.tools.code_executor import CodeExecutorTool
from src.tools.registry import ToolRegistry


class TestToolRegistry:
    """Test cases for Tool Registry."""

    def test_register_tool(self):
        """Test registering a tool."""
        registry = ToolRegistry()
        tool = type("MockTool", (), {"name": "test", "description": "Test tool"})()
        registry.register(tool)

        assert registry.has_tool("test")
        assert registry.get("test") == tool

    def test_list_tools(self):
        """Test listing registered tools."""
        registry = ToolRegistry()
        tool1 = type("MockTool", (), {"name": "tool1", "description": "Tool 1"})()
        tool2 = type("MockTool", (), {"name": "tool2", "description": "Tool 2"})()
        registry.register(tool1)
        registry.register(tool2)

        tools = registry.list_tools()
        assert "tool1" in tools
        assert "tool2" in tools

    def test_unregister_tool(self):
        """Test unregistering a tool."""
        registry = ToolRegistry()
        tool = type("MockTool", (), {"name": "test", "description": "Test tool"})()
        registry.register(tool)

        result = registry.unregister("test")
        assert result is True
        assert not registry.has_tool("test")


class TestCodeExecutorTool:
    """Test cases for Code Executor Tool."""

    @pytest.mark.asyncio
    async def test_execute_simple_code(self):
        """Test executing simple Python code."""
        tool = CodeExecutorTool(timeout=5)
        result = await tool.execute("print('Hello, World!')")

        assert result["success"] is True
        assert "Hello, World!" in result["stdout"]

    @pytest.mark.asyncio
    async def test_block_dangerous_import(self):
        """Test that dangerous imports are blocked."""
        tool = CodeExecutorTool(timeout=5)
        result = await tool.execute("import os\nos.system('echo test')")

        assert result["success"] is False
        assert "__import__ not found" in result["stderr"]

    @pytest.mark.asyncio
    async def test_timeout(self):
        """Test that long-running code times out."""
        tool = CodeExecutorTool(timeout=1)
        result = await tool.execute("while True: pass")

        assert result["success"] is False
        assert "timed out" in result["stderr"]
