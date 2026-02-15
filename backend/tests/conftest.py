"""Common test fixtures."""

import pytest

from src.core.config import AppConfig, LLMConfig, MemoryConfig, RAGConfig, ToolsConfig
from src.core.container import Container
from src.core.di_container import container as di_container


class MockLLM:
    """Mock LLM provider for testing."""

    async def generate(self, messages, **kwargs) -> str:
        return "This is a mock response."

    async def stream(self, messages, **kwargs):
        yield "This "
        yield "is "
        yield "a "
        yield "mock "
        yield "response."

    async def generate_structured(self, messages, output_schema, **kwargs) -> dict:
        # Return a valid routing decision by default
        if hasattr(output_schema, "__name__") and "Route" in output_schema.__name__:
            return {"selected_agent": "chat", "reasoning": "Mock routing decision"}
        return {}


class MockMemoryStore:
    """Mock memory store for testing."""

    def __init__(self):
        self._messages = []

    async def add_message(self, message):
        """Add a message to memory."""
        self._messages.append(message)

    async def get_messages(self, limit: int = 10):
        """Get recent messages."""
        return self._messages[-limit:]

    async def clear(self):
        """Clear all messages."""
        self._messages = []

    async def get_conversation_history(self, limit: int = 10):
        """Get conversation history."""
        return self._messages[-limit:]


@pytest.fixture
def test_config() -> AppConfig:
    """Create test configuration."""
    return AppConfig(
        debug=True,
        log_level="DEBUG",
        llm=LLMConfig(
            provider="openai",
            model="gpt-4o-mini",
            temperature=0.7,
            max_tokens=100,
        ),
        memory=MemoryConfig(backend="in_memory"),
        rag=RAGConfig(collection_name="test_documents"),
        tools=ToolsConfig(
            tavily_api_key=None,
            code_execution_enabled=False,
        ),
    )


@pytest.fixture
def mock_llm() -> MockLLM:
    """Create mock LLM provider."""
    return MockLLM()


@pytest.fixture
def mock_memory() -> MockMemoryStore:
    """Create mock memory store."""
    return MockMemoryStore()


@pytest.fixture
def di_container_fixture():
    """Provide the DI container for testing."""
    yield di_container


@pytest.fixture
def override_llm(mock_llm):
    """Override LLM provider in DI container."""
    with di_container.llm.override(mock_llm):
        yield


@pytest.fixture
def override_memory(mock_memory):
    """Override memory store in DI container."""
    with di_container.memory.override(mock_memory):
        yield


@pytest.fixture
def test_container(test_config: AppConfig, mock_llm: MockLLM) -> Container:
    """Create test container with mock dependencies (legacy container)."""
    container = Container(config=test_config)
    return container.override(llm_override=mock_llm)
