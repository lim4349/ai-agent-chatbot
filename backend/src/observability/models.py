"""Pydantic models for observability metrics."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RequestMetric(BaseModel):
    """Individual request metric recorded by the system."""

    session_id: str = Field(..., description="Session identifier")
    user_id: str | None = Field(default=None, description="User identifier")
    agent_name: str = Field(..., description="Agent that handled the request")
    model_name: str = Field(..., description="LLM model used")
    duration_ms: float = Field(..., description="Request duration in milliseconds")
    input_tokens: int = Field(default=0, description="Input tokens processed")
    output_tokens: int = Field(default=0, description="Output tokens generated")
    status: str = Field(..., description="Request status: success, error, timeout")
    error_message: str | None = Field(default=None, description="Error message if status is error")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="When the request was made"
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class AgentDailyStats(BaseModel):
    """Daily statistics for a specific agent."""

    agent_name: str = Field(..., description="Agent name")
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    total_requests: int = Field(..., description="Total number of requests")
    success_count: int = Field(default=0, description="Successful requests")
    error_count: int = Field(default=0, description="Failed requests")
    timeout_count: int = Field(default=0, description="Timeout requests")
    avg_duration_ms: float = Field(..., description="Average request duration in milliseconds")
    total_input_tokens: int = Field(default=0, description="Total input tokens")
    total_output_tokens: int = Field(default=0, description="Total output tokens")
    p95_duration_ms: int | None = Field(default=None, description="95th percentile duration")
    p99_duration_ms: int | None = Field(default=None, description="99th percentile duration")


class MetricsSummary(BaseModel):
    """Aggregated metrics summary for a time period."""

    period: str = Field(..., description="Time period: 24h, 7d, 30d")
    total_requests: int = Field(..., description="Total requests in period")
    success_count: int = Field(default=0, description="Successful requests")
    error_count: int = Field(default=0, description="Failed requests")
    timeout_count: int = Field(default=0, description="Timeout requests")
    avg_duration_ms: float = Field(..., description="Average duration across all requests")
    total_input_tokens: int = Field(default=0, description="Total input tokens")
    total_output_tokens: int = Field(default=0, description="Total output tokens")
    agent_stats: list[AgentDailyStats] = Field(
        default_factory=list, description="Per-agent statistics"
    )
    start_time: datetime = Field(..., description="Start of period")
    end_time: datetime = Field(..., description="End of period")
