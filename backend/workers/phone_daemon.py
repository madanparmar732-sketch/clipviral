"""ClipViral PHONE WORKER — run this inside Termux on the phone.

A full pipeline worker (fetch → transcribe → find → render → upload) that
borrows the phone's CPU instead of Render's crippled one. Claims jobs via a
lease (app/services/lease.py) so Render NEVER double-runs the same video, and
heartbeats every 60s so a dead phone's job returns to the queue automatically.

Run:  python -m workers.phone_daemon      (from the backend folder)
"""
from __future__ import annotations

import logging
import os
import sys
import threading
import time

sys.path.insert(0, os.getcwd())
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("phone-daemon")

HEARTBEAT_SECONDS = 60


def _job_row(job_id: str) -> dict:
    from app.supabase_client import get_admin

    res = get_admin().table("jobs").select("*").eq("id", job_id).limit(1).execute()
    return (res.data or [{}])[0]


def _process(job_id: str) -> None:
    from app.config import settings
    from app.services import storage
    from app.workers import pipeline

    row = _job_row(job_id)
    fn = row.get("source_filename") or ""
    url = fn.split("|||", 1)[1].strip() if "|||" in fn else ""
    workdir = os.path.join(settings.media_dir, job_id)
    os.makedirs(workdir, exist_ok=True)
    local = os.path.join(workdir, "source.mp4")

    if url.startswith("http"):
        log.info("job %s: fetching link %s", job_id[:8], url[:80])
        pipeline.fetch_and_run(job_id, url)
        return

    if not os.path.exists(local):
        log.info("job %s: downloading source from storage", job_id[:8])
        if not storage.download_file_from_storage(f"{job_id}/source.mp4", local):
            pipeline.update_job(
                job_id, status="failed", stage="failed",
                error="Phone worker could not download the source file from storage.",
            )
            return
    log.info("job %s: running pipeline on phone CPU", job_id[:8])
    pipeline.run_pipeline(job_id, local)


def main() -> None:
    from app.services import lease

    log.info("ClipViral phone worker starting (heartbeats every %ss)", HEARTBEAT_SECONDS)
    current_ref: list[str | None] = [None]

    def beat() -> None:
        while True:
            time.sleep(HEARTBEAT_SECONDS)
            if current_ref[0]:
                lease.heartbeat(current_ref[0])

    threading.Thread(target=beat, daemon=True).start()

    while True:
        try:
            job_id = lease.claim_any() or lease.claim_orphan_processing()
            if not job_id:
                time.sleep(5)
                continue
            current_ref[0] = job_id
            log.info("CLAIMED job %s", job_id[:8])
            try:
                _process(job_id)
            except Exception:  # noqa: BLE001
                log.exception("job %s crashed on phone", job_id[:8])
                try:
                    from app.workers import pipeline

                    pipeline.update_job(job_id, status="failed", stage="failed",
                                        error="Phone worker crashed — see Termux log.")
                except Exception:
                    pass
            finally:
                lease.release(job_id)
                current_ref[0] = None
        except KeyboardInterrupt:
            log.info("stopped by user")
            return
        except Exception:  # noqa: BLE001
            log.exception("daemon loop error - retrying in 10s")
            time.sleep(10)


if __name__ == "__main__":
    main()
