"""Rate limit store using Supabase for persistence."""

from datetime import UTC, datetime, timedelta


class RateLimitStore:
    """Rate limit storage interface."""

    async def get_minute_count(self) -> tuple[int, datetime]:
        """Get current minute count and reset time."""
        ...

    async def increment_minute(self) -> None:
        """Increment minute counter."""
        ...

    async def get_hour_count(self) -> tuple[int, datetime]:
        """Get current hour count and reset time."""
        ...

    async def increment_hour(self) -> None:
        """Increment hour counter."""
        ...

    async def get_daily_count(self) -> tuple[int, datetime]:
        """Get current daily count and reset time."""
        ...

    async def increment_daily(self) -> None:
        """Increment daily counter."""
        ...

    async def get_google_rate_limit_info(self) -> dict:
        """Get stored Google API rate limit info."""
        ...

    async def set_google_rate_limit_info(self, info: dict) -> None:
        """Store Google API rate limit info."""
        ...


class InMemoryRateLimitStore(RateLimitStore):
    """In-memory rate limit storage (no persistence)."""

    def __init__(self) -> None:
        """Initialize in-memory rate limit store."""
        self._minute_count = 0
        self._minute_reset_at = datetime.now(tz=UTC)

        self._hour_count = 0
        self._hour_reset_at = datetime.now(tz=UTC)

        self._daily_count = 0
        self._daily_reset_at = datetime.now(tz=UTC)

        self._google_rate_limit_info: dict = {}

    async def get_minute_count(self) -> tuple[int, datetime]:
        """Get current minute count and reset time."""
        return self._minute_count, self._minute_reset_at

    async def increment_minute(self) -> None:
        """Increment minute counter."""
        self._minute_count += 1

    async def get_hour_count(self) -> tuple[int, datetime]:
        """Get current hour count and reset time."""
        return self._hour_count, self._hour_reset_at

    async def increment_hour(self) -> None:
        """Increment hour counter."""
        self._hour_count += 1

    async def get_daily_count(self) -> tuple[int, datetime]:
        """Get current daily count and reset time."""
        return self._daily_count, self._daily_reset_at

    async def increment_daily(self) -> None:
        """Increment daily counter."""
        self._daily_count += 1

    async def get_google_rate_limit_info(self) -> dict:
        """Get stored Google API rate limit info."""
        return self._google_rate_limit_info

    async def set_google_rate_limit_info(self, info: dict) -> None:
        """Store Google API rate limit info."""
        self._google_rate_limit_info = info


