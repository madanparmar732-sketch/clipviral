"""The pipeline worker: turns one long video into viral short clips.

Order of magic tricks:
1. Read the video's length.
2. Whisper writes down everything said in the video (with timestamps).
3. GPT-4o reads that and picks the 3 most viral moments.
4. FFmpeg cuts each moment into a 9:16 clip with animated captions.
5. Clips + thumbnails are uploaded to Supabase Storage; links saved to the database.
"""

import json
import logging
import os
import shutil
import threading
import time
import uuid
from datetime import datetime, timezone

from app.config import settings
from app.services import captions, highlights, storage, transcription, video_processor
from app.supabase_client import get_admin

logger = logging.getLogger(__name__)

# The free machine is tiny (half a CPU!). Jobs run ONE AT A TIME through a
# priority queue — Pro jobs (priority 1) jump ahead of free jobs (priority 5).
import queue as _queue

_TASKS: "_queue.PriorityQueue" = _queue.PriorityQueue()
_WORKER_STARTED = threading.Event()
_WORKER_GUARD = threading.Lock()
_INFLIGHT: set[str] = set()
_INFLIGHT_LOCK = threading.Lock()


def _mark_inflight(job_id: str) -> None:
    with _INFLIGHT_LOCK:
        _INFLIGHT.add(job_id)


def _unmark_inflight(job_id: str) -> None:
    with _INFLIGHT_LOCK:
        _INFLIGHT.discard(job_id)


def _queue_worker() -> None:
    _recover_stuck()  # pick up anything a restart left behind
    while True:
        try:
            _prio, _seq, job_id, source_path = _TASKS.get(timeout=30)
        except _queue.Empty:
            _recover_stuck()  # periodic sweep — nothing is ever stuck forever
            continue
        try:
            _run_pipeline_unserialized(job_id, source_path)
        except Exception:
            logger.exception("Pipeline crashed for job %s", job_id)
        finally:
            _TASKS.task_done()
            _unmark_inflight(job_id)
            shutil.rmtree(os.path.dirname(source_path), ignore_errors=True)


def ensure_worker_started() -> None:
    with _WORKER_GUARD:
        if not _WORKER_STARTED.is_set():
            threading.Thread(target=_queue_worker, daemon=True).start()
            _WORKER_STARTED.set()


def _recover_stuck() -> None:
    """Re-queue jobs lost to a deploy/restart. Nothing stays queued forever."""
    try:
        res = (
            get_admin()
            .table("jobs")
            .select("*")
            .in_("status", ["queued", "processing"])
            .order("created_at")
            .limit(10)
            .execute()
        )
        rows = res.data or []
    except Exception:
        logger.exception("recover: could not list jobs")
        return

    for row in rows:
        job_id = row.get("id")
        if not job_id:
            continue
        with _INFLIGHT_LOCK:
            if job_id in _INFLIGHT:
                continue
            _INFLIGHT.add(job_id)  # reserve before enqueue
        fn = row.get("source_filename") or ""
        url = fn.split("|||", 1)[1].strip() if "|||" in fn else ""
        if url.startswith("http"):
            logger.info("recover: re-queuing link job %s", job_id)
            threading.Thread(target=fetch_and_run, args=(job_id, url), daemon=True).start()
            continue
        local = os.path.join(settings.media_dir, job_id, "source.mp4")
        if os.path.exists(local) or storage.download_file_from_storage(f"{job_id}/source.mp4", local):
            logger.info("recover: re-queuing stored-source job %s", job_id)
            run_pipeline(job_id, local)
            continue
        logger.warning("recover: job %s has no recoverable source - failing it", job_id)
        update_job(
            job_id,
            status="failed",
            stage="failed",
            error="The server restarted before this job started and the video was not stored yet. Please add the video again.",
        )
        _unmark_inflight(job_id)


