"""Janitor: keeps only the newest N videos per account, deletes the rest.

Deletes: storage files (clips + thumbs + words) -> clips rows -> job row.
Runs automatically after every finished job and when a new job is created.
"""

import logging

from app.config import settings
from app.supabase_client import get_admin

logger = logging.getLogger(__name__)


def cleanup_old_jobs(user_id: str, keep: int | None = None) -> int:
    """Delete everything older than the newest `keep` jobs. Returns how many were removed."""
    keep = keep if keep is not None else settings.max_videos_per_account
    admin = get_admin()

    response = (
        admin.table("jobs")
        .select("id,created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    jobs = response.data or []
    old_jobs = jobs[keep:]
    removed = 0

    for job in old_jobs:
        job_id = job["id"]
        try:
            # 1) storage files inside the job folder
            listing = admin.storage.from_(settings.clips_bucket).list(job_id)
            paths = [f"{job_id}/{item['name']}" for item in (listing or []) if item.get("name")]
            if paths:
                admin.storage.from_(settings.clips_bucket).remove(paths)
        except Exception:
            logger.exception("Could not delete storage for job %s", job_id)

        try:
            admin.table("clips").delete().eq("job_id", job_id).execute()
            admin.table("jobs").delete().eq("id", job_id).execute()
            removed += 1
        except Exception:
            logger.exception("Could not delete job %s", job_id)

    if removed:
        logger.info("Janitor removed %d old job(s) for user %s", removed, user_id)
    return removed
