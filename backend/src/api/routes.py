"""API routes for the chatbot."""

import json
import time
from datetime import UTC, datetime
from uuid import uuid4

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from langchain_core.messages import BaseMessage
from sse_starlette.sse import EventSourceResponse

from src.api.schemas import (
    AgentInfo,
    AgentListResponse,
    ChatRequest,
    ChatResponse,
    DocumentDeleteResponse,
    DocumentInfo,
    DocumentListResponse,
    DocumentUploadRequest,
    DocumentUploadResponse,
    FileUploadResponse,
    HealthResponse,
    MetricsSummaryResponse,
    RateLimitStatus,
    RateLimitStatusResponse,
    SessionCreate,
    SessionListResponse,
    SessionResponse,
)
from src.core.config import AppConfig, RateLimitConfig
from src.core.di_container import DIContainer
from src.core.logging import get_logger, log_request
from src.core.prompt_security import detect_injection, filter_llm_output, sanitize_for_llm
from src.core.protocols import (
    DocumentChunker,
    DocumentParser,
    DocumentRetriever,
    MemoryStore,
    SessionStore,
)
from src.core.validators import (
    ValidationError,
    sanitize_metadata,
    validate_file_upload,
    validate_json_size,
)
from src.documents.models import Document
from src.documents.pinecone_store import PineconeVectorStore
from src.graph.state import create_initial_state
from src.memory.long_term_memory import LongTermMemory
from src.tools.registry import ToolRegistry

logger = get_logger(__name__)

router = APIRouter()

# Rate limiting: session_id -> call_count (legacy per-session tracking)
_rate_limits: dict[str, int] = {}

# Global rate limit tracking (across all sessions)
_global_minute_count: int = 0
_global_minute_reset_at: datetime = datetime.now(tz=UTC)

_global_hour_count: int = 0
_global_hour_reset_at: datetime = datetime.now(tz=UTC)

_global_daily_count: int = 0
_global_daily_reset_at: datetime = datetime.now(tz=UTC)

_global_token_count: int = 0
_global_token_reset_at: datetime = datetime.now(tz=UTC)


def _reset_if_needed() -> None:
    """Reset global counters when their time windows have expired."""
    global _global_minute_count, _global_minute_reset_at
    global _global_hour_count, _global_hour_reset_at
    global _global_daily_count, _global_daily_reset_at
    global _global_token_count, _global_token_reset_at

    now = datetime.now(tz=UTC)

    if (now - _global_minute_reset_at).total_seconds() >= 60:
        _global_minute_count = 0
        _global_minute_reset_at = now

    if (now - _global_hour_reset_at).total_seconds() >= 3600:
        _global_hour_count = 0
        _global_hour_reset_at = now

    if (now - _global_daily_reset_at).total_seconds() >= 86400:
        _global_daily_count = 0
        _global_daily_reset_at = now
        _global_token_count = 0
        _global_token_reset_at = now


def check_rate_limit(session_id: str, config: RateLimitConfig) -> None:
    """Check if global rate limits have been exceeded and increment counters."""
    global _global_minute_count, _global_hour_count, _global_daily_count

    _reset_if_needed()

    if config.per_minute > 0 and _global_minute_count >= config.per_minute:
        raise HTTPException(
            status_code=429,
            detail=f"분당 최대 {config.per_minute}회 호출 가능합니다. 잠시 후 다시 시도해주세요.",
        )

    if config.per_hour > 0 and _global_hour_count >= config.per_hour:
        raise HTTPException(
            status_code=429,
            detail=f"시간당 최대 {config.per_hour}회 호출 가능합니다. 잠시 후 다시 시도해주세요.",
        )

    if config.daily_request_limit > 0 and _global_daily_count >= config.daily_request_limit:
        raise HTTPException(
            status_code=429,
            detail=(
                f"일일 최대 {config.daily_request_limit}회 호출 가능합니다. "
                "내일 다시 시도해주세요."
            ),
        )

    _global_minute_count += 1
    _global_hour_count += 1
    _global_daily_count += 1


def _track_token_usage(token_count: int, config: RateLimitConfig) -> None:
    """Track token usage from a chat response."""
    global _global_token_count

    _reset_if_needed()

    if token_count > 0:
        _global_token_count += token_count
        if config.token_limit > 0 and _global_token_count >= config.token_limit:
            logger.warning(
                "token_limit_reached",
                token_count=_global_token_count,
                token_limit=config.token_limit,
            )


