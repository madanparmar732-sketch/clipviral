"""Checks "who are you?" on every API call, using the Supabase login token."""

from fastapi import Header, HTTPException

from app.supabase_client import get_admin


def get_current_user(authorization: str = Header(default="")):
    """
    Every protected endpoint depends on this.
    The browser sends:  Authorization: Bearer <token-from-supabase-login>
    We ask Supabase: "is this token real, and who does it belong to?"
    """
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header. Please log in.")

    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Empty login token. Please log in.")

    try:
        response = get_admin().auth.get_user(token)
        user = response.user
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired login token. Please log in again.")

    if user is None:
        raise HTTPException(status_code=401, detail="Invalid login token. Please log in again.")
    return user
