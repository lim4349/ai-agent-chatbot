"""API routes for the chatbot."""

import json
import time
from datetime import datetime

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
)
from src.core.config import AppConfig
from src.core.di_container import DIContainer
from src.core.logging import log_request
from src.core.prompt_security import detect_injection, filter_llm_output, sanitize_for_llm
from src.core.protocols import DocumentChunker, DocumentParser, DocumentRetriever, MemoryStore
from src.core.validators import (
    ValidationError,
    sanitize_metadata,
    validate_file_upload,
    validate_json_size,
)
from src.documents.models import Document
from src.documents.store import DocumentVectorStore
from src.graph.state import create_initial_state
from src.tools.registry import ToolRegistry

router = APIRouter()


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
) -> ChatResponse:
    """Send a message and get a response (synchronous).

    The supervisor will route to the appropriate specialist agent.
    """
    start_time = time.perf_counter()

    # Security: Check for prompt injection attacks
    injection = detect_injection(request.message)
    if injection:
        # Log the security event
        log_request(
            method="POST",
            path="/api/v1/chat",
            session_id=request.session_id,
            user_message=request.message,
            duration_ms=0,
            status="blocked",
            error=f"Prompt injection detected: {injection['type']}",
        )
        raise HTTPException(
            status_code=400,
            detail="Your request contains potentially malicious content and cannot be processed."
        )

    # Security: Sanitize input for LLM
    sanitized_message = sanitize_for_llm(request.message)

    # Create initial state with sanitized message
    initial_state = create_initial_state(sanitized_message, request.session_id)

    # Configure with thread ID for state persistence
    config = {"configurable": {"thread_id": request.session_id}}

    try:
        # Execute graph
        result = await graph.ainvoke(initial_state, config=config)

        # Extract response
        messages = result.get("messages", [])
        response_message = get_message_content(messages[-1]) if messages else ""

        # Security: Filter potential prompt leaks from output
        response_message = filter_llm_output(response_message)

        agent_used = result.get("next_agent", "chat")
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
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/chat/stream")
@inject
async def chat_stream(
    request: ChatRequest,
    graph=Depends(Provide[DIContainer.graph]),  # noqa: B008
):
    """Send a message and get a streaming response (SSE).

    Yields tokens as they are generated.
    """
    # Security: Check for prompt injection attacks
    injection = detect_injection(request.message)
    if injection:
        log_request(
            method="POST",
            path="/api/v1/chat/stream",
            session_id=request.session_id,
            user_message=request.message,
            duration_ms=0,
            status="blocked",
            error=f"Prompt injection detected: {injection['type']}",
        )
        # Return error as SSE event
        async def error_generator():
            yield {"event": "error", "data": json.dumps({"error": "Request contains potentially malicious content"})}
        return EventSourceResponse(error_generator())

    # Security: Sanitize input for LLM
    sanitized_message = sanitize_for_llm(request.message)
    initial_state = create_initial_state(sanitized_message, request.session_id)
    config = {"configurable": {"thread_id": request.session_id}}

    async def event_generator():
        try:
            # Yield metadata first
            yield {"event": "metadata", "data": json.dumps({"session_id": request.session_id})}

            # Stream events from graph
            async for event in graph.astream_events(initial_state, config=config, version="v2"):
                kind = event.get("event")

                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        yield {"event": "token", "data": chunk.content}

                elif kind == "on_chain_end":
                    # Send metadata about which agent was used
                    if event.get("name") == "supervisor":
                        output = event.get("data", {}).get("output", {})
                        agent = output.get("next_agent", "chat")
                        yield {"event": "agent", "data": json.dumps({"agent": agent})}

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
    available_agents = ["supervisor", "chat", "code"]
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
        AgentInfo(
            name="code",
            description="Code generation, analysis, and debugging",
            tools=["code_executor"] if tool_registry.get("code_executor") else [],
        ),
    ]

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

    Requires a configured retriever (ChromaDB).
    """
    if not retriever:
        raise HTTPException(
            status_code=400,
            detail="RAG is not configured. Set up a document retriever first.",
        )

    try:
        await retriever.add_documents(
            [{"content": request.content, "metadata": request.metadata}]
        )
        return DocumentUploadResponse(
            status="indexed",
            message="Document successfully added to knowledge base",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
            log_files.append({
                "name": f.name,
                "size_bytes": stat.st_size,
                "modified": f.stat().st_mtime,
            })

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
    doc_store: DocumentVectorStore = Depends(Provide[DIContainer.vector_store]),  # noqa: B008
    parser: DocumentParser = Depends(Provide[DIContainer.document_parser]),  # noqa: B008
    chunker: DocumentChunker = Depends(Provide[DIContainer.document_chunker]),  # noqa: B008
) -> FileUploadResponse:
    """Upload a file for RAG processing.

    Supports PDF, DOCX, TXT, MD, CSV, and JSON files.
    The file is parsed, chunked, and stored in the vector database.
    """
    # Check if document store is available
    if not doc_store:
        raise HTTPException(
            status_code=400,
            detail="Document store is not configured. Set up ChromaDB first.",
        )

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
        raise HTTPException(status_code=400, detail=str(e)) from e
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
    file_type = file_metadata["extension"]

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

        # Store in vector database
        await doc_store.add_document(doc)

        return FileUploadResponse(
            document_id=doc.id,
            filename=filename,
            file_type=file_type,
            chunks_created=len(chunks),
            total_tokens=doc.total_tokens,
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
    doc_store: DocumentVectorStore = Depends(Provide[DIContainer.vector_store]),  # noqa: B008
) -> DocumentListResponse:
    """List all uploaded documents."""
    if not doc_store:
        return DocumentListResponse(documents=[])

    try:
        doc_ids = await doc_store.list_documents()

        documents = []
        for doc_id in doc_ids:
            stats = await doc_store.get_document_stats(doc_id)
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
    doc_store: DocumentVectorStore = Depends(Provide[DIContainer.vector_store]),  # noqa: B008
) -> DocumentDeleteResponse:
    """Delete a document and all its chunks."""
    if not doc_store:
        raise HTTPException(
            status_code=400,
            detail="Document store is not configured.",
        )

    try:
        success = await doc_store.delete_document(document_id)
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")

        return DocumentDeleteResponse(
            document_id=document_id,
            status="deleted",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {e}") from e
