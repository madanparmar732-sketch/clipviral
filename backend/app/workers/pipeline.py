"""The pipeline worker: turns one long video into viral short clips.

Order of magic tricks:
1. Read the video's length.
2. Whisper writes down everything said in the video (with timestamps).
3. GPT-4o reads that and picks the 3 most viral moments.
4. FFmpeg cuts each moment into a 9:16 clip with animated captions.
5. Clips + thumbnails are uploaded to Supabase Storage; links saved to the database.
"""

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

# The free machine is tiny (half a CPU!). Jobs run ONE AT A TIME so two
# renders never fight each other into slow-motion.
_PIPELINE_LOCK = threading.Lock()


def update_job(job_id: str, **fields) -> None:
    fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    try:
        get_admin().table("jobs").update(fields).eq("id", job_id).execute()
    except Exception:
        logger.exception("Could not update job %s", job_id)


def run_pipeline(job_id: str, source_path: str) -> None:
    """Entry point used by the upload route. One job at a time (tiny machine!)."""
    with _PIPELINE_LOCK:
        _run_pipeline_unserialized(job_id, source_path)


def _run_pipeline_unserialized(job_id: str, source_path: str) -> None:
    """Runs in a background thread after the upload response is sent."""
    workdir = os.path.dirname(source_path)
    admin = get_admin()

    try:
        job_res = admin.table("jobs").select("*").eq("id", job_id).limit(1).execute()
        job_rows = job_res.data or []
        user_id = job_rows[0].get("user_id") if job_rows else None

        # ---------- Step 1: measure the video ----------
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

            captions.build_ass_captions(
                transcript["words"], clip["start"], clip["end"], ass_path
            )
            video_processor.render_clip(
                source_path, clip["start"], clip["end"], ass_path, clip_path,
                on_progress=_clip_progress,
            )
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

    workdir = os.path.join(settings.media_dir, job_id)
    os.makedirs(workdir, exist_ok=True)

    def on_progress(percent: int) -> None:
        update_job(job_id, stage="fetching_link", progress=max(2, min(20, 2 + percent // 6)))

    try:
        update_job(job_id, status="processing", stage="fetching_link", progress=2)
        result = link_fetcher.fetch_video(url, workdir, on_progress=on_progress)
        fields = {
            "stage": "link_fetched",
            "progress": 22,
            "source_filename": result["title"],
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
        return

    try:
        run_pipeline(job_id, result["path"])
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
