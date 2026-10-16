"""Script-to-Video job runner."""

import logging
import os
import shutil
import uuid

from app.config import settings
from app.services import storage, video_processor
from app.services.script2video import script_to_video
from app.workers.pipeline import update_job

logger = logging.getLogger(__name__)


def run_script_job(job_id: str, user_id: str, script: str, style: str) -> None:
    workdir = os.path.join(settings.media_dir, job_id)
    os.makedirs(workdir, exist_ok=True)
    try:
        update_job(job_id, status="processing", stage="writing_script", progress=8)
        result = script_to_video(script, workdir, style)
        update_job(job_id, stage="rendering_clip_1_of_1", progress=55,
                   duration_seconds=result["duration"])

        clip_path = result["path"]
        thumb_path = os.path.join(workdir, "thumb.jpg")
        try:
            video_processor.make_thumbnail(clip_path, thumb_path, at_seconds=1.0)
        except Exception:
            thumb_path = ""

        clip_id = str(uuid.uuid4())
        video_url = storage.upload_file_to_storage(clip_path, f"{job_id}/clip_1.mp4")
        thumb_url = ""
        if thumb_path and os.path.exists(thumb_path):
            thumb_url = storage.upload_file_to_storage(thumb_path, f"{job_id}/clip_1.jpg")

        admin_row = {
            "id": clip_id,
            "job_id": job_id,
            "user_id": user_id,
            "title": result["title"],
            "hook": " ".join(result["lines"][:1]),
            "score": 75,
            "start_seconds": 0,
            "end_seconds": round(result["duration"], 2),
            "video_url": video_url,
            "thumbnail_url": thumb_url,
            "storage_path": f"{job_id}/clip_1.mp4",
            "hashtags": ["#aitools", "#shorts"],
        }
        from app.supabase_client import get_admin
        get_admin().table("clips").insert(admin_row).execute()
        update_job(job_id, status="completed", stage="done", progress=100, error=None)
    except Exception as exc:
        logger.exception("Script job %s failed", job_id)
        update_job(job_id, status="failed", stage="failed", error=f"Script-to-video failed: {str(exc)[:200]}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