class SupabaseRateLimitStore(RateLimitStore):
    """Supabase-backed rate limit storage with persistence."""

    def __init__(self, supabase_url: str, supabase_key: str) -> None:
        """Initialize Supabase rate limit store.

        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase service role key
        """
        self._client: object | None = None
        self._table_name = "rate_limits"

        try:
            from httpx import AsyncClient, Limits
            from supabase import ClientOptions, create_client  # type: ignore[attr-defined]

            limits = Limits(
                max_connections=5,
                max_keepalive_connections=2,
            )
            http_client = AsyncClient(
                limits=limits,
                timeout=10.0,
            )
            options = ClientOptions(http_client=http_client)
            self._client = create_client(supabase_url, supabase_key, options=options)
        except (ImportError, Exception):
            self._client = None

    @property
    def is_available(self) -> bool:
        """Check if Supabase client is available."""
        return self._client is not None

    async def _get_or_create_counter(self, metric_type: str) -> dict:
        """Get or create a counter record."""
        if not self.is_available:
            raise RuntimeError("Supabase client not available")

        try:
            response = self._client.table(self._table_name).select("*").eq(
                "metric_type", metric_type
            ).execute()

            if response.data and len(response.data) > 0:
                return response.data[0]

            # Create new counter
            now = datetime.now(tz=UTC)
            reset_at = now + timedelta(
                seconds=60 if metric_type == "minute"
                else 3600 if metric_type == "hour"
                else 86400
            )

            new_record = {
                "metric_type": metric_type,
                "count": 0,
                "reset_at": reset_at.isoformat(),
            }
            self._client.table(self._table_name).insert(new_record).execute()
            return new_record
        except Exception as e:
            raise RuntimeError(f"Failed to get rate limit counter: {e}")

    async def get_minute_count(self) -> tuple[int, datetime]:
        """Get current minute count and reset time."""
        if not self.is_available:
            raise RuntimeError("Supabase client not available")

        record = await self._get_or_create_counter("minute")
        return (
            record.get("count", 0),
            datetime.fromisoformat(record.get("reset_at", datetime.now(tz=UTC).isoformat())),
        )

    async def increment_minute(self) -> None:
        """Increment minute counter."""
        if not self.is_available:
            raise RuntimeError("Supabase client not available")

        try:
            record = await self._get_or_create_counter("minute")
            self._client.table(self._table_name).update(
                {"count": record.get("count", 0) + 1}
            ).eq("metric_type", "minute").execute()
        except Exception as e:
            raise RuntimeError(f"Failed to increment minute counter: {e}")

    async def get_hour_count(self) -> tuple[int, datetime]:
        """Get current hour count and reset time."""
        if not self.is_available:
            raise RuntimeError("Supabase client not available")

        record = await self._get_or_create_counter("hour")
        return (
            record.get("count", 0),
            datetime.fromisoformat(record.get("reset_at", datetime.now(tz=UTC).isoformat())),
        )

    async def increment_hour(self) -> None:
        """Increment hour counter."""
        if not self.is_available:
            raise RuntimeError("Supabase client not available")

        try:
            record = await self._get_or_create_counter("hour")
            self._client.table(self._table_name).update(
                {"count": record.get("count", 0) + 1}
            ).eq("metric_type", "hour").execute()
        except Exception as e:
            raise RuntimeError(f"Failed to increment hour counter: {e}")

    async def get_daily_count(self) -> tuple[int, datetime]:
        """Get current daily count and reset time."""
        if not self.is_available:
            raise RuntimeError("Supabase client not available")

        record = await self._get_or_create_counter("daily")
        return (
            record.get("count", 0),
            datetime.fromisoformat(record.get("reset_at", datetime.now(tz=UTC).isoformat())),
        )

    async def increment_daily(self) -> None:
        """Increment daily counter."""
        if not self.is_available:
            raise RuntimeError("Supabase client not available")

        try:
            record = await self._get_or_create_counter("daily")
            self._client.table(self._table_name).update(
                {"count": record.get("count", 0) + 1}
            ).eq("metric_type", "daily").execute()
        except Exception as e:
            raise RuntimeError(f"Failed to increment daily counter: {e}")

    async def get_google_rate_limit_info(self) -> dict:
        """Get stored Google API rate limit info."""
        if not self.is_available:
            raise RuntimeError("Supabase client not available")

        try:
            response = self._client.table(self._table_name).select("*").eq(
                "metric_type", "google"
            ).execute()

            if response.data and len(response.data) > 0:
                record = response.data[0]
                return {
                    "remaining_requests": record.get("remaining_requests", -1),
                    "remaining_tokens": record.get("remaining_tokens", -1),
                    "limit_requests": record.get("limit_requests", -1),
                    "limit_tokens": record.get("limit_tokens", -1),
                }
            return {}
        except Exception as e:
            raise RuntimeError(f"Failed to get Google rate limit info: {e}")

    async def set_google_rate_limit_info(self, info: dict) -> None:
        """Store Google API rate limit info."""
        if not self.is_available:
            raise RuntimeError("Supabase client not available")

        try:
            response = self._client.table(self._table_name).select("*").eq(
                "metric_type", "google"
            ).execute()

            record_data = {
                "metric_type": "google",
                "remaining_requests": info.get("remaining_requests", -1),
                "remaining_tokens": info.get("remaining_tokens", -1),
                "limit_requests": info.get("limit_requests", -1),
                "limit_tokens": info.get("limit_tokens", -1),
            }

            if response.data and len(response.data) > 0:
                # Update existing
                self._client.table(self._table_name).update(record_data).eq(
                    "metric_type", "google"
                ).execute()
            else:
                # Create new
                self._client.table(self._table_name).insert(record_data).execute()
        except Exception as e:
            raise RuntimeError(f"Failed to set Google rate limit info: {e}")
