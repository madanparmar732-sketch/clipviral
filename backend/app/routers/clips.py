"""Download links for finished clips."""

import httpx
from pydantic import BaseModel
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
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

    _editor_precheck(response.data[0])
    background_tasks.add_task(re_edit_clip_job, clip_id, removed)
    return {
        "ok": True,
        "message": "Re-cutting your clip — press Refresh in about a minute to see it.",
    }


def _editor_precheck(clip: dict) -> None:
    """Fail fast with a HUMAN message if this clip can't be re-rendered."""
    from app.config import settings

    sp = clip.get("storage_path")
    job_id = clip.get("job_id")
    if not sp or not job_id:
        raise HTTPException(status_code=400, detail="This clip is too old for editing — please re-generate the clips for this video.")
    bucket = get_admin().storage.from_(settings.clips_bucket)
    names = [f.get("name") for f in (bucket.list(job_id, {"limit": 100}) or [])]
    if "source.mp4" not in names:
        raise HTTPException(status_code=400, detail="The original video was already cleaned up — please upload this video again to edit.")
    try:
        wraw = bucket.download(sp.rsplit(".", 1)[0] + ".words.json")
        import json as _json

        wmeta = _json.loads(wraw)
    except Exception:
        wmeta = {}
    if "kept_segments" not in wmeta or "words" not in wmeta:
        raise HTTPException(status_code=400, detail="This clip has no transcript data — please re-generate the clips for this video.")



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

    _editor_precheck(response.data[0])
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


class RecaptionIn(BaseModel):
    style: str = "none"   # "none" strips captions entirely


@router.post("/api/clips/{clip_id}/recaption")
def recaption(clip_id: str, body: RecaptionIn, background_tasks: BackgroundTasks,
              user=Depends(get_current_user)):
    """Re-render this clip with a different caption style — or no captions."""
    from app.services.captions import STYLE_PRESETS

    if body.style not in STYLE_PRESETS:
        raise HTTPException(status_code=400, detail=f"Unknown style '{body.style}'.")
    rows = (
        get_admin().table("clips").select("id, user_id")
        .eq("id", clip_id).limit(1).execute().data or []
    )
    if not rows or rows[0].get("user_id") != user.id:
        raise HTTPException(status_code=404, detail="Clip not found.")
    background_tasks.add_task(_run_recaption, clip_id, body.style)
    return {"ok": True, "message": "Re-rendering with new captions — refresh in ~2 minutes."}


def _run_recaption(clip_id: str, style: str) -> None:
    from app.workers.pipeline import recaption_clip

    recaption_clip(clip_id, style)


@router.post("/api/clips/{clip_id}/render-now")
def render_now(clip_id: str, user=Depends(get_current_user)):
    """'Can't wait for tonight?' — bump this clip's encode to priority."""
    rows = (
        get_admin().table("clips").select("id, video_url")
        .eq("id", clip_id).eq("user_id", user.id).limit(1).execute().data or []
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Clip not found.")
    if rows[0].get("video_url"):
        return {"ok": True, "already": True}
    from app.services import assets as _assets

    if not _assets.requeue_now(clip_id):
        raise HTTPException(status_code=409, detail="Nothing pending for this clip.")
    return {"ok": True}


# ---------------- Browser Studio video proxy (CORS-safe fallback) ----------------
_ALLOWED_PROXY_HOSTS = ("dkavqwoolwomouajmcsy.supabase.co",)


@router.get("/api/proxy")
async def proxy_video(url: str, request: Request):
    """Buffered CORS proxy for storage videos (fallback when direct load fails)."""
    from urllib.parse import urlparse

    from fastapi.responses import Response as RawResponse

    host = urlparse(url).hostname or ""
    if host not in _ALLOWED_PROXY_HOSTS:
        raise HTTPException(status_code=400, detail="Only ClipViral storage URLs are allowed.")
    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            upstream = await client.get(url)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not fetch video: {exc}"[:200])
    return RawResponse(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "video/mp4"),
        headers={
            "Access-Control-Allow-Origin": "*",
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=3600",
        },
    )


# ---------------- Self-Doctor: public health endpoint ----------------
@router.get("/api/health")
def api_health():
    """Live system report. Also runs auto-fixes every time it is called."""
    from app.services import doctor

    fixes = doctor.auto_fixes()
    checks = doctor.quick_checks()
    bad = {k: v for k, v in checks.items() if isinstance(v, str) and v.startswith("FAIL")}
    try:
        doctor._report(checks, fixes)
    except Exception:
        pass
    return {
        "ok": not bad,
        "build": "2026-10-17.1",  # bump on every deploy so we can see which code is live
        "checks": checks,
        "fixed_now": fixes,
        "time": doctor._now_iso(),
    }