def _build_rate_limit_status(config: RateLimitConfig) -> RateLimitStatusResponse:
    """Build current rate limit status from global counters."""
    from datetime import timedelta

    _reset_if_needed()

    def _make_status(limit: int, used: int, reset_at: datetime) -> RateLimitStatus | None:
        if limit == 0:
            return None
        remaining = max(0, limit - used)
        return RateLimitStatus(
            limit=limit,
            used=used,
            remaining=remaining,
            reset_at=reset_at.isoformat(),
        )

    minute_reset = _global_minute_reset_at + timedelta(seconds=60)
    hour_reset = _global_hour_reset_at + timedelta(seconds=3600)
    daily_reset = _global_daily_reset_at + timedelta(seconds=86400)

    return RateLimitStatusResponse(
        per_minute=_make_status(config.per_minute, _global_minute_count, minute_reset),
        per_hour=_make_status(config.per_hour, _global_hour_count, hour_reset),
        daily=_make_status(config.daily_request_limit, _global_daily_count, daily_reset),
        tokens=_make_status(config.token_limit, _global_token_count, daily_reset),
    )


def get_message_content(msg) -> str:
    """Extract content from a message (dict or LangChain message)."""
    if isinstance(msg, dict):
        return msg.get("content", "")
    if isinstance(msg, BaseMessage):
        return msg.content
    return str(msg)


@router.post("/chat", response_model=ChatResponse)
@inject
async def chat(
    request: ChatRequest,
    graph=Depends(Provide[DIContainer.graph]),  # noqa: B008
    vector_store: PineconeVectorStore = Depends(Provide[DIContainer.vector_store]),  # noqa: B008
    session_store: SessionStore = Depends(Provide[DIContainer.session_store]),  # noqa: B008
    tool_registry: ToolRegistry = Depends(Provide[DIContainer.tool_registry]),  # noqa: B008
    config: AppConfig = Depends(Provide[DIContainer.config]),  # noqa: B008
) -> ChatResponse:
    """Send a message and get a response (synchronous).

    The supervisor will route to the appropriate specialist agent.
    """
    # Rate limiting
    check_rate_limit(request.session_id, config.rate_limit)

    start_time = time.perf_counter()

    # Security: Check for prompt injection attacks
    injection = detect_injection(request.message)
    if injection:
        # Log the security event (with details for internal logging)
        log_request(
            method="POST",
            path="/api/v1/chat",
            session_id=request.session_id,
            user_message=request.message,
            duration_ms=0,
            status="blocked",
            error=f"Prompt injection detected: {injection['type']}",
        )
        # Generic error message to avoid revealing security details
        raise HTTPException(
            status_code=400,
            detail="Invalid request. Please try again with different input.",
        )

    # Security: Sanitize input for LLM
    sanitized_message = sanitize_for_llm(request.message)

    # Get device_id: prefer request parameter, then session store
    device_id = request.device_id
    has_docs = False
    if session_store:
        try:
            session = await session_store.get(request.session_id)
            if session:
                # Use session's user_id if request doesn't have device_id
                if not device_id:
                    device_id = session.user_id  # In guest mode, user_id is device_id
                if vector_store:
                    has_docs = await vector_store.has_documents_for_session(
                        device_id=device_id, session_id=request.session_id
                    )
        except Exception as e:
            log_request(
                method="POST",
                path="/api/v1/chat",
                session_id=request.session_id,
                user_message="[session_store unavailable]",
                duration_ms=0,
                status="warning",
                error=f"Session store error (continuing without session): {e}",
            )

    # Determine available agents for capability awareness
    available_agents = ["supervisor", "chat", "report"]
    if tool_registry.get("code_executor"):
        available_agents.append("code")
    if tool_registry.get("web_search"):
        available_agents.append("web_search")
    if vector_store:
        available_agents.append("rag")

    # Create initial state with sanitized message and device_id
    initial_state = create_initial_state(
        sanitized_message, request.session_id, device_id, available_agents
    )
    initial_state["has_documents"] = has_docs

    # Configure with thread ID for state persistence
    graph_config = {"configurable": {"thread_id": request.session_id}}

    try:
        # Execute graph
        result = await graph.ainvoke(initial_state, config=graph_config)

        # Extract response
        messages = result.get("messages", [])
        response_message = get_message_content(messages[-1]) if messages else ""

        # Security: Filter potential prompt leaks from output
        response_message = filter_llm_output(response_message)

        # Determine which agent actually processed the request
        # Use completed_steps (tracks actual processing agents) over next_agent (routing state)
        completed_steps = result.get("completed_steps", [])
        if completed_steps:
            agent_used = completed_steps[-1]  # Last agent that actually processed
        else:
            agent_used = result.get("next_agent", "chat")
            if agent_used == "done":
                agent_used = "chat"  # Default for greetings/simple responses

        duration_ms = (time.perf_counter() - start_time) * 1000

        # Log request/response (PII masking handled by logging module)
        log_request(
            method="POST",
            path="/api/v1/chat",
            session_id=request.session_id,
            user_message=sanitized_message,
            agent=agent_used,
            response=response_message,
            duration_ms=duration_ms,
            status="success",
        )

        return ChatResponse(
            message=response_message,
            session_id=request.session_id,
            agent_used=agent_used,
            route_reasoning=result.get("metadata", {}).get("route_reasoning"),
            tool_results=result.get("tool_results", []),
        )

    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        log_request(
            method="POST",
            path="/api/v1/chat",
            session_id=request.session_id,
            user_message=request.message,
            duration_ms=duration_ms,
            status="error",
            error=str(e),
        )
        raise HTTPException(status_code=500, detail="요청 처리 중 오류가 발생했습니다.") from e


