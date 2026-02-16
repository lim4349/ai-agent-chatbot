"""Application configuration using pydantic-settings."""

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env file from project root
_project_root = Path(__file__).parent.parent.parent
_env_file = _project_root / ".env"
if _env_file.exists():
    load_dotenv(_env_file)


class LLMConfig(BaseSettings):
    """LLM provider configuration."""

    provider: str = "openai"
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 4096
    base_url: str | None = None

    # API keys (used based on provider)
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    model_config = SettingsConfigDict(env_prefix="LLM_")


class MemoryConfig(BaseSettings):
    """Memory store configuration."""

    backend: str = "in_memory"
    redis_url: str = "redis://localhost:6379/0"
    ttl_seconds: int = 3600

    model_config = SettingsConfigDict(env_prefix="MEMORY_")


class RAGConfig(BaseSettings):
    """RAG pipeline configuration."""

    collection_name: str = "documents"
    embedding_provider: str = "pinecone"  # 'openai' or 'pinecone'
    embedding_model: str = "multilingual-e5-large"
    chunk_size: int = 500
    chunk_overlap: int = 50
    top_k: int = 3
    chunking_strategy: str = "auto"

    # Pinecone settings (ChromaDB deprecated)
    pinecone_api_key: str | None = None
    pinecone_index_name: str = "documents"
    pinecone_namespace: str = "default"

    # Deprecated: ChromaDB connection settings (use Pinecone instead)
    chroma_host: str | None = None
    chroma_port: int = 8000
    chroma_token: str | None = None

    model_config = SettingsConfigDict(env_prefix="RAG_")


class ToolsConfig(BaseSettings):
    """External tools configuration."""

    tavily_api_key: str | None = None
    code_execution_enabled: bool = True
    code_execution_timeout: int = 10

    model_config = SettingsConfigDict(env_prefix="TOOLS_")


class MCPConfig(BaseSettings):
    """MCP (Model Context Protocol) server configuration."""

    enabled: bool = False
    servers_json: str = "[]"
    default_timeout: int = 30
    health_check_enabled: bool = True

    @property
    def servers(self) -> list[dict]:
        """Parse servers from JSON string."""
        import json

        try:
            raw = json.loads(self.servers_json)
            return raw if isinstance(raw, list) else []
        except json.JSONDecodeError:
            return []


class SupabaseConfig(BaseSettings):
    """Supabase authentication configuration."""

    url: str | None = None
    service_key: str | None = None

    model_config = SettingsConfigDict(env_prefix="SUPABASE_")


class AppConfig(BaseSettings):
    """Top-level application configuration."""

    app_name: str = "AI Agent Chatbot"
    debug: bool = False
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list = Field(default_factory=lambda: ["*"])

    llm: LLMConfig = Field(default_factory=LLMConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    supabase: SupabaseConfig = Field(default_factory=SupabaseConfig)

    model_config = SettingsConfigDict(env_file=str(_env_file), env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_config() -> AppConfig:
    """Get cached application configuration."""
    return AppConfig()