def _user_prefs(user_id: str) -> dict:
    from app.services.captions import FREE_STYLES

    prefs = {"is_pro": False, "caption_style": "beast", "sfx": False, "enhance": False, "reframe": "face"}
    try:
        _auth = get_admin().auth
        res = getattr(_auth, "admin", _auth).get_user_by_id(user_id)
        user = getattr(res, "user", res)
        meta = (getattr(user, "user_metadata", None) or {}) if user else {}
        for key in prefs:
            if key in meta:
                prefs[key] = meta[key]
        if prefs["caption_style"] not in FREE_STYLES:
            prefs["caption_style"] = "beast"  # unknown style -> safe default (all styles are free)
    except Exception:
        logger.exception("Could not read user prefs (using free defaults)")
    return prefs


def run_pipeline(job_id: str, source_path: str) -> None:
    """Entry point used by the upload route. Pro jobs get priority."""
    ensure_worker_started()
    _mark_inflight(job_id)

    priority = 5
    try:
        job_res = get_admin().table("jobs").select("user_id").eq("id", job_id).limit(1).execute()
        rows = job_res.data or []
        if rows and _user_prefs(rows[0].get("user_id")).get("is_pro"):
            priority = 1
    except Exception:
        pass
    _TASKS.put((priority, time.monotonic(), job_id, source_path))


