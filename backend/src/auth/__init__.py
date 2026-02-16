"""Supabase authentication module.

Provides JWT-based authentication using Supabase.
"""

from src.auth.dependencies import get_current_user
from src.auth.schemas import Session, User
from src.auth.supabase_client import SupabaseAuthClient, get_supabase_client

__all__ = [
    "SupabaseAuthClient",
    "get_supabase_client",
    "get_current_user",
    "User",
    "Session",
]
