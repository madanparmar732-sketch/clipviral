"""Data shapes the API returns (documentation + validation)."""

from typing import Optional

from pydantic import BaseModel


class ClipOut(BaseModel):
    id: str
    job_id: str
    title: Optional[str] = None
    hook: Optional[str] = None
    score: int = 0
    start_seconds: float = 0
    end_seconds: float = 0
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    hashtags: list[str] = []


class JobOut(BaseModel):
    id: str
    status: str
    stage: Optional[str] = None
    progress: int = 0
    source_filename: Optional[str] = None
    duration_seconds: float = 0
    error: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    clips: list[ClipOut] = []
