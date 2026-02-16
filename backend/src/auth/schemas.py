"""Authentication schemas for Supabase integration."""

from pydantic import BaseModel, Field


class User(BaseModel):
    """User model from Supabase auth.users."""

    id: str = Field(..., description="User UUID from Supabase")
    email: str = Field(..., description="User email address")
    created_at: str | None = Field(default=None, description="ISO timestamp of user creation")

    def __hash__(self) -> int:
        """Hash based on id for use in sets/dicts."""
        return hash(self.id)


class Session(BaseModel):
    """Session model for authenticated user sessions."""

    access_token: str = Field(..., description="JWT access token")
    user: User = Field(..., description="Authenticated user")
    expires_at: str | None = Field(default=None, description="ISO timestamp of token expiration")
    refresh_token: str | None = Field(
        default=None, description="Refresh token for obtaining new access tokens"
    )
