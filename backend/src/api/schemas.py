"""Request and response schemas for the API."""

from datetime import datetime
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
    stream: bool = Field(default=False, description="Enable streaming response")


class DocumentUploadRequest(BaseModel):
    """Document upload request for RAG."""

    content: str = Field(..., min_length=1, description="Document content")
    metadata: dict = Field(default_factory=dict, description="Document metadata")


class FileUploadRequest(BaseModel):
    """File upload request for RAG with binary file content."""

    metadata: dict = Field(default_factory=dict, description="Document metadata")


# --- Response Models ---


class ChatResponse(BaseModel):
    """Chat response schema."""

    message: str = Field(..., description="Assistant response")
    session_id: str = Field(..., description="Session ID")
    agent_used: str = Field(..., description="Agent that processed the request")
    route_reasoning: str | None = Field(default=None, description="Supervisor routing reasoning")
    tool_results: list[dict] = Field(default_factory=list, description="Tool execution results")
    created_at: datetime = Field(default_factory=datetime.now, description="Response timestamp")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service status")
    llm_provider: str = Field(..., description="Active LLM provider")
    llm_model: str = Field(..., description="Active LLM model")
    memory_backend: str = Field(..., description="Active memory backend")
    available_agents: list[str] = Field(..., description="Available agent names")


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
