"""Integration tests for the API.

Note: These tests require proper mock setup or API keys.
Running without mocks requires OPENAI_API_KEY or ANTHROPIC_API_KEY environment variable.
"""

import os

import pytest
from fastapi.testclient import TestClient

from src.api.dependencies import (
    get_cached_config,
    get_container,
)
from src.main import create_app

# Check if we have API keys available
HAS_API_KEY = bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))


@pytest.mark.skipif(not HAS_API_KEY, reason="Requires OPENAI_API_KEY or ANTHROPIC_API_KEY")
class TestChatAPI:
    """Integration tests for Chat API endpoints - requires API key."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        # Clear caches
        get_cached_config.cache_clear()
        get_container.cache_clear()

        app = create_app()
        with TestClient(app) as client:
            yield client

        # Cleanup
        get_cached_config.cache_clear()
        get_container.cache_clear()

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "llm_provider" in data
        assert "available_agents" in data

    def test_agents_endpoint(self, client):
        """Test agents list endpoint."""
        response = client.get("/api/v1/agents")

        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        agent_names = [a["name"] for a in data["agents"]]
        assert "supervisor" in agent_names
        assert "chat" in agent_names

    def test_clear_session(self, client):
        """Test session clearing endpoint."""
        # Clear a session (doesn't need to exist)
        response = client.delete("/api/v1/sessions/test-clear")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cleared"
