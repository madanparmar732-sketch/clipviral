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
    if _editor_cancelled(clip_id):
        return
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
    ejid = _editor_job_start(clip, "Re-cut")
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
        _editor_job_done(ejid)
    except Exception as exc:
        logger.exception("Re-edit failed for clip %s", clip_id)
        _editor_job_fail(ejid, f"Re-cut failed: {str(exc)[:160]}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def pro_edit_clip_job(clip_id: str, opts: dict) -> None:
    if _editor_cancelled(clip_id):
        return
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
    ejid = _editor_job_start(clip, "Editor render")
    try:
        # ---- who is this + what can they use ----
        job_rows = admin.table("jobs").select("user_id").eq("id", job_id).limit(1).execute().data or []
        user_id = job_rows[0].get("user_id") if job_rows else None
        is_pro = False
        prefs = {"reframe": "face"}
        if user_id:
            try:
                _auth = admin.auth
                res = getattr(_auth, "admin", _auth).get_user_by_id(user_id)
                u = getattr(res, "user", res)
                meta = getattr(u, "user_metadata", None) or {}
                is_pro = bool(meta.get("is_pro", False))
                prefs.update({k: meta[k] for k in ("reframe",) if k in meta})
            except Exception:
                pass
        # Editor is FREE for everyone. (Pro only removes the watermark below.)

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

        # ---- trim + struck-out words -> keep windows on the clip timeline ----
        total_len = float(wmeta.get("clip_duration") or 0)
        ts = max(0.0, float(opts.get("trim_start") or 0.0))
        te = min(total_len, float(opts.get("trim_end") or total_len))
        if te - ts < 1.5:
            raise RuntimeError("Trim is too short — keep at least 1.5 seconds.")

        removed = []
        for pair in opts.get("removed") or []:
            try:
                a, b = float(pair[0]), float(pair[1])
            except (TypeError, ValueError, IndexError):
                continue
            a, b = max(ts, a), min(te, b)
            if b - a > 0.05:
                removed.append((a, b))
        removed.sort()

        keep_windows = []
        cur = ts
        for a, b in removed:
            if a - cur > 0.1:
                keep_windows.append((cur, a))
            cur = max(cur, b)
        if te - cur > 0.1:
            keep_windows.append((cur, te))
        if not keep_windows:
            raise RuntimeError("You removed everything — keep at least a little video!")

        segs = [(float(a), float(b)) for a, b in wmeta["kept_segments"]]
        all_words = wmeta.get("words", [])
        override = opts.get("words_override") or []
        if isinstance(override, list) and override:
            all_words = [
                {"start": float(w.get("start", 0)), "end": float(w.get("end", 0)), "word": str(w.get("word", ""))}
                for w in override if isinstance(w, dict)
            ]

        mapped: list[tuple[float, float]] = []
        words: list[dict] = []
        new_len = 0.0
        for w_start, w_end in keep_windows:
            offset = 0.0
            for a, b in segs:
                seg_len = b - a
                lo, hi = max(offset, w_start), min(offset + seg_len, w_end)
                if hi - lo > 0.1:
                    mapped.append((a + (lo - offset), a + (hi - offset)))
                offset += seg_len
            win_len = w_end - w_start
            for w in all_words:
                ws, we = float(w.get("start", 0)), float(w.get("end", 0))
                if we <= w_start or ws >= w_end:
                    continue
                ns = max(0.0, ws - w_start) + new_len
                ne = min(win_len, we - w_start) + new_len
                if ne - ns > 0.03:
                    words.append({"start": round(ns, 3), "end": round(ne, 3), "word": w.get("word", "")})
            new_len += win_len
        if not mapped:
            raise RuntimeError("Nothing left after cutting.")

        style = str(opts.get("style") or wmeta.get("style") or "beast")
        if style not in FREE_STYLES and not is_pro:
            style = "beast"

        ass_path = os.path.join(workdir, "edit.ass")
        build_ass_captions(
            words, 0.0, max(1.0, new_len), ass_path, style=style,
            watermark=not is_pro,
            pos=str(opts.get("caption_pos") or "bottom"),
            size_scale=max(0.5, min(1.6, float(opts.get("size_scale") or 1.0))),
            caps=bool(opts.get("caps", True)),
        )

        aspect = str(opts.get("aspect") or "9:16")
        layout = str(opts.get("layout") or "full")
        chain = video_processor.clip_video_chain(
            source_local, mapped[0][0], mapped[-1][1],
            reframe=str(opts.get("reframe") or prefs.get("reframe") or "face"),
            enhance=bool(opts.get("enhance")),
            watermark=not is_pro,
            aspect=aspect, layout=layout,
            brightness=float(opts.get("brightness") or 0.0),
            contrast=float(opts.get("contrast") or 1.0),
            saturation=float(opts.get("saturation") or 1.0),
        )
        size_map = video_processor.ASPECT_SIZES_HD if opts.get("enhance") else video_processor.ASPECT_SIZES
        ow, oh = size_map.get(aspect, size_map["9:16"])
        post_vf = video_processor.pad_post_filter(ow, oh) if layout == "pad" else ""
        audio_chain = ""
        if opts.get("volume") is not None:
            audio_chain = f"volume={max(0.1, min(3.0, float(opts.get('volume')))):.2f}"
        out = os.path.join(workdir, "out.mp4")
        video_processor.cut_and_concat(
            source_local, mapped, out,
            video_chain=chain, ass_path=ass_path, total_seconds=new_len,
            post_vf=post_vf, audio_chain=audio_chain,
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
        _editor_job_done(ejid)
    except Exception as exc:
        logger.exception("Pro edit failed for clip %s", clip_id)
        _editor_job_fail(ejid, f"Editor render failed: {str(exc)[:160]}")
        try:
            admin.table("clips").update({"hook": f"Editor: {str(exc)[:110]}"}).eq("id", clip_id).execute()
        except Exception:
            pass
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _editor_cancelled(clip_id: str) -> bool:
    """True if the parent job was cancelled by the user."""
    try:
        rows = get_admin().table("clips").select("job_id").eq("id", clip_id).limit(1).execute().data or []
        if not rows:
            return True
        jrows = (
            get_admin().table("jobs").select("status").eq("id", rows[0].get("job_id")).limit(1).execute().data or []
        )
        return bool(jrows and jrows[0].get("status") == "cancelled")
    except Exception:
        return False


def _editor_job_start(clip: dict, kind: str) -> str | None:
    """Create a visible 'Editor render' job so the dashboard shows progress/errors."""
    try:
        import uuid as _uuid

        job_id = str(_uuid.uuid4())
        job_rows = get_admin().table("jobs").select("user_id").eq("id", clip.get("job_id")).limit(1).execute().data or []
        user_id = job_rows[0].get("user_id") if job_rows else None
        get_admin().table("jobs").insert(
            {
                "id": job_id,
                "user_id": user_id,
                "status": "processing",
                "stage": "rendering",
                "progress": 35,
                "source_filename": f"{kind}: {(clip.get('title') or 'clip')[:60]}",
                "source_size_bytes": 0,
            }
        ).execute()
        return job_id
    except Exception:
        logger.exception("could not create editor job row")
        return None


def _editor_job_done(job_id: str | None) -> None:
    if not job_id:
        return
    try:
        get_admin().table("jobs").delete().eq("id", job_id).execute()
    except Exception:
        pass


def _editor_job_fail(job_id: str | None, message: str) -> None:
    if not job_id:
        return
    try:
        from datetime import datetime, timezone

        get_admin().table("jobs").update(
            {
                "status": "failed",
                "stage": "failed",
                "error": message[:220],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", job_id).execute()
    except Exception:
        pass