@router.post("/chat/stream")
@inject
async def chat_stream(
    request: ChatRequest,
    graph=Depends(Provide[DIContainer.graph]),  # noqa: B008
    vector_store: PineconeVectorStore = Depends(Provide[DIContainer.vector_store]),  # noqa: B008
    session_store: SessionStore = Depends(Provide[DIContainer.session_store]),  # noqa: B008
    tool_registry: ToolRegistry = Depends(Provide[DIContainer.tool_registry]),  # noqa: B008
    config: AppConfig = Depends(Provide[DIContainer.config]),  # noqa: B008
):
    """Send a message and get a streaming response (SSE).

    Yields tokens as they are generated.
    """
    # Rate limiting
    check_rate_limit(request.session_id, config.rate_limit)

    # Security: Check for prompt injection attacks
    injection = detect_injection(request.message)
    if injection:
        # Log the security event (with details for internal logging)
        log_request(
            method="POST",
            path="/api/v1/chat/stream",
            session_id=request.session_id,
            user_message=request.message,
            duration_ms=0,
            status="blocked",
            error=f"Prompt injection detected: {injection['type']}",
        )

        # Return error as SSE event with generic message
        async def error_generator():
            yield {
                "event": "error",
                "data": json.dumps(
                    {"error": "Invalid request. Please try again with different input."}
                ),
            }

        return EventSourceResponse(error_generator())

    # Security: Sanitize input for LLM
    sanitized_message = sanitize_for_llm(request.message)

    # Get session to retrieve device_id
    device_id = None
    has_docs = False
    if session_store:
        try:
            session = await session_store.get(request.session_id)
            if session:
                device_id = session.user_id  # In guest mode, user_id is device_id
                if vector_store:
                    has_docs = await vector_store.has_documents_for_session(
                        device_id=device_id, session_id=request.session_id
                    )
        except Exception as e:
            log_request(
                method="POST",
                path="/api/v1/chat/stream",
                session_id=request.session_id,
                user_message="[session_store unavailable]",
                duration_ms=0,
                status="warning",
                error=f"Session store error (continuing without session): {e}",
            )

    # Determine available agents for capability awareness
    available_agents = ["supervisor", "chat", "report"]
    if tool_registry.get("code_executor"):
        available_agents.append("code")
    if tool_registry.get("web_search"):
        available_agents.append("web_search")
    if vector_store:
        available_agents.append("rag")

    # Create initial state with device_id
    initial_state = create_initial_state(
        sanitized_message, request.session_id, device_id, available_agents
    )
    initial_state["has_documents"] = has_docs

    graph_config = {"configurable": {"thread_id": request.session_id}}

    async def event_generator():
        try:
            # Yield metadata first
            yield {"event": "metadata", "data": json.dumps({"session_id": request.session_id})}

            # Nodes that use non-streaming LLM calls (ainvoke) — handled via on_chain_end
            # because ainvoke() does not emit on_chat_model_stream events
            non_streaming_nodes = {"code", "report"}
            # Track which nodes actually sent streaming tokens (for fallback detection)
            streamed_nodes: set[str] = set()
            # Track content sent to avoid duplicates
            sent_content_hashes: set[int] = set()
            # Track all agents that ran during this workflow
            all_agents: list[str] = []

            # Stream events from graph
            async for event in graph.astream_events(
                initial_state, config=graph_config, version="v2"
            ):
                kind = event.get("event")

                if kind == "on_chat_model_stream":
                    # Skip supervisor's structured output tokens (routing decision)
                    # Only stream tokens from actual response agents (chat, code, rag, web_search)
                    metadata = event.get("metadata", {})
                    langgraph_node = metadata.get("langgraph_node", "")
                    if langgraph_node == "supervisor":
                        continue
                    # code/report use non-streaming LLM calls; their output is sent via on_chain_end
                    if langgraph_node in non_streaming_nodes:
                        continue

                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content"):
                        content = chunk.content
                        if isinstance(content, list):
                            # Anthropic/Gemini via OpenRouter returns content as list of blocks
                            text = "".join(
                                block.get("text", "")
                                for block in content
                                if isinstance(block, dict) and block.get("type") == "text"
                            )
                        else:
                            text = content
                        if text:
                            streamed_nodes.add(langgraph_node)
                            yield {"event": "token", "data": text}

                elif kind == "on_chain_end":
                    node_name = event.get("name", "")
                    if node_name == "supervisor":
                        output = event.get("data", {}).get("output", {})
                        agent = output.get("next_agent", "chat")
                        # Track all agents that ran during workflow
                        if agent != "done" and agent not in all_agents:
                            all_agents.append(agent)
                            # Send agent event for UI updates during streaming
                            yield {"event": "agent", "data": json.dumps({"agent": agent, "all_agents": all_agents})}
                        # When workflow completes, send final agent list
                        elif agent == "done" and all_agents:
                            yield {"event": "agents_complete", "data": json.dumps({"agents": all_agents})}
                        # When supervisor responds directly (no specialist agent ran, e.g. greetings),
                        # send the response as a token — no specialist on_chain_end will fire
                        if agent == "done" and not output.get("completed_steps"):
                            messages = output.get("messages", [])
                            if messages:
                                last_msg = messages[-1]
                                content = (
                                    last_msg.get("content", "")
                                    if isinstance(last_msg, dict)
                                    else getattr(last_msg, "content", "")
                                )
                                if content:
                                    content_hash = hash(content[:100])
                                    if content_hash not in sent_content_hashes:
                                        sent_content_hashes.add(content_hash)
                                        yield {"event": "token", "data": content}
                    elif node_name in non_streaming_nodes:
                        # code/report: always send full response (includes exec output) via on_chain_end
                        output = event.get("data", {}).get("output", {})
                        messages = output.get("messages", [])
                        logger.info(
                            "routes_on_chain_end", node_name=node_name, message_count=len(messages)
                        )
                        if messages:
                            last_msg = messages[-1]
                            content = (
                                last_msg.get("content", "")
                                if isinstance(last_msg, dict)
                                else getattr(last_msg, "content", "")
                            )
                            if content:
                                content_hash = hash(content[:100])
                                logger.info(
                                    "routes_content_hash",
                                    node_name=node_name,
                                    content_hash=content_hash,
                                    already_sent=content_hash in sent_content_hashes,
                                )
                                if content_hash not in sent_content_hashes:
                                    sent_content_hashes.add(content_hash)
                                    yield {"event": "token", "data": content}
                    elif (
                        node_name in {"chat", "rag", "web_search"}
                        and node_name not in streamed_nodes
                    ):
                        # Fallback: if a normally-streaming node didn't stream, send its output now
                        output = event.get("data", {}).get("output", {})
                        messages = output.get("messages", [])
                        if messages:
                            last_msg = messages[-1]
                            content = (
                                last_msg.get("content", "")
                                if isinstance(last_msg, dict)
                                else getattr(last_msg, "content", "")
                            )
                            if content:
                                content_hash = hash(content[:100])
                                if content_hash not in sent_content_hashes:
                                    sent_content_hashes.add(content_hash)
                                    yield {"event": "token", "data": content}

            yield {"event": "done", "data": ""}

        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(event_generator())


