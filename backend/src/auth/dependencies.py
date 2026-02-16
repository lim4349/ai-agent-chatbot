"""FastAPI dependencies for authentication."""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from src.auth.schemas import User
from src.auth.supabase_client import SupabaseAuthClient, SupabaseAuthError, get_supabase_client


async def _get_token_from_header(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """Extract JWT token from Authorization header.

    Args:
        authorization: Authorization header value

    Returns:
        JWT access token

    Raises:
        HTTPException: If header is missing or malformed
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Authorization header must start with "Bearer "',
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization[7:].strip()  # Remove "Bearer " prefix
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is empty",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token


async def get_current_user(
    token: Annotated[str, Depends(_get_token_from_header)],
    client: Annotated[SupabaseAuthClient, Depends(get_supabase_client)],
) -> User:
    """Get the currently authenticated user from JWT token.

    FastAPI dependency that verifies the JWT token with Supabase
    and returns the user object.

    Args:
        token: JWT access token from Authorization header
        client: Supabase auth client

    Returns:
        Authenticated user

    Raises:
        HTTPException: If token is invalid or user not found
    """
    try:
        return await client.verify_token(token)
    except SupabaseAuthError as e:
        status_code = (
            status.HTTP_401_UNAUTHORIZED
            if e.status_code is None or e.status_code == 401
            else status.HTTP_403_FORBIDDEN
        )
        raise HTTPException(
            status_code=status_code,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


# Type alias for convenience
CurrentUser = Annotated[User, Depends(get_current_user)]
