"""Authentication and authorization dependencies for FastAPI."""

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


@dataclass
class User:
    """Authenticated user model."""

    id: str
    email: str
    created_at: datetime | None = None


security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Security(security)],
) -> User:
    """Get the current authenticated user from Authorization header.

    Args:
        credentials: HTTP Bearer credentials

    Returns:
        User object

    Raises:
        HTTPException: If authentication fails
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # TODO: Integrate with Supabase auth
    # For now, implement a simple token validation
    # In production, validate JWT token with Supabase

    # Example Supabase validation (to be implemented):
    # try:
    #     supabase_client = get_supabase_client()
    #     user = supabase_client.auth.get_user(token)
    #     if not user or not user.user:
    #         raise HTTPException(status_code=401, detail="Invalid token")
    #
    #     return User(
    #         id=user.user.id,
    #         email=user.user.email,
    #         created_at=user.user.created_at,
    #     )
    # except Exception as e:
    #     raise HTTPException(status_code=401, detail="Invalid token") from e

    # Temporary: Extract user_id from token (placeholder)
    # In production, validate proper JWT
    if not token or token == "invalid":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # For development: allow test tokens
    # Format: "test_user_<user_id>" or use actual JWT
    if token.startswith("test_user_"):
        user_id = token.replace("test_user_", "")
        return User(
            id=user_id,
            email=f"test{user_id}@example.com",
            created_at=datetime.utcnow(),
        )

    # TODO: Replace with actual Supabase JWT validation
    # For now, return a mock user for testing
    return User(
        id="dev_user",
        email="dev@example.com",
        created_at=datetime.utcnow(),
    )


async def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Security(security)],
) -> User | None:
    """Get the current user if authenticated, otherwise return None.

    This is useful for endpoints that work with or without authentication.

    Args:
        credentials: HTTP Bearer credentials (optional)

    Returns:
        User object if authenticated, None otherwise
    """
    if credentials is None:
        return None

    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None
