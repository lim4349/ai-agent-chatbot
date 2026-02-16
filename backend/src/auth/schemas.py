"""Authentication schemas for Supabase integration."""


class User:
    """User model from Supabase auth.users."""

    def __init__(self, id: str, email: str, created_at: str | None = None):
        """Initialize user.

        Args:
            id: User UUID from Supabase
            email: User email address
            created_at: ISO timestamp of user creation
        """
        self.id = id
        self.email = email
        self.created_at = created_at

    def __eq__(self, other: object) -> bool:
        """Check equality based on id."""
        if not isinstance(other, User):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        """Hash based on id."""
        return hash(self.id)

    def __repr__(self) -> str:
        """String representation."""
        return f"User(id={self.id!r}, email={self.email!r})"


class Session:
    """Session model for authenticated user sessions."""

    def __init__(
        self,
        access_token: str,
        user: User,
        expires_at: str | None = None,
        refresh_token: str | None = None,
    ):
        """Initialize session.

        Args:
            access_token: JWT access token
            user: Authenticated user
            expires_at: ISO timestamp of token expiration
            refresh_token: Refresh token for obtaining new access tokens
        """
        self.access_token = access_token
        self.user = user
        self.expires_at = expires_at
        self.refresh_token = refresh_token

    def __repr__(self) -> str:
        """String representation."""
        return f"Session(user={self.user!r}, expires_at={self.expires_at!r})"