@router.get("/health", response_model=HealthResponse)
@inject
async def health(
    config: AppConfig = Depends(Provide[DIContainer.config]),  # noqa: B008
    tool_registry: ToolRegistry = Depends(Provide[DIContainer.tool_registry]),  # noqa: B008
    retriever: DocumentRetriever | None = Depends(Provide[DIContainer.retriever]),  # noqa: B008
) -> HealthResponse:
    """Check service health and configuration."""
    # Determine available agents based on configuration
    available_agents = ["supervisor", "chat", "report"]
    if tool_registry.get("code_executor"):
        available_agents.append("code")
    if tool_registry.get("web_search"):
        available_agents.append("web_search")
    if retriever:
        available_agents.append("rag")

    return HealthResponse(
        status="ok",
        llm_provider=config.llm.provider,
        llm_model=config.llm.model,
        memory_backend=config.memory.backend,
        available_agents=available_agents,
        daily_request_limit=config.rate_limit.daily_request_limit,
        per_minute_limit=config.rate_limit.per_minute,
        per_hour_limit=config.rate_limit.per_hour,
        token_limit=config.rate_limit.token_limit,
        rate_limit_status=_build_rate_limit_status(config.rate_limit),
    )


@router.get("/agents", response_model=AgentListResponse)
@inject
async def list_agents(
    tool_registry: ToolRegistry = Depends(Provide[DIContainer.tool_registry]),  # noqa: B008
    retriever: DocumentRetriever | None = Depends(Provide[DIContainer.retriever]),  # noqa: B008
) -> AgentListResponse:
    """List all available agents and their descriptions."""
    agents = [
        AgentInfo(
            name="supervisor",
            description="Routes user queries to the appropriate specialist agent",
            tools=[],
        ),
        AgentInfo(
            name="chat",
            description="General conversation and casual questions",
            tools=["memory"],
        ),
    ]

    if tool_registry.get("code_executor"):
        agents.append(
            AgentInfo(
                name="code",
                description="Code generation, analysis, and debugging",
                tools=["code_executor"],
            )
        )

    if tool_registry.get("web_search"):
        agents.append(
            AgentInfo(
                name="web_search",
                description="Search the web for current information",
                tools=["web_search"],
            )
        )

    if retriever:
        agents.append(
            AgentInfo(
                name="rag",
                description="Answer questions based on uploaded documents",
                tools=["retriever"],
            )
        )

    return AgentListResponse(agents=agents)


