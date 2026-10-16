"""Transcript-based editor: re-cuts a finished clip by removing chosen time ranges.

The user strikes out words/sentences in the UI; we cut those parts out of the
already-rendered clip and glue the rest back together (captions included).
"""

import json
import logging
import os
import shutil

from app.config import settings
from app.services import video_processor
from app.services.captions import remap_words
from app.services.storage import upload_file_to_storage
from app.supabase_client import get_admin

logger = logging.getLogger(__name__)


def re_edit_clip_job(clip_id: str, removed: list[tuple[float, float]]) -> None:
    admin = get_admin()
    clip_res = admin.table("clips").select("*").eq("id", clip_id).limit(1).execute()
    rows = clip_res.data or []
    if not rows:
        return
    clip = rows[0]
    storage_path = clip.get("storage_path")
    if not storage_path:
        return

    workdir = os.path.join(settings.media_dir, f"edit-{clip_id}")
    os.makedirs(workdir, exist_ok=True)
    try:
        # 1) Download the current clip
        local = os.path.join(workdir, "in.mp4")
        data = admin.storage.from_(settings.clips_bucket).download(storage_path)
        with open(local, "wb") as f:
            f.write(data)

        info = video_processor.probe_video(local)
        duration = float(info.get("duration") or 0)

        # 2) kept parts = everything except the removed ranges
        removed = sorted((max(0.0, a), min(duration, b)) for a, b in removed if b > a)
        kept: list[tuple[float, float]] = []
        cursor = 0.0
        for a, b in removed:
            if a - cursor > 0.1:
                kept.append((cursor, a))
            cursor = max(cursor, b)
        if duration - cursor > 0.1:
            kept.append((cursor, duration))
        if not kept:
            raise RuntimeError("You removed everything — keep at least a little video.")

        # 3) Cut + glue (captions are already in the file)
        out = os.path.join(workdir, "out.mp4")
        video_processor.cut_and_concat(local, kept, out)

        # 4) Replace the stored file (remove + upload = overwrite)
        bucket = admin.storage.from_(settings.clips_bucket)
        try:
            bucket.remove([storage_path])
        except Exception:
            pass
        upload_file_to_storage(out, storage_path)

        # 5) Refresh the words.json so the editor matches the new video
        try:
            words_path = storage_path.rsplit(".", 1)[0] + ".words.json"
            raw = bucket.download(words_path)
            wdata = json.loads(raw)
            remapped = remap_words(wdata.get("words") or [], kept)
            payload = json.dumps(
                {"clip_duration": round(sum(b - a for a, b in kept), 3), "words": remapped}
            ).encode("utf-8")
            try:
                bucket.remove([words_path])
            except Exception:
                pass
            bucket.upload(words_path, payload, {"content-type": "application/json"})
        except Exception:
            logger.exception("words.json refresh failed (not fatal)")

        # 6) Cache-bust the video URL so the browser fetches the new file
        from datetime import datetime, timezone

        base_url = (clip.get("video_url") or "").split("?")[0]
        if base_url:
            bust = f"{base_url}?v={int(datetime.now(timezone.utc).timestamp())}"
        else:
            bust = ""
        admin.table("clips").update(
            {
                "video_url": bust,
                "start_seconds": 0,
                "end_seconds": round(sum(b - a for a, b in kept), 3),
            }
        ).eq("id", clip_id).execute()
        logger.info("Clip %s re-cut: kept %.1fs of %.1fs", clip_id, sum(b - a for a, b in kept), duration)
    except Exception:
        logger.exception("Re-edit failed for clip %s", clip_id)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