def _run_pipeline_unserialized(job_id: str, source_path: str) -> None:
    """Runs in a background thread after the upload response is sent."""
    workdir = os.path.dirname(source_path)
    admin = get_admin()

    try:
        job_res = admin.table("jobs").select("*").eq("id", job_id).limit(1).execute()
        job_rows = job_res.data or []
        user_id = job_rows[0].get("user_id") if job_rows else None
        prefs = _user_prefs(user_id) if user_id else {"is_pro": False, "caption_style": "beast", "sfx": False, "enhance": False, "reframe": "face"}
        is_pro = bool(prefs.get("is_pro"))

        # Keep a copy of the SOURCE so the Pro editor can re-render in full quality
        try:
            if os.path.getsize(source_path) <= 250 * 1024 * 1024:
                storage.upload_file_to_storage(source_path, f"{job_id}/source.mp4")
        except Exception:
            logger.exception("source upload failed (not fatal)")

        # ---------- Step 1: measure the video ----------
        if _is_cancelled(job_id):
            logger.info("Job %s was cancelled - stopping.", job_id)
            return
        update_job(job_id, status="processing", stage="measuring_video", progress=5)
        info = video_processor.probe_video(source_path)
        duration = info["duration"]
        update_job(job_id, duration_seconds=duration)
        logger.info("Job %s: video is %.1f seconds long", job_id, duration)

        # ---------- Step 2: Whisper transcription ----------
        update_job(job_id, stage="transcribing_audio", progress=15)
        transcript = transcription.transcribe_video(source_path, workdir)
        if not transcript["segments"]:
            raise RuntimeError("No speech found in the video, so there is nothing to clip.")
        logger.info("Job %s: transcript has %d segments", job_id, len(transcript["segments"]))

        # ---------- Step 3: GPT-4o highlight detection ----------
        update_job(job_id, stage="finding_viral_moments", progress=40)
        clips = highlights.detect_highlights(transcript, duration)
        if not clips:
            raise RuntimeError("The AI could not find any good moments to clip.")
        logger.info("Job %s: AI picked %d moments", job_id, len(clips))

        # ---------- Step 4 & 5: cut, caption, upload ----------
        saved_clips = []
        for index, clip in enumerate(clips):
            if _is_cancelled(job_id):
                logger.info("Job %s was cancelled mid-render - stopping.", job_id)
                return
            update_job(
                job_id,
                stage=f"rendering_clip_{index + 1}_of_{len(clips)}",
                progress=42 + 16 * index,
            )

            # Live progress WHILE ffmpeg renders (the bar keeps moving!)
            base_progress = 42 + 16 * index
            last_touch = [0.0]

            def _clip_progress(frac: float, _base=base_progress, _last=last_touch) -> None:
                now = time.time()
                if now - _last[0] < 2.0 and frac < 0.99:
                    return  # don't hammer the database
                _last[0] = now
                update_job(job_id, progress=_base + int(14 * max(0.0, min(1.0, frac))))

            clip_id = str(uuid.uuid4())
            ass_path = os.path.join(workdir, f"clip_{index + 1}.ass")
            clip_path = os.path.join(workdir, f"clip_{index + 1}.mp4")
            thumb_path = os.path.join(workdir, f"clip_{index + 1}.jpg")
            words_path = os.path.join(workdir, f"clip_{index + 1}.words.json")

            # ---- AUTOMATIC PAUSE-REMOVAL: dead air gets cut out ----
            try:
                silences = video_processor.detect_silences(source_path, clip["start"], clip["end"])
            except Exception:
                silences = []
            kept_segments = video_processor.build_kept_segments(clip["start"], clip["end"], silences)

            # Captions follow the NEW pause-free timeline
            remapped = captions.remap_words(transcript["words"], kept_segments)
            kept_len = sum(b - a for a, b in kept_segments)
            captions.build_ass_captions(remapped, 0.0, max(1.0, kept_len), ass_path,
                                        style=str(prefs.get("caption_style") or "beast"),
                                        watermark=not is_pro)

            chain = video_processor.clip_video_chain(
                source_path, clip["start"], clip["end"],
                reframe=str(prefs.get("reframe") or "face"),
                enhance=bool(prefs.get("enhance")) and is_pro,
                watermark=not is_pro,
            )
            video_processor.cut_and_concat(
                source_path, kept_segments, clip_path,
                video_chain=chain, ass_path=ass_path,
                total_seconds=kept_len, on_progress=_clip_progress,
            )

            if is_pro and prefs.get("sfx"):
                try:
                    sfx = video_processor.make_sfx(workdir)
                    starts = captions.line_start_times(remapped)[:12]
                    if starts:
                        paths, times = [], []
                        for i, t in enumerate(starts):
                            paths.append(sfx["whoosh"] if i == 0 else sfx["pop"])
                            times.append(t)
                        video_processor.mix_sfx(clip_path, clip_path + ".sfx.mp4", paths, times)
                        os.replace(clip_path + ".sfx.mp4", clip_path)
                except Exception:
                    logger.exception("Auto SFX failed (not fatal)")

            # Words JSON for the transcript-based editor
            try:
                with open(words_path, "w", encoding="utf-8") as wf:
                    json.dump(
                        {
                            "clip_duration": round(kept_len, 3),
                            "source_start": clip["start"],
                            "source_end": clip["end"],
                            "kept_segments": [[round(a, 3), round(b, 3)] for a, b in kept_segments],
                            "style": str(prefs.get("caption_style") or "beast"),
                            "words": [
                                {"start": round(w["start"], 3), "end": round(w["end"], 3), "word": w.get("word", "")}
                                for w in remapped
                            ],
                        },
                        wf,
                    )
            except Exception:
                logger.exception("words json write failed (not fatal)")
            try:
                video_processor.make_thumbnail(clip_path, thumb_path)
            except Exception:
                logger.exception("Thumbnail failed (not fatal)")
                thumb_path = ""

            clip_storage_path = f"{job_id}/clip_{index + 1}.mp4"
            video_url = storage.upload_file_to_storage(clip_path, clip_storage_path)
            thumb_url = ""
            if thumb_path and os.path.exists(thumb_path):
                thumb_url = storage.upload_file_to_storage(
                    thumb_path, f"{job_id}/clip_{index + 1}.jpg"
                )
            if os.path.exists(words_path):
                try:
                    storage.upload_file_to_storage(words_path, f"{job_id}/clip_{index + 1}.words.json")
                except Exception:
                    logger.exception("words json upload failed (not fatal)")

            clip_row = {
                "id": clip_id,
                "job_id": job_id,
                "user_id": user_id,
                "title": clip["title"],
                "hook": clip["hook"],
                "score": clip["score"],
                "start_seconds": clip["start"],
                "end_seconds": clip["end"],
                "video_url": video_url,
                "thumbnail_url": thumb_url,
                "storage_path": clip_storage_path,
                "hashtags": clip["hashtags"],
            }
            admin.table("clips").insert(clip_row).execute()
            saved_clips.append(clip_path)

        # ---------- Optional: MoviePy recap reel ----------
        if settings.recap_enabled and len(saved_clips) > 1:
            update_job(job_id, stage="making_recap", progress=92)
            try:
                recap_path = os.path.join(workdir, "recap.mp4")
                video_processor.make_recap_moviepy(saved_clips, recap_path)
                recap_url = storage.upload_file_to_storage(recap_path, f"{job_id}/recap.mp4")
                admin.table("clips").insert(
                    {
                        "id": str(uuid.uuid4()),
                        "job_id": job_id,
                        "user_id": user_id,
                        "title": "All highlights recap",
                        "hook": "Every best moment in one reel",
                        "score": 0,
                        "start_seconds": 0,
                        "end_seconds": 0,
                        "video_url": recap_url,
                        "thumbnail_url": "",
                        "storage_path": f"{job_id}/recap.mp4",
                        "hashtags": ["#recap"],
                    }
                ).execute()
            except Exception:
                logger.exception("Recap render failed (not fatal)")

        update_job(job_id, status="completed", stage="done", progress=100, error=None)

        # Janitor: keep only the newest 4 videos per account, auto-delete older ones
        try:
            from app.services.janitor import cleanup_old_jobs
            if user_id:
                cleanup_old_jobs(user_id)
        except Exception:
            logger.exception("Janitor failed (not fatal)")
        logger.info("Job %s completed with %d clips", job_id, len(saved_clips))

    except Exception as exc:
        logger.exception("Job %s failed", job_id)
        update_job(job_id, status="failed", stage="failed", error=str(exc)[:1000])

    finally:
        # Free disk space: delete the working folder (clips are already in Supabase).
        shutil.rmtree(workdir, ignore_errors=True)


