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


# ==================== TRANSCRIPT-BASED EDITOR ====================

from pydantic import BaseModel  # noqa: E402
from fastapi import BackgroundTasks  # noqa: E402

from app.workers.editor import re_edit_clip_job  # noqa: E402


class ReEditRequest(BaseModel):
    # Time ranges (seconds, clip-relative) to REMOVE from the clip.
    removed: list[list[float]]


@router.post("/api/clips/{clip_id}/re-edit")
async def re_edit_clip(
    clip_id: str,
    payload: ReEditRequest,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
):
    """Transcript editor: cut out the parts the user struck out, keep the rest."""
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

    removed: list[tuple[float, float]] = []
    for pair in payload.removed:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            continue
        try:
            a, b = float(pair[0]), float(pair[1])
        except (TypeError, ValueError):
            continue
        if b - a > 0.05:
            removed.append((a, b))

    if not removed:
        raise HTTPException(status_code=400, detail="Select at least one word to remove.")

    background_tasks.add_task(re_edit_clip_job, clip_id, removed)
    return {
        "ok": True,
        "message": "Re-cutting your clip — press Refresh in about a minute to see it.",
    }


class ProEditRequest(BaseModel):
    style: str | None = None
    trim_start: float | None = None
    trim_end: float | None = None
    enhance: bool | None = None
    sfx: bool | None = None
    reframe: str | None = None
    removed: list[list[float]] | None = None
    aspect: str | None = None
    layout: str | None = None
    caption_pos: str | None = None
    size_scale: float | None = None
    caps: bool | None = None
    brightness: float | None = None
    contrast: float | None = None
    saturation: float | None = None
    volume: float | None = None
    words_override: list[dict] | None = None


@router.post("/api/clips/{clip_id}/pro-edit")
async def pro_edit_clip(
    clip_id: str,
    payload: ProEditRequest,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
):
    """Pro Editor: re-render this clip with new style/trim/polish (full quality)."""
    from app.workers.editor import pro_edit_clip_job

    response = (
        get_admin().table("clips").select("*").eq("id", clip_id).eq("user_id", user.id).limit(1).execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Clip not found.")

    background_tasks.add_task(pro_edit_clip_job, clip_id, payload.dict())
    return {"ok": True, "message": "Re-rendering in full quality — press Refresh in about a minute."}


# ==================== EDITOR: clip fetch + details ====================

@router.get("/api/clips/{clip_id}")
def get_clip(clip_id: str, user=Depends(get_current_user)):
    """One clip (for the editor page)."""
    rows = (
        get_admin().table("clips").select("*")
        .eq("id", clip_id).eq("user_id", user.id).limit(1).execute().data or []
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Clip not found.")
    return {"clip": rows[0]}


class ClipMeta(BaseModel):
    title: str | None = None
    hook: str | None = None
    hashtags: list[str] | None = None


@router.patch("/api/clips/{clip_id}")
def update_clip_meta(clip_id: str, payload: ClipMeta, user=Depends(get_current_user)):
    """Update clip details (title / hook / hashtags)."""
    fields = {k: v for k, v in payload.dict().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="Nothing to update.")
    if "title" in fields:
        fields["title"] = str(fields["title"])[:70]
    if "hook" in fields:
        fields["hook"] = str(fields["hook"])[:120]
    if "hashtags" in fields:
        fields["hashtags"] = [str(t)[:30] for t in fields["hashtags"]][:5]
    get_admin().table("clips").update(fields).eq("id", clip_id).eq("user_id", user.id).execute()
    return {"ok": True}
