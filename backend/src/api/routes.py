"""API routes for the chatbot."""

import json
import time
from datetime import UTC, datetime
from uuid import uuid4

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sse_starlette.sse import EventSourceResponse

from src.api.chat_turn import (
    PromptInjectionRejectedError,
    extract_response_message,
    get_graph_capabilities,
    prepare_chat_turn,
    resolve_agent_used,
    validate_and_sanitize_message,
)
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
    SessionCreate,
    SessionListResponse,
    SessionResponse,
    UserMemoryDeleteResponse,
)
from src.api.sse_streamer import stream_graph_events
from src.core.config import AppConfig
from src.core.di_container import DIContainer
from src.core.logging import get_logger, log_request
from src.core.protocols import (
    DocumentChunker,
    DocumentParser,
    DocumentRetriever,
    MemoryStore,
    SessionStore,
)
from src.documents.lifecycle import (
    DocumentLifecycle,
    DocumentUploadValidationError,
    parse_upload_metadata,
    validate_upload_bytes,
)
from src.documents.pinecone_store import PineconeVectorStore
from src.memory.long_term_memory import LongTermMemory
from src.tools.registry import ToolRegistry

logger = get_logger(__name__)

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
@inject
async def chat(
    request: ChatRequest,
    graph=Depends(Provide[DIContainer.graph]),  # noqa: B008
    vector_store: PineconeVectorStore = Depends(Provide[DIContainer.vector_store]),  # noqa: B008
    session_store: SessionStore = Depends(Provide[DIContainer.session_store]),  # noqa: B008
    tool_registry: ToolRegistry = Depends(Provide[DIContainer.tool_registry]),  # noqa: B008
) -> ChatResponse:
    """Send a message and get a response (synchronous).

    The LLM router selects the appropriate specialist agent.
    """
    start_time = time.perf_counter()

    try:
        sanitized_message = validate_and_sanitize_message(
            request.message,
            request.session_id,
            "/api/v1/chat",
        )
    except PromptInjectionRejectedError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    turn = await prepare_chat_turn(
        sanitized_message=sanitized_message,
        session_id=request.session_id,
        request_device_id=request.device_id,
        path="/api/v1/chat",
        vector_store=vector_store,
        session_store=session_store,
        tool_registry=tool_registry,
    )

    try:
        result = await graph.ainvoke(turn.initial_state, config=turn.graph_config)
        response_message = extract_response_message(result)
        agent_used = resolve_agent_used(result)

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
):
    """Send a message and get a streaming response (SSE).

    Yields tokens as they are generated.
    """
    try:
        sanitized_message = validate_and_sanitize_message(
            request.message,
            request.session_id,
            "/api/v1/chat/stream",
        )
    except PromptInjectionRejectedError as e:
        error_message = str(e)

        async def error_generator():
            yield {"event": "error", "data": json.dumps({"error": error_message})}

        return EventSourceResponse(error_generator())

    turn = await prepare_chat_turn(
        sanitized_message=sanitized_message,
        session_id=request.session_id,
        request_device_id=request.device_id,
        path="/api/v1/chat/stream",
        vector_store=vector_store,
        session_store=session_store,
        tool_registry=tool_registry,
    )

    async def event_generator():
        try:
            # Yield metadata first
            yield {"event": "metadata", "data": json.dumps({"session_id": request.session_id})}

            async for ev in stream_graph_events(graph, turn.initial_state, turn.graph_config):
                yield ev

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
    available_agents, available_tools, _ = get_graph_capabilities(tool_registry, retriever)

    return HealthResponse(
        status="ok",
        llm_provider=config.llm.provider,
        llm_model=config.llm.model,
        memory_backend=config.memory.backend,
        available_agents=available_agents,
        available_tools=available_tools,
    )


@router.get("/agents", response_model=AgentListResponse)
@inject
async def list_agents(
    tool_registry: ToolRegistry = Depends(Provide[DIContainer.tool_registry]),  # noqa: B008
    retriever: DocumentRetriever | None = Depends(Provide[DIContainer.retriever]),  # noqa: B008
) -> AgentListResponse:
    """List all available agents and their descriptions."""
    research_tools = []
    if tool_registry.get("web_search"):
        research_tools.append("web_search")
    if retriever or tool_registry.get("retriever"):
        research_tools.append("retriever")

    agents = [
        AgentInfo(
            name="chat",
            description="General conversation, memory commands, and ordinary Q&A",
            tools=["memory"],
        ),
        AgentInfo(
            name="research",
            description="Agentic web search, uploaded-document retrieval, and report synthesis",
            tools=research_tools,
        ),
    ]

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


