"""FastAPI application entry point. This file is what Render runs."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import account as account_router
from app.routers import clips, jobs, uploads

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("opusclip")


@asynccontextmanager
async def lifespan(_: FastAPI):
    os.makedirs(settings.media_dir, exist_ok=True)
    logger.info("API started. Media folder: %s", os.path.abspath(settings.media_dir))
    yield
    logger.info("API shutting down.")


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)


@app.on_event("startup")
def _boot_worker() -> None:
    """Start the job worker + recover anything a restart left queued."""
    try:
        from app.workers.pipeline import ensure_worker_started

        ensure_worker_started()
    except Exception:
        pass

# CORS = the "guest list" that says which websites may call this API.
# Without this the browser blocks requests and you get CORS errors (see TROUBLESHOOTING.md).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    # Smart rule: any *.vercel.app website is welcome (covers all Vercel addresses).
    allow_origin_regex=r"https://.*[.]vercel[.]app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(account_router.router, tags=["account"])
app.include_router(uploads.router, tags=["uploads"])
app.include_router(jobs.router, tags=["jobs"])
app.include_router(clips.router, tags=["clips"])


@app.get("/")
def root():
    return {"status": "ok", "service": settings.app_name, "docs": "/docs"}


@app.get("/api/health")
def health():
    return {"status": "ok", "service": settings.app_name}
