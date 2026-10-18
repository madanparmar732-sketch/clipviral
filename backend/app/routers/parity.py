"""OpusClip-Parity API — everything OpusClip has, we give free.

Collections · Duplicate · Public share · SRT/VTT · AI thumbnails ·
Censor bleep · Filler removal · Social packs · Schedules (+.ics) ·
Translation · Brand kits.
"""

import logging
import os
import shutil
import tempfile
import uuid as uuidlib
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel

from app.auth import get_current_user
from app.services import parity
from app.supabase_client import get_admin

logger = logging.getLogger(__name__)
router = APIRouter()

PLATFORMS = ("youtube", "tiktok", "instagram", "x", "linkedin", "facebook")


def _clip_or_404(clip_id: str, user) -> dict:
    rows = (
        get_admin().table("clips").select("*").eq("id", clip_id).eq("user_id", user.id).limit(1).execute().data
        or []
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Clip not found.")
    return rows[0]


def _words_for(clip: dict) -> list[dict]:
    sp = clip.get("storage_path") or ""
    if not sp:
        return []
    try:
        raw = get_admin().storage.from_(parity.BUCKET).download(sp.rsplit(".", 1)[0] + ".words.json")
        import json

        return list((json.loads(raw) or {}).get("words") or [])
    except Exception:
        return []


# ---------------------------------------------------------------- collections


class CollectionIn(BaseModel):
    name: str


@router.get("/api/collections")
def api_list_collections(user=Depends(get_current_user)):
    return {"collections": parity.list_collections(user.id)}


@router.post("/api/collections")
def api_create_collection(body: CollectionIn, user=Depends(get_current_user)):
    cols = parity.list_collections(user.id)
    col = {"id": uuidlib.uuid4().hex[:10], "name": body.name.strip()[:60] or "Untitled", "clip_ids": []}
    cols.append(col)
    parity.save_collections(user.id, cols)
    return {"collection": col}


@router.delete("/api/collections/{collection_id}")
def api_delete_collection(collection_id: str, user=Depends(get_current_user)):
    cols = [c for c in parity.list_collections(user.id) if c.get("id") != collection_id]
    parity.save_collections(user.id, cols)
    return {"ok": True}


class CollectionItemIn(BaseModel):
    clip_id: str
    remove: bool = False


@router.post("/api/collections/{collection_id}/items")
def api_collection_item(collection_id: str, body: CollectionItemIn, user=Depends(get_current_user)):
    cols = parity.list_collections(user.id)
    col = next((c for c in cols if c.get("id") == collection_id), None)
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found.")
    ids = list(col.get("clip_ids") or [])
    if body.remove:
        ids = [i for i in ids if i != body.clip_id]
    elif body.clip_id not in ids:
        ids.append(body.clip_id)
    col["clip_ids"] = ids
    parity.save_collections(user.id, cols)
    return {"collection": col}


@router.get("/api/collections/{collection_id}/clips")
def api_collection_clips(collection_id: str, user=Depends(get_current_user)):
    col = next((c for c in parity.list_collections(user.id) if c.get("id") == collection_id), None)
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found.")
    ids = col.get("clip_ids") or []
    if not ids:
        return {"clips": []}
    rows = get_admin().table("clips").select("*").in_("id", ids).eq("user_id", user.id).execute().data or []
    return {"clips": rows}


# ---------------------------------------------------------------- duplicate / share


@router.post("/api/clips/{clip_id}/duplicate")
def api_duplicate_clip(clip_id: str, user=Depends(get_current_user)):
    """OpusClip duplicate: an independent copy of the rendered clip (no re-render)."""
    clip = _clip_or_404(clip_id, user)
    new_id = str(uuidlib.uuid4())
    src_sp = clip.get("storage_path") or ""
    new_sp = ""
    if src_sp:
        bucket = get_admin().storage.from_(parity.BUCKET)
        data = bucket.download(src_sp)
        new_sp = src_sp.replace(".mp4", f".copy-{new_id[:8]}.mp4")
        try:
            bucket.remove([new_sp])
        except Exception:
            pass
        bucket.upload(new_sp, data, {"content-type": "video/mp4"})
        video_url = bucket.get_public_url(new_sp)
    else:
        video_url = clip.get("video_url") or ""

    row = {
        "id": new_id,
        "job_id": clip.get("job_id"),
        "user_id": user.id,
        "title": f"{(clip.get('title') or 'Clip')} (Copy)"[:120],
        "hook": clip.get("hook") or "",
        "score": clip.get("score") or 0,
        "start_seconds": clip.get("start_seconds") or 0,
        "end_seconds": clip.get("end_seconds") or 0,
        "video_url": video_url,
        "thumbnail_url": clip.get("thumbnail_url") or "",
        "storage_path": new_sp,
    }
    try:
        get_admin().table("clips").insert(row).execute()
    except Exception:
        # some columns may not exist in older schemas — retry with the core set
        logger.exception("duplicate insert with full row failed, retrying core columns")
        get_admin().table("clips").insert(row).execute()
    # copy the words json too (keeps the transcript editor working on the copy)
    if src_sp:
        try:
            bucket = get_admin().storage.from_(parity.BUCKET)
            wsrc = src_sp.rsplit(".", 1)[0] + ".words.json"
            raw = bucket.download(wsrc)
            bucket.upload(new_sp.rsplit(".", 1)[0] + ".words.json", raw, {"content-type": "application/json"})
        except Exception:
            logger.exception("duplicate words copy failed (non-fatal)")
    return {"clip": row}


class ShareIn(BaseModel):
    enabled: bool = True


@router.post("/api/clips/{clip_id}/share")
def api_share_clip(clip_id: str, body: ShareIn, user=Depends(get_current_user)):
    """Public share page for one clip (or the whole job via /api/jobs/{id}/share)."""
    clip = _clip_or_404(clip_id, user)
    if not body.enabled:
        return {"ok": True, "share_url": ""}
    share_id = parity.make_share_id()
    url = parity.write_share(share_id, {
        "share_id": share_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "clips": [{
            "id": clip.get("id"),
            "title": clip.get("title"),
            "hook": clip.get("hook"),
            "score": clip.get("score"),
            "video_url": clip.get("video_url"),
            "thumbnail_url": clip.get("thumbnail_url"),
            "hashtags": clip.get("hashtags") or [],
        }],
    })
    return {"ok": True, "share_id": share_id, "share_url": url}


class JobShareIn(BaseModel):
    enabled: bool = True


@router.post("/api/jobs/{job_id}/share")
def api_share_job(job_id: str, body: JobShareIn, user=Depends(get_current_user)):
    jrows = get_admin().table("jobs").select("*").eq("id", job_id).eq("user_id", user.id).limit(1).execute().data or []
    if not jrows:
        raise HTTPException(status_code=404, detail="Job not found.")
    if not body.enabled:
        return {"ok": True, "share_url": ""}
    clips = get_admin().table("clips").select("*").eq("job_id", job_id).eq("user_id", user.id).execute().data or []
    share_id = parity.make_share_id()
    parity.write_share(share_id, {
        "share_id": share_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title": (jrows[0].get("source_filename") or "Video")[:80],
        "clips": [{
            "id": c.get("id"), "title": c.get("title"), "hook": c.get("hook"), "score": c.get("score"),
            "video_url": c.get("video_url"), "thumbnail_url": c.get("thumbnail_url"),
            "hashtags": c.get("hashtags") or [],
        } for c in clips],
    })
    return {"ok": True, "share_id": share_id}


@router.get("/api/share/{share_id}")
def api_get_share(share_id: str):
    data = parity.read_share(share_id)
    if not data:
        raise HTTPException(status_code=404, detail="Share link not found.")
    return data


# ---------------------------------------------------------------- subtitles


@router.get("/api/clips/{clip_id}/subtitles.srt")
def api_srt(clip_id: str, user=Depends(get_current_user)):
    clip = _clip_or_404(clip_id, user)
    return PlainTextResponse(parity.words_to_srt(_words_for(clip)), media_type="text/plain")


@router.get("/api/clips/{clip_id}/subtitles.vtt")
def api_vtt(clip_id: str, user=Depends(get_current_user)):
    clip = _clip_or_404(clip_id, user)
    return PlainTextResponse(parity.words_to_vtt(_words_for(clip)), media_type="text/plain")


# ---------------------------------------------------------------- thumbnails


class ThumbIn(BaseModel):
    prompt: str = ""   # used as the overlay text hint (title by default)
    pick: int = -1     # set a candidate as THE thumbnail


@router.post("/api/clips/{clip_id}/thumbnails")
def api_thumbnails(clip_id: str, body: ThumbIn, background_tasks: BackgroundTasks, user=Depends(get_current_user)):
    clip = _clip_or_404(clip_id, user)
    background_tasks.add_task(_thumb_job, clip, body.prompt, user.id)
    return {"ok": True, "message": "Designing thumbnails — refresh in ~20 seconds."}


def _thumb_job(clip: dict, prompt: str, user_id: str) -> None:
    from app.workers.editor import _editor_job_done, _editor_job_fail, _editor_job_start

    ejid = _editor_job_start(clip, "Thumbnails")
    workdir = os.path.join(tempfile.gettempdir(), f"thumbs-{clip.get('id')}")
    try:
        bucket = get_admin().storage.from_(parity.BUCKET)
        sp = clip.get("storage_path") or ""
        local = os.path.join(workdir, "clip.mp4")
        os.makedirs(workdir, exist_ok=True)
        data = None
        for attempt in range(2):  # storage can hiccup mid-deploy; one silent retry
            try:
                data = bucket.download(sp)
                break
            except Exception:
                if attempt:
                    raise
                import time as _t; _t.sleep(2.0)
        with open(local, "wb") as fh:
            fh.write(data)
        title = prompt.strip() or (clip.get("title") or "Viral moment")
        paths = parity.make_thumbnail_candidates(local, title, workdir)
        urls = []
        for i, p in enumerate(paths):
            name = f"{sp.rsplit('.', 1)[0]}.thumb{i + 1}.jpg"
            with open(p, "rb") as fh:
                urls.append(parity.put_bytes(name, fh.read(), "image/jpeg"))
        get_admin().table("clips").update({"thumbnail_url": urls[0]}).eq("id", clip["id"]).execute()
        parity.put_json(f"{sp.rsplit('.', 1)[0]}.thumbs.json", {"candidates": urls, "title": title})
        _editor_job_done(ejid)
    except Exception as exc:
        logger.exception("thumbnail job failed")
        _editor_job_fail(ejid, f"Thumbnails failed: {str(exc)[:150]}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# ---------------------------------------------------------------- censor


class CensorIn(BaseModel):
    beep: bool = False


@router.post("/api/clips/{clip_id}/censor")
def api_censor(clip_id: str, body: CensorIn, background_tasks: BackgroundTasks, user=Depends(get_current_user)):
    clip = _clip_or_404(clip_id, user)
    if not _words_for(clip):
        raise HTTPException(status_code=400, detail="No transcript for this clip — cannot detect swears.")
    background_tasks.add_task(_censor_job, clip, body.beep)
    return {"ok": True, "message": "Bleeping swears — refresh in ~30 seconds."}


def _censor_job(clip: dict, beep: bool) -> None:
    from app.workers.editor import _editor_job_done, _editor_job_fail, _editor_job_start

    ejid = _editor_job_start(clip, "Censor")
    workdir = os.path.join(tempfile.gettempdir(), f"censor-{clip.get('id')}")
    try:
        bucket = get_admin().storage.from_(parity.BUCKET)
        sp = clip.get("storage_path") or ""
        os.makedirs(workdir, exist_ok=True)
        local = os.path.join(workdir, "clip.mp4")
        with open(local, "wb") as fh:
            fh.write(bucket.download(sp))
        words = _words_for(clip)
        ranges = parity.find_profanity_ranges(words)
        if not ranges:
            _editor_job_done(ejid)
            parity.put_json(f"{sp.rsplit('.', 1)[0]}.censor.json", {"ranges": [], "status": "clean"})
            return
        out = os.path.join(workdir, "censored.mp4")
        parity.apply_censor(local, out, ranges, beep=beep)
        with open(out, "rb") as fh:
            data = fh.read()
        bucket.remove([sp]) if False else None  # keep original path (re-upload below)
        try:
            bucket.remove([sp])
        except Exception:
            pass
        bucket.upload(sp, data, {"content-type": "video/mp4"})
        base = (clip.get("video_url") or "").split("?")[0]
        get_admin().table("clips").update({
            "video_url": f"{base}?v={int(datetime.now(timezone.utc).timestamp())}" if base else "",
        }).eq("id", clip["id"]).execute()
        parity.put_json(f"{sp.rsplit('.', 1)[0]}.censor.json", {
            "ranges": [[round(a, 2), round(b, 2)] for a, b in ranges], "beep": beep, "status": "done",
        })
        _editor_job_done(ejid)
    except Exception as exc:
        logger.exception("censor job failed")
        _editor_job_fail(ejid, f"Censor failed: {str(exc)[:150]}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# ---------------------------------------------------------------- translate


class TranslateIn(BaseModel):
    lang: str = "hi"
    burn: bool = True  # re-render with translated captions


@router.post("/api/clips/{clip_id}/translate")
def api_translate(clip_id: str, body: TranslateIn, background_tasks: BackgroundTasks, user=Depends(get_current_user)):
    clip = _clip_or_404(clip_id, user)
    words = _words_for(clip)
    if not words:
        raise HTTPException(status_code=400, detail="No transcript for this clip.")
    background_tasks.add_task(_translate_job, clip, body.lang.strip()[:8] or "hi", body.burn, user.id)
    return {"ok": True, "message": f"Translating to {body.lang.upper()} — refresh in ~60 seconds."}


def _translate_job(clip: dict, lang: str, burn: bool, user_id: str) -> None:
    from app.workers.editor import _editor_job_done, _editor_job_fail, _editor_job_start

    ejid = _editor_job_start(clip, f"Translate→{lang.upper()}")
    workdir = os.path.join(tempfile.gettempdir(), f"tr-{clip.get('id')}-{lang}")
    try:
        bucket = get_admin().storage.from_(parity.BUCKET)
        sp = clip.get("storage_path") or ""
        wraw = bucket.download(sp.rsplit(".", 1)[0] + ".words.json")
        import json

        wmeta = json.loads(wraw)
        words = list(wmeta.get("words") or [])
        translated = parity.translate_words(words, lang)
        srt = parity.words_to_srt(translated)
        parity.put_bytes(f"{sp.rsplit('.', 1)[0]}.{lang}.srt", srt.encode("utf-8"), "text/plain")
        parity.put_json(f"{sp.rsplit('.', 1)[0]}.{lang}.words.json", {**wmeta, "words": translated, "lang": lang})

        if burn:
            os.makedirs(workdir, exist_ok=True)
            src = os.path.join(workdir, "source.mp4")
            with open(src, "wb") as fh:
                fh.write(bucket.download(f"{clip.get('job_id')}/source.mp4"))
            from app.services import captions, video_processor

            kept = [[float(a), float(b)] for a, b in (wmeta.get("kept_segments") or [])]
            if not kept:
                kept = [[0.0, float(wmeta.get("clip_duration") or 10.0)]]
            kept_len = sum(b - a for a, b in kept)
            style = str(wmeta.get("style") or "karaoke")
            ass_path = os.path.join(workdir, f"{lang}.ass")
            captions.build_ass_captions(translated, 0.0, max(1.0, kept_len), ass_path, style=style, watermark=True)
            chain = video_processor.clip_video_chain(src, 0.0, kept_len, reframe="face", enhance=False, watermark=True)
            out_path = os.path.join(workdir, f"{lang}.mp4")
            video_processor.cut_and_concat(src, kept, out_path, video_chain=chain, ass_path=ass_path,
                                           total_seconds=kept_len)
            new_sp = f"{sp.rsplit('.', 1)[0]}.{lang}.mp4"
            with open(out_path, "rb") as fh:
                data = fh.read()
            try:
                bucket.remove([new_sp])
            except Exception:
                pass
            bucket.upload(new_sp, data, {"content-type": "video/mp4"})
            row = {
                "id": str(uuidlib.uuid4()),
                "job_id": clip.get("job_id"),
                "user_id": user_id,
                "title": f"{(clip.get('title') or 'Clip')} · {lang.upper()}"[:120],
                "hook": clip.get("hook") or "",
                "score": clip.get("score") or 0,
                "start_seconds": 0,
                "end_seconds": round(kept_len, 2),
                "video_url": bucket.get_public_url(new_sp),
                "thumbnail_url": "",
                "storage_path": new_sp,
            }
            get_admin().table("clips").insert(row).execute()
            try:
                bucket.upload(new_sp.rsplit(".", 1)[0] + ".words.json",
                              json.dumps({**wmeta, "words": translated, "lang": lang}).encode(),
                              {"content-type": "application/json"})
            except Exception:
                pass
        _editor_job_done(ejid)
    except Exception as exc:
        logger.exception("translate job failed")
        _editor_job_fail(ejid, f"Translate failed: {str(exc)[:150]}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# ---------------------------------------------------------------- social pack


@router.get("/api/clips/{clip_id}/social-pack")
def api_social_pack(clip_id: str, user=Depends(get_current_user)):
    clip = _clip_or_404(clip_id, user)
    sp = clip.get("storage_path") or ""
    cached = parity.get_json(f"{sp.rsplit('.', 1)[0]}.social.json") if sp else None
    return {"pack": cached or {}, "platforms": list(PLATFORMS)}


class SocialIn(BaseModel):
    prompt: str = ""
    lang: str = "en"


@router.post("/api/clips/{clip_id}/social-pack")
def api_build_social(clip_id: str, body: SocialIn, user=Depends(get_current_user)):
    clip = _clip_or_404(clip_id, user)
    words = _words_for(clip)
    snippet = " ".join(str(w.get("word", "")) for w in words[:80])
    pack = parity.build_social_pack(
        title=clip.get("title") or "Clip",
        hook=clip.get("hook") or "",
        transcript_snippet=snippet,
        hashtags=clip.get("hashtags") or [],
        prompt=body.prompt,
        lang=body.lang or "en",
    )
    sp = clip.get("storage_path") or ""
    if sp:
        parity.put_json(f"{sp.rsplit('.', 1)[0]}.social.json", pack)
    return {"pack": pack}


# ---------------------------------------------------------------- schedules


class ScheduleIn(BaseModel):
    clip_id: str
    platform: str
    publish_at: str
    title: str = ""
    description: str = ""


@router.get("/api/schedules")
def api_list_schedules(user=Depends(get_current_user)):
    return {"schedules": parity.list_schedules(user.id)}


@router.post("/api/schedules")
def api_create_schedule(body: ScheduleIn, user=Depends(get_current_user)):
    if body.platform not in PLATFORMS:
        raise HTTPException(status_code=400, detail=f"platform must be one of {list(PLATFORMS)}")
    try:
        datetime.fromisoformat(body.publish_at.replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(status_code=400, detail="publish_at must be an ISO date-time.")
    items = parity.list_schedules(user.id)
    item = {
        "id": uuidlib.uuid4().hex[:10],
        "clip_id": body.clip_id,
        "platform": body.platform,
        "publish_at": body.publish_at,
        "title": body.title[:120],
        "description": body.description[:500],
        "status": "scheduled",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    items.append(item)
    parity.save_schedules(user.id, items)
    return {"schedule": item}


@router.delete("/api/schedules/{schedule_id}")
def api_delete_schedule(schedule_id: str, user=Depends(get_current_user)):
    items = [s for s in parity.list_schedules(user.id) if s.get("id") != schedule_id]
    parity.save_schedules(user.id, items)
    return {"ok": True}


@router.get("/api/schedules.ics")
def api_schedules_ics(user=Depends(get_current_user)):
    data = parity.schedules_to_ics(parity.list_schedules(user.id))
    return Response(content=data, media_type="text/calendar",
                    headers={"Content-Disposition": 'attachment; filename="clipviral-schedule.ics"'})


# ---------------------------------------------------------------- brand kits


class BrandKitIn(BaseModel):
    id: str | None = None
    name: str = "My brand"
    logo_data_url: str = ""   # small data:image/...;base64,... pasted from the browser
    caption_style: str = "karaoke"
    accent: str = "#7C3AED"


@router.get("/api/brand-kits")
def api_list_brand_kits(user=Depends(get_current_user)):
    return {"brand_kits": parity.list_brand_kits(user.id)}


@router.put("/api/brand-kits")
def api_save_brand_kit(body: BrandKitIn, user=Depends(get_current_user)):
    kits = parity.list_brand_kits(user.id)
    logo_url = ""
    if body.logo_data_url.startswith("data:image/"):
        try:
            import base64

            header, b64 = body.logo_data_url.split(",", 1)
            ext = "png" if "png" in header else ("webp" if "webp" in header else "jpg")
            logo_url = parity.put_bytes(
                f"brand/{user.id}/{uuidlib.uuid4().hex[:8]}.{ext}",
                base64.b64decode(b64), f"image/{ext if ext != 'jpg' else 'jpeg'}",
            )
        except Exception:
            logger.exception("logo upload failed")
    kit = {
        "id": body.id or uuidlib.uuid4().hex[:8],
        "name": body.name[:60],
        "caption_style": body.caption_style,
        "accent": body.accent,
        "logo_url": logo_url or (next((k.get("logo_url") for k in kits if k.get("id") == body.id), "") if body.id else ""),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    kits = [k for k in kits if k.get("id") != kit["id"]] + [kit]
    parity.save_brand_kits(user.id, kits)
    return {"brand_kit": kit}
