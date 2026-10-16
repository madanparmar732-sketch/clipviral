"""Lets the dashboard ask: "how is my video doing? Give me my clips." """

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.supabase_client import get_admin

router = APIRouter()


@router.get("/api/jobs")
def list_jobs(user=Depends(get_current_user)):
    """All of this user's jobs, newest first, with their clips."""
    response = (
        get_admin()
        .table("jobs")
        .select("*, clips(*)")
        .eq("user_id", user.id)
        .order("created_at", desc=True)
        .execute()
    )
    jobs = response.data or []
    for job in jobs:
        job.setdefault("clips", [])
        job["clips"].sort(key=lambda c: c.get("score", 0), reverse=True)
    return {"jobs": jobs}


@router.get("/api/jobs/{job_id}")
def get_job(job_id: str, user=Depends(get_current_user)):
    """One specific job with its clips (used for live status updates)."""
    response = (
        get_admin()
        .table("jobs")
        .select("*, clips(*)")
        .eq("id", job_id)
        .eq("user_id", user.id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Job not found.")
    job = rows[0]
    job.setdefault("clips", [])
    job["clips"].sort(key=lambda c: c.get("score", 0), reverse=True)
    return {"job": job}
