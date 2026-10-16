"""Download links for finished clips."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from app.auth import get_current_user
from app.config import settings
from app.supabase_client import get_admin

router = APIRouter()


@router.get("/api/clips/{clip_id}/download")
def download_clip(clip_id: str, user=Depends(get_current_user)):
    """
    Gives a fresh, short-lived download link for one clip.
    The browser follows the redirect and the video downloads.
    """
    response = (
        get_admin()
        .table("clips")
        .select("*")
        .eq("id", clip_id)
        .eq("user_id", user.id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Clip not found.")

    clip = rows[0]
    storage_path = clip.get("storage_path")
    if not storage_path:
        raise HTTPException(status_code=404, detail="This clip has no file yet.")

    try:
        result = get_admin().storage.from_(settings.clips_bucket).create_signed_url(storage_path, 600)
        signed_url = result.get("signedURL") or result.get("signed_url") or result.get("url")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not create download link: {exc}")

    if not signed_url:
        raise HTTPException(status_code=500, detail="Storage returned no download link.")

    return RedirectResponse(url=signed_url, status_code=307)
