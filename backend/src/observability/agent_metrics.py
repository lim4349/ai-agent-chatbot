"""Agent metrics wrapper for automatic metrics recording."""

import time
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from src.core.logging import get_logger

if TYPE_CHECKING:
    from src.observability.metrics_store import MetricsStore

logger = get_logger(__name__)


@asynccontextmanager
async def record_agent_metrics(
    metrics_store: "MetricsStore | None",
    session_id: str,
    agent_name: str,
    model_name: str,
    user_id: str | None = None,
):
    """Context manager for recording agent execution metrics.

    Automatically captures duration, token usage, and status from LLM responses.

    Usage:
        async with record_agent_metrics(store, sid, "chat", "gpt-4o") as metrics:
            result = await llm.generate(messages)
            metrics.set_token_count(input_tokens, output_tokens)
            metrics.set_status("success")
            # or metrics.set_error(exception)

    Args:
        metrics_store: MetricsStore instance (optional)
        session_id: Session identifier
        agent_name: Agent that handled the request
        model_name: LLM model used
        user_id: Optional user identifier

    Yields:
        AgentMetricsRecorder for setting metrics data
    """
    recorder = AgentMetricsRecorder(
        metrics_store=metrics_store,
        session_id=session_id,
        agent_name=agent_name,
        model_name=model_name,
        user_id=user_id,
    )

    start_time = time.perf_counter()
    try:
        yield recorder
    except Exception as e:
        recorder.set_error(e)
        raise
    finally:
        duration_ms = (time.perf_counter() - start_time) * 1000
        await recorder.record(duration_ms)


class AgentMetricsRecorder:
    """Recorder for agent execution metrics.

    Used within the record_agent_metrics context manager to set
    token counts and status before automatic recording.
    """

    def __init__(
        self,
        metrics_store: "MetricsStore | None",
        session_id: str,
        agent_name: str,
        model_name: str,
        user_id: str | None = None,
    ):
        self.metrics_store = metrics_store
        self.session_id = session_id
        self.agent_name = agent_name
        self.model_name = model_name
        self.user_id = user_id
        self.input_tokens = 0
        self.output_tokens = 0
        self.status = "success"
        self.error_message: str | None = None
        self.metadata: dict = {}

    def set_token_count(self, input_tokens: int, output_tokens: int) -> None:
        """Set the token counts for this request.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
        """
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens

    def set_status(self, status: str) -> None:
        """Set the request status.

        Args:
            status: Request status (success, error, timeout)
        """
        self.status = status

    def set_error(self, error: Exception) -> None:
        """Set error information from an exception.

        Args:
            error: Exception that occurred
        """
        self.status = "error"
        self.error_message = str(error)[:1000]  # Limit error message length

    def set_metadata(self, **kwargs) -> None:
        """Set additional metadata.

        Args:
            **kwargs: Additional metadata key-value pairs
        """
        self.metadata.update(kwargs)

    async def record(self, duration_ms: float) -> None:
        """Record the metrics to the store.

        Called automatically by the context manager.

        Args:
            duration_ms: Request duration in milliseconds
        """
        if not self.metrics_store:
            return

        try:
            await self.metrics_store.record_request(
                session_id=self.session_id,
                agent_name=self.agent_name,
                duration_ms=duration_ms,
                model_name=self.model_name,
                input_tokens=self.input_tokens,
                output_tokens=self.output_tokens,
                status=self.status,
                error_message=self.error_message,
                user_id=self.user_id,
                metadata=self.metadata if self.metadata else None,
            )
        except Exception as e:
            # Don't let metrics recording failures break the main flow
            logger.warning("metrics_recording_failed", error=str(e))


def extract_token_usage_from_response(response) -> tuple[int, int]:
    """Extract token usage from LangChain/LLM response.

    Args:
        response: LLM response object

    Returns:
        Tuple of (input_tokens, output_tokens)
    """
    input_tokens = 0
    output_tokens = 0

    # LangChain response with usage_metadata
    if hasattr(response, "usage_metadata"):
        usage = response.usage_metadata
        if usage:
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)

    # LangChain response with response_metadata
    elif hasattr(response, "response_metadata"):
        meta = response.response_metadata
        if meta and "token_usage" in meta:
            token_usage = meta["token_usage"]
            input_tokens = token_usage.get("input_tokens", 0) or token_usage.get("prompt_tokens", 0)
            output_tokens = token_usage.get("output_tokens", 0) or token_usage.get(
                "completion_tokens", 0
            )

    # OpenAI-style response
    elif hasattr(response, "usage"):
        usage = response.usage
        if usage:
            input_tokens = getattr(usage, "prompt_tokens", 0)
            output_tokens = getattr(usage, "completion_tokens", 0)

    # Log warning if no token usage found
    if input_tokens == 0 and output_tokens == 0:
        logger.warning(
            "token_usage_not_found",
            response_type=type(response).__name__,
            has_usage_metadata=hasattr(response, "usage_metadata"),
            has_response_metadata=hasattr(response, "response_metadata"),
            has_usage=hasattr(response, "usage"),
        )

    return input_tokens, output_tokens
