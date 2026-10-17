"""Handles video uploads: saves the file, creates a job, starts the AI pipeline."""

import json
import logging
import os
import shutil
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.auth import get_current_user
from app.config import settings
from app.supabase_client import get_admin
from app.workers.pipeline import run_pipeline

router = APIRouter()
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}


@router.post("/api/videos/upload")
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    options: str = Form(""),
    user=Depends(get_current_user),
):
    """
    Step 1 of the magic trick:
    1. Save the uploaded video to a folder.
    2. Write a "job ticket" in the database (status: queued).
    3. Tell the background worker to start cutting the video.
    """
    original_name = file.filename or "video.mp4"
    extension = os.path.splitext(original_name)[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{extension}'. Please upload: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    job_id = str(uuid.uuid4())
    job_dir = os.path.join(settings.media_dir, job_id)
    os.makedirs(job_dir, exist_ok=True)
    destination = os.path.join(job_dir, f"source{extension}")

    size = 0
    try:
        with open(destination, "wb") as out_file:
            while True:
                chunk = await file.read(1024 * 1024)  # read 1 MB at a time
                if not chunk:
                    break
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File is bigger than the {settings.max_upload_mb} MB limit.",
                    )
                out_file.write(chunk)
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(job_dir, ignore_errors=True)
        logger.exception("Failed to save upload")
        raise HTTPException(status_code=500, detail=f"Could not save the upload: {exc}")

    if size == 0:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    job_row = {
        "id": job_id,
        "user_id": user.id,
        "status": "queued",
        "stage": "queued",
        "progress": 0,
        "source_filename": original_name,
        "source_size_bytes": size,
    }
    get_admin().table("jobs").insert(job_row).execute()

    # Job options (genre / keywords / prompt / aspect / fillers / ...) — parity pack
    try:
        from app.services import parity as _parity

        _parity.save_job_prefs(job_id, json.loads(options) if options.strip() else {})
    except Exception:
        logger.exception("could not save create options (non-fatal)")

    # Keep a storage copy RIGHT AWAY so a server restart can never lose this job.
    try:
        from app.services import storage as _storage

        _storage.upload_file_to_storage(destination, f"{job_id}/source.mp4")
    except Exception:
        logger.exception("source pre-upload failed (not fatal)")

    # This runs AFTER the response is sent, in the background.
    background_tasks.add_task(run_pipeline, job_id, destination)

    logger.info("Job %s created for %s (%.1f MB)", job_id, original_name, size / 1024 / 1024)
    return {"job": {**job_row, "clips": []}}


class LinkRequest(BaseModel):
    url: str
    options: dict = {}


@router.post("/api/videos/from-link")
async def upload_from_link(
    background_tasks: BackgroundTasks,
    payload: LinkRequest,
    user=Depends(get_current_user),
):
    """Paste a YouTube / Facebook / X / Instagram link: we fetch the video and clip it."""
    from app.services.link_fetcher import validate_url
    from app.workers.pipeline import fetch_and_run

    try:
        url = validate_url(payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    from urllib.parse import urlparse as _urlparse

    job_id = str(uuid.uuid4())
    job_row = {
        "id": job_id,
        "user_id": user.id,
        "status": "queued",
        "stage": "fetching_link",
        "progress": 2,
        "source_filename": f"Link: {_urlparse(url).netloc}|||{url}",
        "source_size_bytes": 0,
    }
    get_admin().table("jobs").insert(job_row).execute()

    # Job options (genre / keywords / prompt / aspect / fillers / ...) — parity pack
    try:
        from app.services import parity as _parity

        _parity.save_job_prefs(job_id, dict(payload.options or {}))
    except Exception:
        logger.exception("could not save create options (non-fatal)")

    # Fetch the video + run the pipeline, both in the background.
    background_tasks.add_task(fetch_and_run, job_id, url)

    logger.info("Job %s created from link %s", job_id, url[:120])
    return {"job": {**job_row, "clips": []}}


class ScriptRequest(BaseModel):
    script: str
    style: str = "beast"


@router.post("/api/videos/from-script")
async def upload_from_script(
    background_tasks: BackgroundTasks,
    payload: ScriptRequest,
    user=Depends(get_current_user),
):
    """Script-to-Video (Beta): type a topic or script, get a narrated vertical video."""
    from app.workers.script_job import run_script_job

    text = (payload.script or "").strip()
    if len(text) < 3:
        raise HTTPException(status_code=400, detail="Please type a topic or a script first.")
    if len(text) > 3000:
        raise HTTPException(status_code=400, detail="That's a lot! Keep the script under 3000 characters.")

    job_id = str(uuid.uuid4())
    job_row = {
        "id": job_id,
        "user_id": user.id,
        "status": "queued",
        "stage": "writing_script",
        "progress": 3,
        "source_filename": f"Script: {text[:48]}",
        "source_size_bytes": 0,
    }
    get_admin().table("jobs").insert(job_row).execute()
    background_tasks.add_task(run_script_job, job_id, user.id, text, payload.style)
    return {"job": {**job_row, "clips": []}}