def fetch_and_run(job_id: str, url: str) -> None:
    """Background task: fetch the video from the link, then run the normal pipeline."""
    from app.services import link_fetcher

    _mark_inflight(job_id)

    workdir = os.path.join(settings.media_dir, job_id)
    os.makedirs(workdir, exist_ok=True)

    def on_progress(percent: int) -> None:
        update_job(job_id, stage="fetching_link", progress=max(2, min(20, 2 + percent // 6)))

    try:
        if _is_cancelled(job_id):
            logger.info("Job %s was cancelled - stopping.", job_id)
            _unmark_inflight(job_id)
            return
        update_job(job_id, status="processing", stage="fetching_link", progress=2)
        result = link_fetcher.fetch_video(url, workdir, on_progress=on_progress)
        fields = {
            "stage": "link_fetched",
            "progress": 22,
            "source_filename": f"{result['title']}|||{url}",
            "source_size_bytes": result["size"],
        }
        if result.get("duration"):
            fields["duration_seconds"] = result["duration"]
        update_job(job_id, **fields)
        logger.info("Job %s: fetched link video %r (%.1f MB)", job_id, result["title"], result["size"] / 1024 / 1024)
    except Exception as exc:
        logger.exception("Link fetch failed for job %s", job_id)
        update_job(
            job_id,
            status="failed",
            stage="failed",
            error=f"Could not fetch that video link: {str(exc)[:220]}",
        )
        shutil.rmtree(workdir, ignore_errors=True)
        _unmark_inflight(job_id)
        return

    try:
        run_pipeline(job_id, result["path"])
    except Exception:
        shutil.rmtree(workdir, ignore_errors=True)
        raise


def _is_cancelled(job_id: str) -> bool:
    """True if the user cancelled this job."""
    try:
        row = get_admin().table("jobs").select("status").eq("id", job_id).limit(1).execute().data
        return bool(row and row[0].get("status") == "cancelled")
    except Exception:
        return False
