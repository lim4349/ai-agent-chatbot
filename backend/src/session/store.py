"""Session store implementations."""

import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass
class Session:
    """Session data model."""

    id: str
    user_id: str
    title: str
    metadata: dict[str, object]
    created_at: datetime
    updated_at: datetime


@runtime_checkable
class SessionStore(Protocol):
    """Session storage interface."""

    async def create(
        self,
        session_id: str,
        user_id: str,
        title: str,
        metadata: dict[str, object] | None = None,
    ) -> Session:
        """Create a new session.

        Args:
            session_id: Unique session identifier
            user_id: Owner user ID
            title: Session title
            metadata: Optional session metadata

        Returns:
            Created session
        """
        ...

    async def get(self, session_id: str) -> Session | None:
        """Get a session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session or None if not found
        """
        ...

    async def list_by_user(self, user_id: str) -> list[Session]:
        """List all sessions for a user.

        Args:
            user_id: User identifier

        Returns:
            List of sessions sorted by created_at descending
        """
        ...

    async def delete(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted, False if not found
        """
        ...

    async def exists(self, session_id: str) -> bool:
        """Check if a session exists.

        Args:
            session_id: Session identifier

        Returns:
            True if session exists
        """
        ...


class InMemorySessionStore:
    """In-memory session storage with thread-safe access.

    Falls back to this implementation when Supabase is not configured.
    """

    def __init__(self) -> None:
        """Initialize in-memory session store."""
        self._sessions: dict[str, dict[str, object]] = {}
        self._lock = threading.Lock()

    async def create(
        self,
        session_id: str,
        user_id: str,
        title: str,
        metadata: dict[str, object] | None = None,
    ) -> Session:
        """Create a new session."""
        now = datetime.utcnow()
        session_data = {
            "id": session_id,
            "user_id": user_id,
            "title": title,
            "created_at": now,
            "updated_at": now,
            "metadata": metadata or {},
        }

        with self._lock:
            self._sessions[session_id] = session_data

        return Session(
            id=str(session_data["id"]),
            user_id=str(session_data["user_id"]),
            title=str(session_data["title"]),
            metadata=dict(session_data["metadata"]),  # type: ignore[arg-type]
            created_at=session_data["created_at"],  # type: ignore[arg-type]
            updated_at=session_data["updated_at"],  # type: ignore[arg-type]
        )

    async def get(self, session_id: str) -> Session | None:
        """Get a session by ID."""
        with self._lock:
            data = self._sessions.get(session_id)
            if not data:
                return None
            return Session(
                id=str(data["id"]),
                user_id=str(data["user_id"]),
                title=str(data["title"]),
                metadata=dict(data["metadata"]),  # type: ignore[arg-type]
                created_at=data["created_at"],  # type: ignore[arg-type]
                updated_at=data["updated_at"],  # type: ignore[arg-type]
            )

    async def list_by_user(self, user_id: str) -> list[Session]:
        """List all sessions for a user."""
        with self._lock:
            user_sessions = [
                Session(
                    id=str(data["id"]),
                    user_id=str(data["user_id"]),
                    title=str(data["title"]),
                    metadata=dict(data["metadata"]),  # type: ignore[arg-type]
                    created_at=data["created_at"],  # type: ignore[arg-type]
                    updated_at=data["updated_at"],  # type: ignore[arg-type]
                )
                for data in self._sessions.values()
                if data["user_id"] == user_id
            ]

        # Sort by created_at descending
        user_sessions.sort(key=lambda s: s.created_at, reverse=True)
        return user_sessions

    async def delete(self, session_id: str) -> bool:
        """Delete a session."""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    async def exists(self, session_id: str) -> bool:
        """Check if a session exists."""
        with self._lock:
            return session_id in self._sessions


class SupabaseSessionStore:
    """Supabase-backed session storage.

    Requires SUPABASE_URL and SUPABASE_KEY environment variables.
    Falls back to InMemorySessionStore if not configured.
    """

    def __init__(
        self,
        supabase_url: str,
        supabase_key: str,
        table_name: str = "sessions",
    ) -> None:
        """Initialize Supabase session store.

        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase service role key
            table_name: Name of sessions table
        """
        self._table_name = table_name
        self._client: object | None = None

        try:
            from supabase import create_client  # type: ignore[attr-defined]

            self._client = create_client(supabase_url, supabase_key)
        except ImportError:
            # supabase-py not installed, will use fallback
            self._client = None
        except Exception:
            # Connection failed, will use fallback
            self._client = None

    @property
    def is_available(self) -> bool:
        """Check if Supabase client is available."""
        return self._client is not None

    async def create(
        self,
        session_id: str,
        user_id: str,
        title: str,
        metadata: dict[str, object] | None = None,
    ) -> Session:
        """Create a new session in Supabase."""
        if not self.is_available:
            raise RuntimeError("Supabase client not available")

        now = datetime.utcnow()
        data = {
            "id": session_id,
            "user_id": user_id,
            "title": title,
            "metadata": metadata or {},
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        response = (
            self._client.table(self._table_name)  # type: ignore[union-attr]
            .insert(data)
            .execute()
        )

        if response.data:
            row = response.data[0]
            return Session(
                id=row["id"],
                user_id=row["user_id"],
                title=row["title"],
                metadata=row.get("metadata", {}),
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )

        raise RuntimeError(f"Failed to create session: {response}")

    async def get(self, session_id: str) -> Session | None:
        """Get a session by ID from Supabase."""
        if not self.is_available:
            raise RuntimeError("Supabase client not available")

        response = (
            self._client.table(self._table_name)  # type: ignore[union-attr]
            .select("*")
            .eq("id", session_id)
            .limit(1)
            .execute()
        )

        if response.data:
            row = response.data[0]
            return Session(
                id=row["id"],
                user_id=row["user_id"],
                title=row["title"],
                metadata=row.get("metadata", {}),
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )

        return None

    async def list_by_user(self, user_id: str) -> list[Session]:
        """List all sessions for a user from Supabase."""
        if not self.is_available:
            raise RuntimeError("Supabase client not available")

        response = (
            self._client.table(self._table_name)  # type: ignore[union-attr]
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )

        sessions = []
        for row in response.data:
            sessions.append(
                Session(
                    id=row["id"],
                    user_id=row["user_id"],
                    title=row["title"],
                    metadata=row.get("metadata", {}),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
            )

        return sessions

    async def delete(self, session_id: str) -> bool:
        """Delete a session from Supabase."""
        if not self.is_available:
            raise RuntimeError("Supabase client not available")

        response = (
            self._client.table(self._table_name)  # type: ignore[union-attr]
            .delete()
            .eq("id", session_id)
            .execute()
        )

        return len(response.data) > 0

    async def exists(self, session_id: str) -> bool:
        """Check if a session exists in Supabase."""
        return await self.get(session_id) is not None
