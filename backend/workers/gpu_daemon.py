"""ClipViral GPU RENDER FARM worker — run inside a Google Colab (or Kaggle)
notebook with a free T4/P100 GPU.

Same lease protocol as the phone worker (app/services/lease.py), so Render and
the phone NEVER double-run a job this box owns. Differences:

  * probes NVIDIA NVENC once at startup; when it works, sets CLIPVIRAL_GPU=1
    which flips video_processor to hardware H.264 encoding (5-10x faster)
  * runs up to GPU_WORKERS (default 2) clips in parallel — a T4 has plenty
    of encoder sessions for that
  * reads credentials from Colab "Secrets" first (SUPABASE_URL,
    SUPABASE_SERVICE_ROLE, GROQ_API_KEY), falling back to the environment

Run:  python -m workers.gpu_daemon      (from the extracted backend folder)
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.getcwd())
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("gpu-daemon")

HEARTBEAT_SECONDS = 45
MAX_HOURS = float(os.environ.get("GPU_MAX_HOURS", "0"))  # 0 = run forever


# ------------------------------------------------------------------ secrets
def _secret(name: str) -> str:
    val = os.environ.get(name, "")
    if val:
        return val
    try:
        from google.colab import userdata  # type: ignore

        return userdata.get(name) or ""
    except Exception:
        return ""


def _load_secrets() -> bool:
    os.environ.setdefault("SUPABASE_URL", _secret("SUPABASE_URL"))
    os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY",
                          _secret("SUPABASE_SERVICE_ROLE_KEY") or _secret("SUPABASE_SERVICE_ROLE"))
    os.environ.setdefault("GROQ_API_KEY", _secret("GROQ_API_KEY"))
    need = ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "GROQ_API_KEY")
    missing = [k for k in need if not os.environ.get(k)]
    for k in missing:
        log.error("missing secret: %s (add it in Colab's Secrets panel)", k)
    if not missing:
        os.makedirs(os.environ.get("MEDIA_DIR", "./media"), exist_ok=True)
        os.environ.setdefault("MEDIA_DIR", "./media")
    return not missing


# ------------------------------------------------------------------- NVENC
def nvenc_probe() -> bool:
    """True if this box can actually encode h264_nvenc right now."""
    try:
        if os.system("nvidia-smi -L >/dev/null 2>&1") != 0:
            log.warning("no NVIDIA GPU visible — falling back to CPU encode")
            return False
        enc = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"],
                             capture_output=True, text=True, timeout=30)
        if "h264_nvenc" not in (enc.stdout or ""):
            log.warning("ffmpeg lacks h264_nvenc — CPU encode (apt ffmpeg fix "
                        "in the bootstrap should have prevented this)")
            return False
        test = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
             "-f", "lavfi", "-i", "color=black:s=256x256:d=0.2",
             "-c:v", "h264_nvenc", "-f", "null", "-"],
            capture_output=True, text=True, timeout=60)
        return test.returncode == 0
    except Exception:
        return False


# ------------------------------------------------------------------ workers
def _worker_loop(stop: threading.Event, active: set, lock: threading.Lock) -> None:
    from app.services import lease
    from workers import phone_daemon

    while not stop.is_set():
        job_id = None
        try:
            job_id = lease.claim_any() or lease.claim_orphan_processing()
        except Exception:
            log.exception("claim failed")
        if not job_id:
            stop.wait(5)
            continue
        with lock:
            active.add(job_id)
        log.info("CLAIMED job %s", job_id[:8])
        try:
            phone_daemon._process(job_id)
            log.info("job %s DONE", job_id[:8])
        except Exception:
            log.exception("job %s crashed on GPU box", job_id[:8])
            try:
                from app.workers import pipeline

                pipeline.update_job(job_id, status="failed", stage="failed",
                                    error="GPU worker crashed — see notebook log.")
            except Exception:
                pass
        finally:
            try:
                lease.release(job_id)
            except Exception:
                pass
            with lock:
                active.discard(job_id)


def main() -> None:
    if not _load_secrets():
        sys.exit(2)

    if nvenc_probe():
        os.environ["CLIPVIRAL_GPU"] = "1"
        log.info("NVENC hardware encoder READY — clips will render on the GPU")
    else:
        os.environ.pop("CLIPVIRAL_GPU", None)
        log.info("using CPU encode (still faster than Render's 0.1 vCPU)")

    workers_n = 2 if os.environ.get("CLIPVIRAL_GPU") == "1" else 1
    workers_n = int(os.environ.get("GPU_WORKERS", workers_n))
    log.info("ClipViral GPU render farm starting — %d parallel worker(s)", workers_n)

    active: set = set()
    lock = threading.Lock()
    stop = threading.Event()

    def beat() -> None:
        from app.services import lease

        while not stop.wait(HEARTBEAT_SECONDS):
            for jid in list(active):
                lease.heartbeat(jid)

    threads = [threading.Thread(target=_worker_loop, args=(stop, active, lock), daemon=True)
               for _ in range(workers_n)]
    threading.Thread(target=beat, daemon=True).start()
    for t in threads:
        t.start()

    started = time.time()
    try:
        while any(t.is_alive() for t in threads):
            if MAX_HOURS and time.time() - started > MAX_HOURS * 3600:
                log.info("GPU_MAX_HOURS reached — exiting so the next session starts fresh")
                break
            time.sleep(5)
    except KeyboardInterrupt:
        pass
    stop.set()
    log.info("gpu daemon stopped")


if __name__ == "__main__":
    main()
