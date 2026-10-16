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


def pro_edit_clip_job(clip_id: str, opts: dict) -> None:
    """Pro Editor: FULL re-render from the stored source — new caption style,
    trim, enhance, sfx, reframe — in original quality."""
    from app.services.captions import FREE_STYLES, build_ass_captions
    from app.services.storage import upload_file_to_storage

    admin = get_admin()
    rows = admin.table("clips").select("*").eq("id", clip_id).limit(1).execute().data or []
    if not rows:
        return
    clip = rows[0]
    storage_path = clip.get("storage_path")
    job_id = clip.get("job_id")
    if not storage_path or not job_id:
        return

    workdir = os.path.join(settings.media_dir, f"pro-{clip_id}")
    os.makedirs(workdir, exist_ok=True)
    try:
        # ---- who is this + what can they use ----
        job_rows = admin.table("jobs").select("user_id").eq("id", job_id).limit(1).execute().data or []
        user_id = job_rows[0].get("user_id") if job_rows else None
        is_pro = False
        prefs = {"reframe": "face"}
        if user_id:
            try:
                res = admin.auth.get_user_by_id(user_id)
                u = getattr(res, "user", res)
                meta = getattr(u, "user_metadata", None) or {}
                is_pro = bool(meta.get("is_pro", False))
                prefs.update({k: meta[k] for k in ("reframe",) if k in meta})
            except Exception:
                pass
        if not is_pro:
            raise RuntimeError("The Pro Editor is a Pro feature — upgrade to use it.")

        # ---- source + words metadata ----
        bucket = admin.storage.from_(settings.clips_bucket)
        try:
            source_bytes = bucket.download(f"{job_id}/source.mp4")
        except Exception:
            source_bytes = None
        wraw = bucket.download(storage_path.rsplit(".", 1)[0] + ".words.json")
        wmeta = json.loads(wraw)
        if not source_bytes or "kept_segments" not in wmeta or "source_start" not in wmeta:
            raise RuntimeError("Full re-render needs the source copy (old clip) — please re-upload this video.")

        source_local = os.path.join(workdir, "source.mp4")
        with open(source_local, "wb") as f:
            f.write(source_bytes)

        # ---- trim window on the clip timeline ----
        total_len = float(wmeta.get("clip_duration") or 0)
        ts = max(0.0, float(opts.get("trim_start") or 0.0))
        te = min(total_len, float(opts.get("trim_end") or total_len))
        if te - ts < 2.0:
            raise RuntimeError("Trim is too short — keep at least 2 seconds.")

        segs = [(float(a), float(b)) for a, b in wmeta["kept_segments"]]
        mapped: list[tuple[float, float]] = []
        offset = 0.0
        for a, b in segs:
            seg_len = b - a
            lo, hi = max(offset, ts), min(offset + seg_len, te)
            if hi - lo > 0.1:
                mapped.append((a + (lo - offset), a + (hi - offset)))
            offset += seg_len
        if not mapped:
            raise RuntimeError("Nothing left after trimming.")

        words = [
            {"start": max(0.0, float(w["start"]) - ts),
             "end": max(0.05, min(te, float(w["end"])) - ts),
             "word": w.get("word", "")}
            for w in wmeta.get("words", [])
            if float(w.get("end", 0)) > ts and float(w.get("start", 0)) < te
        ]
        new_len = te - ts

        style = str(opts.get("style") or wmeta.get("style") or "beast")
        if style not in FREE_STYLES and not is_pro:
            style = "beast"

        ass_path = os.path.join(workdir, "edit.ass")
        build_ass_captions(words, 0.0, max(1.0, new_len), ass_path, style=style)

        chain = video_processor.clip_video_chain(
            source_local, mapped[0][0], mapped[-1][1],
            reframe=str(opts.get("reframe") or prefs.get("reframe") or "face"),
            enhance=bool(opts.get("enhance")),
            watermark=False,
        )
        out = os.path.join(workdir, "out.mp4")
        video_processor.cut_and_concat(
            source_local, mapped, out,
            video_chain=chain, ass_path=ass_path, total_seconds=new_len,
        )

        if opts.get("sfx"):
            try:
                sfx = video_processor.make_sfx(workdir)
                starts = [w["start"] for i, w in enumerate(words) if i % 4 == 0][:12]
                if starts:
                    paths = [sfx["whoosh"] if i == 0 else sfx["pop"] for i in range(len(starts))]
                    video_processor.mix_sfx(out, out + ".sfx.mp4", paths, starts)
                    os.replace(out + ".sfx.mp4", out)
            except Exception:
                logger.exception("SFX failed (not fatal)")

        # ---- replace stored files ----
        try:
            bucket.remove([storage_path])
        except Exception:
            pass
        upload_file_to_storage(out, storage_path)

        new_words_payload = json.dumps({
            "clip_duration": round(new_len, 3),
            "source_start": wmeta.get("source_start"),
            "source_end": wmeta.get("source_end"),
            "kept_segments": [[round(a, 3), round(b, 3)] for a, b in mapped],
            "style": style,
            "words": [{"start": round(w["start"], 3), "end": round(w["end"], 3), "word": w["word"]} for w in words],
        }).encode("utf-8")
        words_path = storage_path.rsplit(".", 1)[0] + ".words.json"
        try:
            bucket.remove([words_path])
        except Exception:
            pass
        bucket.upload(words_path, new_words_payload, {"content-type": "application/json"})

        from datetime import datetime, timezone
        base_url = (clip.get("video_url") or "").split("?")[0]
        admin.table("clips").update({
            "video_url": f"{base_url}?v={int(datetime.now(timezone.utc).timestamp())}" if base_url else "",
            "start_seconds": 0,
            "end_seconds": round(new_len, 3),
        }).eq("id", clip_id).execute()
        logger.info("Pro re-render OK for clip %s (style=%s, %.1fs)", clip_id, style, new_len)
    except Exception as exc:
        logger.exception("Pro edit failed for clip %s", clip_id)
        try:
            admin.table("clips").update({"hook": f"Editor: {str(exc)[:110]}"}).eq("id", clip_id).execute()
        except Exception:
            pass
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
