"""Supabase authentication client."""

import os
from functools import lru_cache
from typing import Any

import httpx
from pydantic import ValidationError

from src.auth.schemas import Session, User
from src.core.config import get_config


class SupabaseAuthError(Exception):
    """Supabase authentication error."""

    def __init__(self, message: str, status_code: int | None = None):
        """Initialize error.

        Args:
            message: Error message
            status_code: HTTP status code if applicable
        """
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class SupabaseAuthClient:
    """Client for Supabase authentication.

    Provides JWT token verification and user retrieval.
    """

    def __init__(self, url: str, service_key: str):
        """Initialize Supabase client.

        Args:
            url: Supabase project URL
            service_key: Supabase service role key (has admin privileges)
        """
        self.url = url.rstrip("/")
        self.service_key = service_key
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get async HTTP client (lazy initialization)."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.url,
                headers={
                    "apikey": self.service_key,
                    "Authorization": f"Bearer {self.service_key}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def verify_token(self, token: str) -> User:
        """Verify JWT token and return user.

        Args:
            token: JWT access token from Supabase

        Returns:
            User object

        Raises:
            SupabaseAuthError: If token is invalid or verification fails
        """
        try:
            response = await self.client.get(
                "/auth/v1/user",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()

            data = response.json()
            return User(
                id=data["id"],
                email=data["email"],
                created_at=data.get("created_at"),
            )

        except httpx.HTTPStatusError as e:
            raise SupabaseAuthError(
                f"Token verification failed: {e.response.text}",
                status_code=e.response.status_code,
            ) from e
        except (KeyError, ValueError) as e:
            raise SupabaseAuthError(f"Invalid user data: {e}") from e
        except httpx.RequestError as e:
            raise SupabaseAuthError(f"Request to Supabase failed: {e}") from e

    async def get_user(self, user_id: str) -> User:
        """Get user by ID using service key.

        Args:
            user_id: User UUID

        Returns:
            User object

        Raises:
            SupabaseAuthError: If user not found or request fails
        """
        try:
            response = await self.client.get(f"/auth/v1/admin/users/{user_id}")
            response.raise_for_status()

            data = response.json()
            return User(
                id=data["id"],
                email=data["email"],
                created_at=data.get("created_at"),
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise SupabaseAuthError(f"User not found: {user_id}", status_code=404) from e
            raise SupabaseAuthError(
                f"Failed to get user: {e.response.text}",
                status_code=e.response.status_code,
            ) from e
        except (KeyError, ValueError) as e:
            raise SupabaseAuthError(f"Invalid user data: {e}") from e
        except httpx.RequestError as e:
            raise SupabaseAuthError(f"Request to Supabase failed: {e}") from e


def _get_supabase_config() -> tuple[str, str]:
    """Get Supabase URL and service key from environment.

    Returns:
        Tuple of (url, service_key)

    Raises:
        SupabaseAuthError: If configuration is missing
    """
    # Check environment variables directly
    url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_KEY")

    if not url:
        raise SupabaseAuthError("SUPABASE_URL environment variable is not set")
    if not service_key:
        raise SupabaseAuthError("SUPABASE_SERVICE_KEY environment variable is not set")

    return url, service_key


@lru_cache
def get_supabase_client() -> SupabaseAuthClient:
    """Get cached Supabase client instance.

    Returns:
        SupabaseAuthClient instance

    Raises:
        SupabaseAuthError: If configuration is missing
    """
    url, service_key = _get_supabase_config()
    return SupabaseAuthClient(url=url, service_key=service_key)
