"""Night-batch render queue — the "100 videos on a tiny CPU" trick.

The live pipeline inserts a clip card IMMEDIATELY (title/hook/score/thumbnail-
less) and queues the heavy encode here. During the quiet window (default
1:30-6:30 IST) — when Render's free box has no users to keep waiting — a
background loop renders every pending clip with full captions and fills the
card in. If a user can't wait, "Render now" flips the asset to priority mode
and it goes out on the next free minute.

Table (see supabase/night_batch.sql):
  render_assets(id uuid, job_id, clip_id, user_id, clip_index int,
                mode text 'night'|'now', status 'queued'|'processing'|'done'|'failed',
                payload jsonb, attempts int, heartbeat timestamptz, created_at)
Everything degrades gracefully: if the table is missing, queue_night_render
returns False and the pipeline renders exactly like it used to.
"""
from __future__ import annotations

import json
import logging
import shutil
import os
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))
_STALE_MIN = 40
_done_ok = True  # flips False when the table is absent (stop nagging supabase)


def _admin():
    from app.supabase_client import get_admin

    return get_admin()


def in_night_window() -> bool:
    from app.config import settings

    now = datetime.now(IST)
    start, end = settings.night_start_hour, settings.night_end_hour
    h = now.hour + now.minute / 60.0
    return (h >= start or h < end) if start > end else (start <= h < end)


def _touch(asset_id: str, **fields) -> None:
    try:
        _admin().table("render_assets").update(fields).eq("id", asset_id).execute()
    except Exception:
        pass


def queue_night_render(*, job_id: str, clip_id: str, user_id: str | None,
                       clip_index: int, payload: dict) -> bool:
    """True = queued for later. False = queue unavailable, render NOW."""
    global _done_ok
    try:
        _admin().table("render_assets").insert({
            "id": str(uuid.uuid4()),
            "job_id": job_id,
            "clip_id": clip_id,
            "user_id": user_id,
            "clip_index": clip_index,
            "mode": "night",
            "status": "queued",
            "payload": payload,
            "attempts": 0,
        }).execute()
        return True
    except Exception as exc:
        if _done_ok:
            logger.info("render_assets queue unavailable (%s) - lazy mode off", str(exc)[:120])
        _done_ok = False
        return False


def requeue_now(clip_id: str) -> bool:
    """'Render now' button: flip the pending asset to priority mode."""
    try:
        upd = _admin().table("render_assets").update({"mode": "now"}).eq("clip_id", clip_id).eq("status", "queued").execute()
        if (upd.data or []):
            return True
        # asset vanished (already done?) — treat as no-op
        return False
    except Exception:
        return False


def _claim(window: bool) -> dict | None:
    """Atomically take one queued asset. `window` gates night-mode items."""
    global _done_ok
    from app.config import settings

    try:
        res = (
            _admin().table("render_assets")
            .select("*")
            .eq("status", "queued")
            .order("created_at")
            .limit(1)
            .execute()
        )
        rows = res.data or []
    except Exception as exc:
        if _done_ok:
            logger.info("night claim failed (%s)", str(exc)[:100])
        _done_ok = False
        return None
    for row in rows:
        if row.get("mode") == "night" and not (window and _idle_ok()):
            continue
        upd = (
            _admin().table("render_assets")
            .update({"status": "processing",
                     "heartbeat": datetime.now(timezone.utc).isoformat()})
            .eq("id", row["id"]).eq("status", "queued").execute()
        )
        if upd.data:
            return row
    return None


def _idle_ok() -> bool:
    """Don't fight the live job queue for the CPU."""
    try:
        from app.workers import pipeline

        with pipeline._INFLIGHT_LOCK:
            if pipeline._INFLIGHT:
                return False
    except Exception:
        pass
    try:
        from app.config import settings
        from app.services.lease import has_fresh_lease  # noqa: F401
        if getattr(settings, "phone_worker", False):
            # phone/gpu own the jobs; night box may still use leftover CPU — ok
            return True
    except Exception:
        pass
    return True


def _reset_stale() -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=_STALE_MIN)).isoformat()
    try:
        _admin().table("render_assets").update({"status": "queued"}).eq("status", "processing").lt("heartbeat", cutoff).execute()
    except Exception:
        pass


