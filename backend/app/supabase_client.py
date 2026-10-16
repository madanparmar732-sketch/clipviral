"""Supabase admin client. Used by the backend to talk to the database and file storage."""

from functools import lru_cache

from supabase import Client, create_client

from app.config import settings


@lru_cache
def get_admin() -> Client:
    """
    Returns a Supabase client that uses the SERVICE ROLE key.
    This key is like a master key: it can write to the database and storage.
    It lives ONLY on the backend (Render) — never in the website code.
    """
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in the environment (.env)."
        )
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
