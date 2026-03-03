"""Metrics store for recording and querying observability data."""

from datetime import datetime, timedelta

from src.core.logging import get_logger

logger = get_logger(__name__)


class MetricsStore:
    """Store for recording and querying request metrics.

    Uses Supabase for persistent storage with in-memory fallback.
    """

    def __init__(
        self,
        supabase_url: str | None = None,
        supabase_key: str | None = None,
    ):
        """Initialize metrics store.

        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase service key
        """
        self._supabase_url = supabase_url
        self._supabase_key = supabase_key

        # In-memory fallback
        self._metrics: list[dict] = []

        # Try to initialize Supabase client
        self._client = None
        self._use_supabase = False

        if supabase_url and supabase_key:
            try:
                from supabase import create_client

                self._client = create_client(supabase_url, supabase_key)
                # Test connection
                self._client.table("request_metrics").select("id").limit(1).execute()
                self._use_supabase = True
                logger.info("metrics_store_initialized", supabase=True)
            except ImportError:
                logger.warning(
                    "supabase_not_available",
                    message="Supabase client not installed, using in-memory fallback for metrics",
                )
            except Exception as e:
                logger.warning(
                    "supabase_connection_failed",
                    error=str(e),
                    message="Using in-memory fallback for metrics",
                )
        else:
            logger.info("metrics_store_initialized", supabase=False, in_memory=True)

    async def record_request(
        self,
        session_id: str,
        agent_name: str,
        duration_ms: float,
        model_name: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        status: str = "success",
        error_message: str | None = None,
        user_id: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Record a request metric.

        Args:
            session_id: Session identifier
            agent_name: Agent that handled the request
            duration_ms: Request duration in milliseconds
            model_name: LLM model used
            input_tokens: Input tokens processed
            output_tokens: Output tokens generated
            status: Request status (success, error, timeout)
            error_message: Error message if status is error
            user_id: Optional user identifier
            metadata: Additional metadata (langsmith_run_id, etc.)
        """
        timestamp = datetime.utcnow()
        metric_data = {
            "session_id": session_id,
            "agent_name": agent_name,
            "duration_ms": duration_ms,
            "model_name": model_name,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "status": status,
            "error_message": error_message,
            "user_id": user_id,
            "timestamp": timestamp.isoformat(),
            "metadata": metadata or {},
        }

        # Store in memory fallback
        self._metrics.append(metric_data)

        # Store in Supabase if available
        if self._use_supabase and self._client:
            try:
                self._client.table("request_metrics").insert(
                    {
                        "session_id": session_id,
                        "user_id": user_id,
                        "agent_name": agent_name,
                        "model_name": model_name,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "duration_ms": round(duration_ms),  # DB expects integer
                        "status": status,
                        "error_message": error_message,
                        "metadata": metadata or {},
                    }
                ).execute()
            except Exception as e:
                logger.error("failed_to_record_metric", error=str(e))

        logger.debug(
            "metric_recorded",
            session_id=session_id,
            agent_name=agent_name,
            model_name=model_name,
            duration_ms=duration_ms,
            status=status,
        )

    async def get_summary(self, period: str = "24h") -> dict:
        """Get aggregated metrics summary for a time period.

        Args:
            period: Time period - "24h", "7d", "30d"

        Returns:
            Dictionary with aggregated metrics
        """
        # Calculate time range
        now = datetime.utcnow()
        if period == "24h":
            start_time = now - timedelta(hours=24)
        elif period == "7d":
            start_time = now - timedelta(days=7)
        elif period == "30d":
            start_time = now - timedelta(days=30)
        else:
            start_time = now - timedelta(hours=24)

        # Get metrics from in-memory store
        metrics = [m for m in self._metrics if datetime.fromisoformat(m["timestamp"]) >= start_time]

        # Get from Supabase if available
        if self._use_supabase and self._client:
            try:
                result = (
                    self._client.table("request_metrics")
                    .select("*")
                    .gte("created_at", start_time.isoformat())
                    .execute()
                )
                # Merge with in-memory metrics (avoid duplicates by timestamp + session_id)
                seen = {(m["timestamp"], m["session_id"]) for m in metrics}
                for row in result.data:
                    key = (row.get("created_at"), row.get("session_id"))
                    if key not in seen:
                        metrics.append(
                            {
                                "session_id": row.get("session_id"),
                                "user_id": row.get("user_id"),
                                "agent_name": row.get("agent_name"),
                                "model_name": row.get("model_name"),
                                "duration_ms": row.get("duration_ms", 0),
                                "input_tokens": row.get("input_tokens", 0),
                                "output_tokens": row.get("output_tokens", 0),
                                "status": row.get("status"),
                                "timestamp": row.get("created_at"),
                            }
                        )
                        seen.add(key)
            except Exception as e:
                logger.error("failed_to_query_metrics", error=str(e))

        # Calculate aggregates
        total_requests = len(metrics)
        successful_requests = sum(1 for m in metrics if m.get("status") == "success")
        failed_requests = sum(1 for m in metrics if m.get("status") == "error")
        blocked_requests = sum(1 for m in metrics if m.get("status") == "blocked")

        total_duration = sum(m.get("duration_ms", 0) for m in metrics)
        avg_duration_ms = total_duration / total_requests if total_requests > 0 else 0

        total_input_tokens = sum(m.get("input_tokens", 0) for m in metrics)
        total_output_tokens = sum(m.get("output_tokens", 0) for m in metrics)

        # Group by agent for agent_stats
        agent_stats_map: dict[str, dict] = {}
        for m in metrics:
            agent = m.get("agent_name", "unknown")
            if agent not in agent_stats_map:
                agent_stats_map[agent] = {
                    "total_requests": 0,
                    "successful_requests": 0,
                    "failed_requests": 0,
                    "timeout_requests": 0,
                    "total_duration_ms": 0,
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                }

            agent_stats_map[agent]["total_requests"] += 1
            if m.get("status") == "success":
                agent_stats_map[agent]["successful_requests"] += 1
            elif m.get("status") == "error":
                agent_stats_map[agent]["failed_requests"] += 1
            elif m.get("status") == "timeout":
                agent_stats_map[agent]["timeout_requests"] += 1

            agent_stats_map[agent]["total_duration_ms"] += m.get("duration_ms", 0)
            agent_stats_map[agent]["total_input_tokens"] += m.get("input_tokens", 0)
            agent_stats_map[agent]["total_output_tokens"] += m.get("output_tokens", 0)

        agent_stats = []
        for agent_name, stats in agent_stats_map.items():
            avg = (
                stats["total_duration_ms"] / stats["total_requests"]
                if stats["total_requests"] > 0
                else 0
            )
            agent_stats.append(
                {
                    "agent_name": agent_name,
                    "date": start_time.strftime("%Y-%m-%d"),
                    "total_requests": stats["total_requests"],
                    "success_count": stats["successful_requests"],
                    "error_count": stats["failed_requests"],
                    "timeout_count": stats["timeout_requests"],
                    "avg_duration_ms": avg,
                    "total_input_tokens": stats["total_input_tokens"],
                    "total_output_tokens": stats["total_output_tokens"],
                }
            )

        return {
            "period": period,
            "total_requests": total_requests,
            "success_count": successful_requests,
            "error_count": failed_requests,
            "timeout_count": blocked_requests,  # Reuse blocked for timeout
            "avg_duration_ms": avg_duration_ms,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "agent_stats": agent_stats,
            "start_time": start_time,
            "end_time": now,
        }

    async def get_agent_stats(self, agent_name: str, period: str = "24h") -> dict | None:
        """Get statistics for a specific agent.

        Args:
            agent_name: Agent name to filter by
            period: Time period - "24h", "7d", "30d"

        Returns:
            Dictionary with agent statistics or None if not found
        """
        summary = await self.get_summary(period)

        # Find the specific agent stats
        for agent_stat in summary.get("agent_stats", []):
            if agent_stat.get("agent_name") == agent_name:
                return agent_stat

        return None