@router.delete("/users/{user_id}/memory", response_model=UserMemoryDeleteResponse)
@inject
async def delete_user_memory(
    user_id: str,
    device_id: str,
    long_term_memory: LongTermMemory = Depends(Provide[DIContainer.long_term_memory]),  # noqa: B008
) -> UserMemoryDeleteResponse:
    """Delete long-term personalization data for the current guest user."""
    if user_id != device_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this user memory")

    try:
        if long_term_memory:
            await long_term_memory.clear_user_data(user_id)

        return UserMemoryDeleteResponse(
            user_id=user_id,
            status="deleted",
            message="User personalization data deleted successfully",
        )
    except Exception as e:
        log_request(
            method="DELETE",
            path=f"/api/v1/users/{user_id}/memory",
            session_id=None,
            user_message="Failed to delete user memory",
            duration_ms=0,
            status="error",
            error=str(e),
        )
        raise HTTPException(status_code=500, detail="Failed to delete user memory") from e


# === Logs Endpoints ===


def _require_debug_logs(config: AppConfig) -> None:
    """Restrict log endpoints to debug deployments."""
    if not config.debug:
        raise HTTPException(status_code=403, detail="Log endpoints are disabled")


@router.get("/logs")
@inject
async def get_logs(
    lines: int = 100,
    log_type: str = "app",
    config: AppConfig = Depends(Provide[DIContainer.config]),  # noqa: B008
):
    """Get recent log entries.

    Args:
        lines: Number of lines to return (default: 100, max: 1000)
        log_type: "app" or "error"

    Returns:
        List of log lines
    """
    from src.core.logging import get_recent_logs

    _require_debug_logs(config)
    lines = min(lines, 1000)  # Cap at 1000 lines
    logs = get_recent_logs(lines=lines, log_type=log_type)
    return {
        "log_type": log_type,
        "lines": len(logs),
        "logs": logs,
    }


@router.get("/logs/files")
@inject
async def list_log_files(
    config: AppConfig = Depends(Provide[DIContainer.config]),  # noqa: B008
):
    """List available log files."""
    from src.core.logging import LOG_DIR

    _require_debug_logs(config)
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
@inject
async def clear_logs(
    log_type: str = "all",
    config: AppConfig = Depends(Provide[DIContainer.config]),  # noqa: B008
):
    """Clear log files.

    Args:
        log_type: "app", "error", or "all"
    """
    from src.core.logging import APP_LOG_FILE, ERROR_LOG_FILE, LOG_DIR

    _require_debug_logs(config)
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

    try:
        meta_dict = parse_upload_metadata(metadata)
        content = await file.read()
        upload = validate_upload_bytes(
            filename=file.filename,
            content=content,
            declared_mime_type=file.content_type,
            metadata=meta_dict,
        )
    except DocumentUploadValidationError as e:
        log_request(
            method="POST",
            path="/api/v1/documents/upload",
            session_id=session_id,
            user_message=f"File upload rejected: {file.filename or 'unknown'}",
            duration_ms=0,
            status="blocked",
            error=str(e),
        )
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        lifecycle = DocumentLifecycle(parser=parser, chunker=chunker, vector_store=doc_store)
        doc = await lifecycle.ingest_upload(upload, device_id=device_id, session_id=session_id)
        return FileUploadResponse(
            document_id=doc.id,
            filename=doc.filename,
            file_type=doc.file_type,
            chunks_created=len(doc.chunks),
            total_tokens=doc.total_tokens,
            upload_time=doc.upload_time,
            status="success",
            message=f"Successfully processed {doc.filename} ({len(doc.chunks)} chunks)",
        )
    except ImportError as e:
        raise HTTPException(status_code=400, detail=f"Missing dependency: {e}") from e
    except DocumentUploadValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
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
                        upload_time=stats.upload_time or datetime.now(tz=UTC),
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
