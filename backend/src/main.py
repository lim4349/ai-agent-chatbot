"""FastAPI application entry point."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.dependencies import get_cached_config, get_container_dependency
from src.api.middleware import ExceptionHandlerMiddleware, RequestLoggingMiddleware
from src.api.routes import router as api_router
from src.core.di_container import container as di_container
from src.core.logging import setup_logging

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    config = get_cached_config()

    # Setup logging
    setup_logging(log_level=config.log_level, json_format=not config.debug)

    # Wire DI container
    di_container.wire(
        modules=[
            "src.api.routes",
            "src.agents.supervisor",
            "src.agents.chat_agent",
            "src.agents.code_agent",
            "src.agents.rag_agent",
            "src.agents.web_search_agent",
        ]
    )

    # Log startup
    logger.info(
        "application_starting",
        app_name=config.app_name,
        llm_provider=config.llm.provider,
        llm_model=config.llm.model,
        memory_backend=config.memory.backend,
    )

    # Initialize container (uses dependency to respect test overrides)
    container = get_container_dependency()

    # Initialize MCP tools
    mcp_manager = None
    if config.mcp.enabled:
        from src.tools.mcp.manager import MCPClientManager

        mcp_manager = MCPClientManager(config.mcp)
        await mcp_manager.initialize()
        tools = await mcp_manager.discover_tools()

        tool_registry = container.tool_registry()
        for tool in tools:
            if not tool_registry.has_tool(tool.name):
                tool_registry.register(tool)
                logger.info("mcp_tool_registered", tool=tool.name, server=tool.server_name)
            else:
                logger.warning("mcp_tool_name_conflict", tool_name=tool.name)

    logger.info(
        "container_initialized",
        llm_providers=type(container.llm()).__name__,
        available_tools=container.tool_registry().list_tools(),
    )

    yield

    # Unwire DI container
    di_container.unwire()

    # Cleanup
    if mcp_manager:
        await mcp_manager.close()

    logger.info("application_shutting_down")
    # Close Redis connection if needed
    memory = container.memory()
    if hasattr(memory, "close"):
        await memory.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    config = get_cached_config()

    app = FastAPI(
        title=config.app_name,
        description="LangGraph-based Multi-Agent Chatbot with extensible architecture",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Add middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(ExceptionHandlerMiddleware)

    # Include routers
    app.include_router(api_router, prefix="/api/v1")

    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "name": config.app_name,
            "version": "0.1.0",
            "docs": "/docs",
            "health": "/api/v1/health",
        }

    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    config = get_cached_config()
    uvicorn.run(
        "src.main:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
    )
