"""Common test fixtures."""

import pytest

from src.core.config import AppConfig, LLMConfig, MemoryConfig, RAGConfig, ToolsConfig
from src.core.di_container import container as di_container

# Note: DIContainer is kept for type hints in fixture signatures
# ruff: noqa: F401

DIContainer = di_container.__class__  # type alias for fixtures


class MockLLMConfig:
    """Mock LLM config for testing."""

    model: str = "mock-model"
    temperature: float = 0.7
    max_tokens: int = 100


class MockLLM:
    """Mock LLM provider for testing."""

    def __init__(self):
        self.config = MockLLMConfig()

    async def generate(self, messages, **kwargs) -> str:
        return "This is a mock response."

    async def generate_with_usage(self, messages, **kwargs) -> tuple[str, dict]:
        """Generate response with token usage info."""
        return "This is a mock response.", {"input_tokens": 10, "output_tokens": 20}

    async def stream(self, messages, **kwargs):
        yield "This "
        yield "is "
        yield "a "
        yield "mock "
        yield "response."

    async def generate_structured(self, messages, output_schema, **kwargs) -> dict:
        schema_name = getattr(output_schema, "__name__", "")
        if schema_name == "RouterDecision":
            return {"agent": "chat", "reasoning": "Mock routing decision"}
        if schema_name == "ResearchToolDecision":
            return {"tools": [], "response_mode": "answer", "reasoning": "Mock tool decision"}
        return {}


class MockMemoryStore:
    """Mock memory store for testing."""

    def __init__(self):
        self._sessions: dict[str, list] = {}
        self._summaries: dict[str, str] = {}

    async def add_message(self, session_id: str, message: dict):
        """Add a message to memory."""
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        self._sessions[session_id].append(message)

    async def get_messages(self, session_id: str) -> list[dict]:
        """Get conversation history for a session."""
        return self._sessions.get(session_id, []).copy()

    async def clear(self, session_id: str = None):
        """Clear messages for a session or all sessions."""
        if session_id:
            self._sessions.pop(session_id, None)
            self._summaries.pop(session_id, None)
        else:
            self._sessions.clear()
            self._summaries.clear()

    async def get_messages_with_limit(
        self,
        session_id: str,
        max_tokens: int,
    ) -> list[dict]:
        """Get conversation history limited by token count."""
        messages = self._sessions.get(session_id, [])
        # Simple implementation: estimate ~4 chars per token
        result = []
        total_tokens = 0
        for msg in reversed(messages):
            msg_tokens = len(str(msg.get("content", ""))) // 4
            if total_tokens + msg_tokens > max_tokens:
                break
            result.insert(0, msg)
            total_tokens += msg_tokens
        return result

    async def add_summary(self, session_id: str, summary: str) -> None:
        """Add or update a conversation summary."""
        self._summaries[session_id] = summary

    async def get_summary(self, session_id: str) -> str | None:
        """Get the conversation summary for a session."""
        return self._summaries.get(session_id)

    async def get_conversation_history(self, session_id: str, limit: int = 10):
        """Get conversation history for a session."""
        messages = self._sessions.get(session_id, [])
        return messages[-limit:]


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
def test_container(test_config: AppConfig, mock_llm: MockLLM) -> DIContainer:
    """Create test container with mock dependencies."""
    # Use the global container with LLM override
    with di_container.llm.override(mock_llm):
        yield di_container