@router.post("/documents", response_model=DocumentUploadResponse)
@inject
async def upload_document(
    request: DocumentUploadRequest,
    retriever: DocumentRetriever | None = Depends(Provide[DIContainer.retriever]),  # noqa: B008
) -> DocumentUploadResponse:
    """Upload a document for RAG.

    Requires a configured retriever (Pinecone).
    """
    if not retriever:
        raise HTTPException(
            status_code=400,
            detail="RAG is not configured. Set up a document retriever first.",
        )

    try:
        await retriever.add_documents([{"content": request.content, "metadata": request.metadata}])
        return DocumentUploadResponse(
            status="indexed",
            message="Document successfully added to knowledge base",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="문서 인덱싱 중 오류가 발생했습니다.") from e


@router.delete("/sessions/{session_id}")
@inject
async def clear_session(
    session_id: str,
    memory: MemoryStore = Depends(Provide[DIContainer.memory]),  # noqa: B008
):
    """Clear conversation history for a session."""
    try:
        await memory.clear(session_id)
        return {"status": "cleared", "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail="세션 초기화 중 오류가 발생했습니다.") from e


# === Session Management Endpoints ===


@router.post("/sessions", response_model=SessionResponse)
@inject
async def create_session(
    request: SessionCreate,
    session_store: SessionStore = Depends(Provide[DIContainer.session_store]),  # noqa: B008
) -> SessionResponse:
    """Create a new session for guest user (identified by device_id)."""
    # Use provided session_id (lazy sync) or generate new one
    session_id = request.session_id if request.session_id else str(uuid4())
    user_id = request.device_id  # Use device_id as user_id for guest mode

    session = await session_store.create(
        session_id=session_id,
        user_id=user_id,
        title=request.title,
        metadata=request.metadata,
    )

    return SessionResponse(
        id=session.id,
        user_id=session.user_id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        metadata=session.metadata,
    )


@router.get("/sessions", response_model=SessionListResponse)
@inject
async def list_sessions(
    device_id: str,
    session_store: SessionStore = Depends(Provide[DIContainer.session_store]),  # noqa: B008
) -> SessionListResponse:
    """List all sessions for the device (guest mode)."""
    sessions = await session_store.list_by_user(device_id)

    user_sessions = [
        SessionResponse(
            id=s.id,
            user_id=s.user_id,
            title=s.title,
            created_at=s.created_at,
            updated_at=s.updated_at,
            metadata=s.metadata,
        )
        for s in sessions
    ]

    return SessionListResponse(sessions=user_sessions)


@router.delete("/sessions/{session_id}/full")
@inject
async def delete_session(
    session_id: str,
    device_id: str,
    session_store: SessionStore = Depends(Provide[DIContainer.session_store]),  # noqa: B008
    vector_store: PineconeVectorStore = Depends(Provide[DIContainer.vector_store]),  # noqa: B008
    memory: MemoryStore = Depends(Provide[DIContainer.memory]),  # noqa: B008
    long_term_memory: LongTermMemory = Depends(Provide[DIContainer.long_term_memory]),  # noqa: B008
):
    """Delete a session and all its associated documents.

    This will:
    1. Delete all document vectors from Pinecone for this session
    2. Clear session memory (Redis)
    3. Delete topic summaries for this session
    4. Remove the session from storage
    """
    # Check if session exists - if it does, verify ownership
    # If session doesn't exist (isLocalOnly), still run cleanup for Pinecone/Redis
    session = await session_store.get(session_id)
    if session and session.user_id != device_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this session")

    try:
        # 1. Delete vectors from Pinecone (always run - idempotent)
        deleted_vectors = 0
        if vector_store:
            deleted_vectors = await vector_store.delete_session_documents(device_id, session_id)
            log_request(
                method="DELETE",
                path=f"/api/v1/sessions/{session_id}/full",
                session_id=session_id,
                user_message=f"Deleted {deleted_vectors} vectors from Pinecone",
                duration_ms=0,
                status="success",
            )

        # 2. Clear Redis memory (always run - idempotent)
        await memory.clear(session_id)

        # 3. Delete topic summaries for this session (always run - idempotent)
        deleted_topics = 0
        if long_term_memory:
            deleted_topics = await long_term_memory.delete_session_topics(session_id)

        # 4. Delete session from storage (only if it exists)
        if session:
            await session_store.delete(session_id)

        # 5. Clean up rate limit counter for this session
        _rate_limits.pop(session_id, None)

        return {
            "status": "deleted",
            "session_id": session_id,
            "deleted_vectors": deleted_vectors,
            "deleted_topics": deleted_topics,
            "message": "Session and associated resources deleted successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        log_request(
            method="DELETE",
            path=f"/api/v1/sessions/{session_id}/full",
            session_id=session_id,
            user_message="Failed to delete session",
            duration_ms=0,
            status="error",
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {e}") from e


# === Logs Endpoints ===


@router.get("/logs")
async def get_logs(
    lines: int = 100,
    log_type: str = "app",
):
    """Get recent log entries.

    Args:
        lines: Number of lines to return (default: 100, max: 1000)
        log_type: "app" or "error"

    Returns:
        List of log lines
    """
    from src.core.logging import get_recent_logs

    lines = min(lines, 1000)  # Cap at 1000 lines
    logs = get_recent_logs(lines=lines, log_type=log_type)
    return {
        "log_type": log_type,
        "lines": len(logs),
        "logs": logs,
    }


@router.get("/logs/files")
async def list_log_files():
    """List available log files."""
    from src.core.logging import LOG_DIR

    log_files = []
    if LOG_DIR.exists():
        for f in LOG_DIR.glob("*.log"):
            stat = f.stat()
            log_files.append(
                {
                    "name": f.name,
                    "size_bytes": stat.st_size,
                    "modified": f.stat().st_mtime,
                }
            )

    return {
        "log_dir": str(LOG_DIR),
        "files": sorted(log_files, key=lambda x: x["modified"], reverse=True),
    }


@router.delete("/logs")
async def clear_logs(
    log_type: str = "all",
):
    """Clear log files.

    Args:
        log_type: "app", "error", or "all"
    """
    from src.core.logging import APP_LOG_FILE, ERROR_LOG_FILE, LOG_DIR

    cleared = []

    if log_type in ("app", "all") and APP_LOG_FILE.exists():
        APP_LOG_FILE.unlink()
        cleared.append("app.log")

    if log_type in ("error", "all") and ERROR_LOG_FILE.exists():
        ERROR_LOG_FILE.unlink()
        cleared.append("error.log")

    # Also clear rotated logs if "all"
    if log_type == "all":
        for f in LOG_DIR.glob("*.log.*"):
            f.unlink()
            cleared.append(f.name)

    return {"status": "cleared", "files": cleared}


# === Document Upload Endpoints ===


@router.post("/documents/upload", response_model=FileUploadResponse)
@inject
async def upload_file(
    file: UploadFile = File(...),  # noqa: B008
    metadata: str = Form(default="{}"),  # JSON string  # noqa: B008
    session_id: str = Form(...),  # noqa: B008
    device_id: str = Form(...),  # noqa: B008
    session_store: SessionStore = Depends(Provide[DIContainer.session_store]),  # noqa: B008
    doc_store: PineconeVectorStore = Depends(Provide[DIContainer.vector_store]),  # noqa: B008
    parser: DocumentParser = Depends(Provide[DIContainer.document_parser]),  # noqa: B008
    chunker: DocumentChunker = Depends(Provide[DIContainer.document_chunker]),  # noqa: B008
) -> FileUploadResponse:
    """Upload a file for RAG processing.

    Supports PDF, DOCX, TXT, MD, CSV, and JSON files.
    The file is parsed, chunked, and stored in the vector database.

    Requires device_id and a valid session_id.
    If session doesn't exist, it will be created automatically.
    """
    # Check if document store is available
    if not doc_store:
        raise HTTPException(
            status_code=400,
            detail="Document store is not configured. Set up Pinecone first.",
        )

    # Verify session exists or create it
    session = await session_store.get(session_id)
    if not session:
        # Auto-create session if it doesn't exist
        session = await session_store.create(
            session_id=session_id,
            user_id=device_id,
            title="Document Upload",
        )
    elif session.user_id != device_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this session")

    # Validate metadata JSON size first (prevent DoS)
    is_valid, error = validate_json_size(metadata, max_size_kb=10)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid metadata: {error}")

    # Parse and sanitize metadata
    try:
        meta_dict = json.loads(metadata)
        meta_dict = sanitize_metadata(meta_dict)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid metadata JSON: {e}") from e

    # Validate filename
    filename = file.filename or "unknown"
    if not filename or filename in (".", "", ".."):
        raise HTTPException(status_code=400, detail="Invalid filename")

    # Read file content
    try:
        content = await file.read()

        # Security: Validate file upload with comprehensive checks
        is_valid, error, file_metadata = validate_file_upload(
            filename=filename,
            content=content,
            declared_mime_type=file.content_type,
        )

        if not is_valid:
            log_request(
                method="POST",
                path="/api/v1/documents/upload",
                session_id=None,
                user_message=f"File upload rejected: {filename}",
                duration_ms=0,
                status="blocked",
                error=error,
            )
            raise HTTPException(status_code=400, detail=error)

    except ValidationError as e:
        raise HTTPException(status_code=400, detail="잘못된 요청 형식입니다.") from e
    except Exception as e:
        log_request(
            method="POST",
            path="/api/v1/documents/upload",
            session_id=None,
            user_message=f"File upload error: {filename}",
            duration_ms=0,
            status="error",
            error=str(e),
        )
        raise HTTPException(status_code=400, detail=f"Failed to process file: {e}") from e

    # Get validated file type
    file_type = file_metadata.get("detected_type") or file_metadata.get("extension")
    if not file_type:
        raise HTTPException(status_code=400, detail="Could not determine file type")

    try:
        # Parse document
        sections = parser.parse_from_bytes(content, file_type)

        if not sections:
            raise HTTPException(status_code=400, detail="No content extracted from file")

        # Chunk document
        chunks = chunker.chunk(sections, source=filename)

        # Create document model
        import uuid
        from datetime import datetime

        doc = Document(
            id=str(uuid.uuid4()),
            filename=filename,
            file_type=file_type,
            upload_time=datetime.utcnow(),
            chunks=chunks,
            total_tokens=sum(c.metadata.token_count for c in chunks),
            metadata=meta_dict,
        )

        # Store in vector database with device/session isolation
        await doc_store.add_document(doc, device_id=device_id, session_id=session_id)

        return FileUploadResponse(
            document_id=doc.id,
            filename=filename,
            file_type=file_type,
            chunks_created=len(chunks),
            total_tokens=doc.total_tokens,
            upload_time=doc.upload_time,
            status="success",
            message=f"Successfully processed {filename} ({len(chunks)} chunks)",
        )

    except ImportError as e:
        raise HTTPException(status_code=400, detail=f"Missing dependency: {e}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {e}") from e


def _get_file_extension(filename: str) -> str:
    """Get file extension from filename."""
    import os

    _, ext = os.path.splitext(filename.lower())
    return ext.lstrip(".")


@router.get("/documents", response_model=DocumentListResponse)
@inject
async def list_documents(
    device_id: str,
    doc_store: PineconeVectorStore = Depends(Provide[DIContainer.vector_store]),  # noqa: B008
) -> DocumentListResponse:
    """List all uploaded documents for the device."""
    if not doc_store:
        return DocumentListResponse(documents=[])

    try:
        doc_ids = await doc_store.list_documents(device_id=device_id)

        documents = []
        for doc_id in doc_ids:
            stats = await doc_store.get_document_stats(doc_id, device_id=device_id)
            if stats:
                documents.append(
                    DocumentInfo(
                        id=stats.document_id,
                        filename=stats.filename or "unknown",
                        file_type=stats.file_type or "unknown",
                        upload_time=stats.upload_time or datetime.utcnow(),
                        chunk_count=stats.chunk_count,
                        total_tokens=stats.total_tokens,
                    )
                )

        return DocumentListResponse(documents=documents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {e}") from e


@router.delete("/documents/{document_id}", response_model=DocumentDeleteResponse)
@inject
async def delete_document(
    document_id: str,
    device_id: str,
    doc_store: PineconeVectorStore = Depends(Provide[DIContainer.vector_store]),  # noqa: B008
) -> DocumentDeleteResponse:
    """Delete a document and all its chunks.

    Verifies that the device owns the document before deletion.
    """
    if not doc_store:
        raise HTTPException(
            status_code=400,
            detail="Document store is not configured.",
        )

    try:
        # Check if document exists and belongs to device
        stats = await doc_store.get_document_stats(document_id, device_id=device_id)
        if not stats:
            raise HTTPException(status_code=404, detail="Document not found")

        # Delete with device isolation
        await doc_store.delete_document(document_id, device_id=device_id)

        return DocumentDeleteResponse(
            document_id=document_id,
            status="deleted",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {e}") from e


# === Metrics Endpoints ===


@router.get("/metrics/summary", response_model=MetricsSummaryResponse)
@inject
async def get_metrics_summary(
    period: str = "24h",
    metrics_store=Depends(Provide[DIContainer.metrics_store]),  # noqa: B008
) -> MetricsSummaryResponse:
    """Get aggregated metrics summary for a time period.

    Args:
        period: Time period - "24h", "7d", "30d"
        metrics_store: Metrics store dependency

    Returns:
        Metrics summary with aggregated statistics
    """
    if not metrics_store:
        raise HTTPException(
            status_code=503,
            detail="Metrics store is not available. Check Supabase configuration.",
        )

    # Validate period
    if period not in ("24h", "7d", "30d"):
        raise HTTPException(
            status_code=400,
            detail="Invalid period. Must be one of: 24h, 7d, 30d",
        )

    try:
        summary = await metrics_store.get_summary(period)

        from src.api.schemas import AgentMetricItem

        agent_stats_items = [
            AgentMetricItem(
                agent_name=stat["agent_name"],
                date=stat["date"],
                total_requests=stat["total_requests"],
                successful_requests=stat["success_count"],
                failed_requests=stat["error_count"],
                blocked_requests=stat.get("timeout_count", 0),
                avg_duration_ms=stat["avg_duration_ms"],
                total_tokens=stat["total_input_tokens"] + stat["total_output_tokens"],
            )
            for stat in summary.get("agent_stats", [])
        ]

        return MetricsSummaryResponse(
            period=summary["period"],
            total_requests=summary["total_requests"],
            successful_requests=summary["success_count"],
            failed_requests=summary["error_count"],
            blocked_requests=summary.get("timeout_count", 0),
            avg_duration_ms=summary["avg_duration_ms"],
            total_tokens=summary["total_input_tokens"] + summary["total_output_tokens"],
            agent_stats=agent_stats_items,
            start_time=summary["start_time"],
            end_time=summary["end_time"],
        )
    except Exception as e:
        logger.error("metrics_summary_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics summary") from e


@router.get("/metrics/agents")
@inject
async def get_agent_metrics(
    agent_name: str,
    period: str = "24h",
    metrics_store=Depends(Provide[DIContainer.metrics_store]),  # noqa: B008
):
    """Get statistics for a specific agent.

    Args:
        agent_name: Agent name to filter by
        period: Time period - "24h", "7d", "30d"
        metrics_store: Metrics store dependency

    Returns:
        Agent-specific statistics
    """
    if not metrics_store:
        raise HTTPException(
            status_code=503,
            detail="Metrics store is not available. Check Supabase configuration.",
        )

    # Validate period
    if period not in ("24h", "7d", "30d"):
        raise HTTPException(
            status_code=400,
            detail="Invalid period. Must be one of: 24h, 7d, 30d",
        )

    try:
        stats = await metrics_store.get_agent_stats(agent_name, period)

        if not stats:
            raise HTTPException(
                status_code=404,
                detail=f"No metrics found for agent '{agent_name}' in period '{period}'",
            )

        from src.api.schemas import AgentMetricsResponse

        return AgentMetricsResponse(
            agent_name=stats["agent_name"],
            date=stats["date"],
            total_requests=stats["total_requests"],
            successful_requests=stats["success_count"],
            failed_requests=stats["error_count"],
            blocked_requests=stats.get("timeout_count", 0),
            avg_duration_ms=stats["avg_duration_ms"],
            total_tokens=stats["total_input_tokens"] + stats["total_output_tokens"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("agent_metrics_error", agent_name=agent_name, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve agent metrics") from e
