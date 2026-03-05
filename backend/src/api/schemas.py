"""Request and response schemas for the API."""

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

# --- Request Models ---


class ChatRequest(BaseModel):
    """Chat request schema."""

    message: str = Field(..., min_length=1, max_length=10000, description="User message")
    session_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Session ID for conversation continuity",
    )
    device_id: str | None = Field(
        default=None, description="Device ID for guest mode cross-session continuity"
    )
    stream: bool = Field(default=False, description="Enable streaming response")


class DocumentUploadRequest(BaseModel):
    """Document upload request for RAG."""

    content: str = Field(..., min_length=1, description="Document content")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Session or document metadata"
    )


class FileUploadRequest(BaseModel):
    """File upload request for RAG with binary file content."""

    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Session or document metadata"
    )


# --- Response Models ---


class ChatResponse(BaseModel):
    """Chat response schema."""

    message: str = Field(..., description="Assistant response")
    session_id: str = Field(..., description="Session ID")
    agent_used: str = Field(..., description="Agent that processed the request")
    route_reasoning: str | None = Field(default=None, description="Supervisor routing reasoning")
    tool_results: list[dict[str, Any]] = Field(
        default_factory=list, description="Tool execution results"
    )
    created_at: datetime = Field(default_factory=datetime.now, description="Response timestamp")


class RateLimitStatus(BaseModel):
    """Status of a single rate limit window."""

    limit: int = Field(..., description="Maximum allowed in this window (0 = unlimited)")
    used: int = Field(..., description="Number used so far in current window")
    remaining: int = Field(..., description="Number remaining before limit is hit")
    reset_at: str = Field(..., description="ISO 8601 timestamp when the window resets")


class RateLimitStatusResponse(BaseModel):
    """Aggregated rate limit status across all windows."""

    per_minute: RateLimitStatus | None = Field(default=None, description="Per-minute limit status")
    per_hour: RateLimitStatus | None = Field(default=None, description="Per-hour limit status")
    daily: RateLimitStatus | None = Field(default=None, description="Daily API call limit status")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service status")
    llm_provider: str = Field(..., description="Active LLM provider")
    llm_model: str = Field(..., description="Active LLM model")
    memory_backend: str = Field(..., description="Active memory backend")
    available_agents: list[str] = Field(..., description="Available agent names")
    daily_request_limit: int = Field(0, description="Daily request limit (0 = unlimited)")
    per_minute_limit: int = Field(0, description="Request limit per minute (0 = unlimited)")
    per_hour_limit: int = Field(0, description="Request limit per hour (0 = unlimited)")
    token_limit: int = Field(0, description="Token limit per day (0 = unlimited)")
    rate_limit_status: RateLimitStatusResponse | None = Field(
        default=None, description="Current rate limit usage status"
    )
    google_rate_limit: dict = Field(
        default_factory=dict, description="Rate limit info from Google AI Studio API headers"
    )


class AgentInfo(BaseModel):
    """Agent information."""

    name: str = Field(..., description="Agent name")
    description: str = Field(..., description="Agent description")
    tools: list[str] = Field(default_factory=list, description="Tools available to agent")


class AgentListResponse(BaseModel):
    """List of available agents."""

    agents: list[AgentInfo] = Field(..., description="Available agents")


class ErrorResponse(BaseModel):
    """Error response schema."""

    error: dict = Field(..., description="Error details")


class DocumentUploadResponse(BaseModel):
    """Document upload response."""

    status: str = Field(..., description="Upload status")
    message: str = Field(..., description="Status message")


class FileUploadResponse(BaseModel):
    """File upload response with processing details."""

    document_id: str = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Original filename")
    file_type: str = Field(..., description="Detected file type (pdf, docx, txt, md, csv, json)")
    chunks_created: int = Field(..., description="Number of chunks created from the document")
    total_tokens: int = Field(..., description="Estimated total tokens in the document")
    upload_time: datetime = Field(..., description="Upload timestamp")
    status: str = Field(..., description="Upload and processing status")
    message: str = Field(..., description="Status message")