def _render_asset(asset: dict) -> None:
    from app.config import settings
    from app.services import captions, storage, video_processor

    aid = asset["id"]
    job_id = asset["job_id"]
    clip_id = asset["clip_id"]
    idx = int(asset.get("clip_index") or 1)
    payload = asset.get("payload") or {}
    if isinstance(payload, str):
        payload = json.loads(payload or "{}")

    workdir = os.path.join(settings.media_dir, job_id, "night")
    os.makedirs(workdir, exist_ok=True)
    try:
        source = os.path.join(workdir, "source.mp4")
        _dj = os.path.join(settings.media_dir, job_id, ".direct.txt")
        _direct = open(_dj).read().strip() if os.path.exists(_dj) else ""
        if _direct:
            source = _direct  # stream-first job: night renders from CDN too
        elif not os.path.exists(source):
            if not storage.download_file_from_storage(f"{job_id}/source.mp4", source):
                raise RuntimeError("source missing")

        kept = [tuple(s) for s in payload.get("kept") or [[payload["start"], payload["end"]]]]
        words = [{"start": w["start"], "end": w["end"], "word": w.get("word", "")}
                 for w in payload.get("words") or []]
        total = sum(b - a for a, b in kept) or 1.0

        ass_path = os.path.join(workdir, f"clip_{idx}.ass")
        captions.build_ass_captions(words, 0.0, max(1.0, total), ass_path,
                                    style=str(payload.get("style") or "karaoke"),
                                    watermark=bool(payload.get("watermark")))
        chain = video_processor.clip_video_chain(
            source, float(payload["start"]), float(payload["end"]),
            reframe=str(payload.get("reframe") or "face"),
            enhance=bool(payload.get("enhance")),
            watermark=bool(payload.get("watermark")),
            aspect=str(payload.get("aspect") or "9:16"),
        )
        clip_path = os.path.join(workdir, f"out_{idx}.mp4")
        video_processor.cut_and_concat(source, kept, clip_path,
                                       video_chain=chain, ass_path=ass_path,
                                       total_seconds=total)
        if payload.get("sfx"):
            try:
                sfx = video_processor.make_sfx(workdir)
                starts = captions.line_start_times(words)[:12]
                if starts:
                    paths = [sfx["whoosh"] if i == 0 else sfx["pop"] for i in range(len(starts))]
                    video_processor.mix_sfx(clip_path, clip_path + ".sfx.mp4", paths, starts)
                    os.replace(clip_path + ".sfx.mp4", clip_path)
            except Exception:
                logger.exception("night sfx failed (non-fatal)")

        thumb_path = os.path.join(workdir, f"clip_{idx}.jpg")
        thumb_url = ""
        try:
            video_processor.make_thumbnail(clip_path, thumb_path)
            thumb_url = storage.upload_file_to_storage(thumb_path, f"{job_id}/clip_{idx}.jpg")
        except Exception:
            logger.exception("night thumbnail failed (non-fatal)")

        storage_path = f"{job_id}/clip_{idx}.mp4"
        video_url = storage.upload_file_to_storage(clip_path, storage_path)
        _admin().table("clips").update({
            "video_url": video_url,
            "thumbnail_url": thumb_url,
            "storage_path": storage_path,
        }).eq("id", clip_id).execute()
        _touch(aid, status="done", heartbeat=datetime.now(timezone.utc).isoformat())
        logger.info("night asset %s rendered for clip %s", aid[:8], clip_id[:8])
    except Exception as exc:
        attempts = int(asset.get("attempts") or 0) + 1
        _touch(aid, status="failed" if attempts >= 3 else "queued",
               attempts=attempts, error=str(exc)[:300],
               heartbeat=datetime.now(timezone.utc).isoformat())
        logger.warning("night render %s failed (attempt %s): %s", aid[:8], attempts, str(exc)[:200])
    finally:
        try:
            shutil.rmtree(workdir, ignore_errors=True)
        except Exception:
            pass




def night_loop() -> None:
    """One background thread: eats the night queue in the quiet window, plus
    'now' priority items whenever the CPU is free."""
    from app.config import settings

    logger.info("night-batch renderer armed (window %s-%s IST)",
                settings.night_start_hour, settings.night_end_hour)
    last_reset = 0.0
    while True:
        try:
            if time.time() - last_reset > 1800:
                _reset_stale()
                last_reset = time.time()
            from app.workers.pipeline import _INFLIGHT, _INFLIGHT_LOCK
            if _INFLIGHT_LOCK and len(_INFLIGHT) > 0:
                time.sleep(45)  # a heavy job is running — don't stack memory
                continue
            work = _claim(window=in_night_window())
            if work:
                _render_asset(work)
                continue
            time.sleep(60)
        except Exception:
            logger.exception("night loop error - retrying in 60s")
            time.sleep(60)