class DocumentInfo(BaseModel):
    """Document information for listing."""

    id: str = Field(..., description="Document identifier")
    filename: str = Field(..., description="Original filename")
    file_type: str = Field(..., description="File type extension")
    upload_time: datetime = Field(..., description="When the document was uploaded")
    chunk_count: int = Field(..., description="Number of chunks")
    total_tokens: int = Field(..., description="Estimated total tokens")


class DocumentListResponse(BaseModel):
    """List of uploaded documents."""

    documents: list[DocumentInfo] = Field(..., description="List of documents")


class DocumentDeleteResponse(BaseModel):
    """Document deletion response."""

    document_id: str = Field(..., description="Deleted document identifier")
    status: str = Field(..., description="Deletion status")


# --- Session Models ---


class SessionCreate(BaseModel):
    """Session creation request."""

    title: str = Field(default="New Chat", max_length=100, description="Session title")
    device_id: str = Field(..., description="Device identifier for guest mode")
    metadata: dict = Field(default_factory=dict, description="Session metadata")
    session_id: str | None = Field(
        default=None, description="Optional session ID (for lazy sync from frontend)"
    )


class SessionResponse(BaseModel):
    """Session response."""

    id: str = Field(..., description="Session identifier")
    user_id: str = Field(..., description="Owner user ID")
    title: str = Field(..., description="Session title")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    metadata: dict = Field(default_factory=dict, description="Session metadata")


class SessionListResponse(BaseModel):
    """List of sessions."""

    sessions: list[SessionResponse] = Field(..., description="List of sessions")


# --- Metrics Models ---


class AgentMetricItem(BaseModel):
    """Per-agent metric item."""

    agent_name: str = Field(..., description="Agent name")
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    total_requests: int = Field(..., description="Total number of requests")
    successful_requests: int = Field(..., description="Successful requests")
    failed_requests: int = Field(..., description="Failed requests")
    blocked_requests: int = Field(..., description="Blocked requests")
    avg_duration_ms: float = Field(..., description="Average request duration in milliseconds")
    total_tokens: int = Field(..., description="Total tokens processed")


class MetricsSummaryResponse(BaseModel):
    """Metrics summary response."""

    period: str = Field(..., description="Time period: 24h, 7d, 30d")
    total_requests: int = Field(..., description="Total requests in period")
    successful_requests: int = Field(..., description="Successful requests")
    failed_requests: int = Field(..., description="Failed requests")
    blocked_requests: int = Field(..., description="Blocked requests")
    avg_duration_ms: float = Field(..., description="Average duration across all requests")
    total_tokens: int = Field(..., description="Total tokens processed")
    agent_stats: list[AgentMetricItem] = Field(
        default_factory=list, description="Per-agent statistics"
    )
    start_time: datetime = Field(..., description="Start of period")
    end_time: datetime = Field(..., description="End of period")


class AgentMetricsResponse(BaseModel):
    """Agent-specific metrics response."""

    agent_name: str = Field(..., description="Agent name")
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    total_requests: int = Field(..., description="Total number of requests")
    successful_requests: int = Field(..., description="Successful requests")
    failed_requests: int = Field(..., description="Failed requests")
    blocked_requests: int = Field(..., description="Blocked requests")
    avg_duration_ms: float = Field(..., description="Average request duration in milliseconds")
    total_tokens: int = Field(..., description="Total tokens processed")


class RequestMetricResponse(BaseModel):
    """Individual request metric response."""

    session_id: str = Field(..., description="Session identifier")
    agent_name: str = Field(..., description="Agent that handled the request")
    duration_ms: float = Field(..., description="Request duration in milliseconds")
    token_count: int = Field(..., description="Tokens processed")
    status: str = Field(..., description="Request status: success, error, blocked")
    error_message: str | None = Field(default=None, description="Error message if status is error")
    timestamp: datetime = Field(..., description="When the request was made")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
