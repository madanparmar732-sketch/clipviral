# ============================================================================
#  ClipViral GPU RENDER FARM — paste this ENTIRE file into ONE Google Colab
#  cell and run it. That's it. (Kaggle: see GPU_NOTEBOOK.txt at the bottom.)
#
#  One-time prep in Colab (30 seconds):
#    1. Open https://colab.research.google.com  -> New Notebook
#    2. Menu Runtime -> Change runtime type -> TPU/GPU: "T4 GPU"
#    3. Left sidebar -> the key icon "Secrets": add
#         SUPABASE_URL            = <url from the setup doc>
#         SUPABASE_SERVICE_ROLE_KEY = <service key from the setup doc>
#         GROQ_API_KEY            = <your groq key>
#    4. Paste everything below into the first code cell, press Shift+Enter.
#
#  Keep the tab open. Each 12h session ends automatically; just re-run the
#  cell afterwards — unfinished jobs come back to the queue by themselves.
# ============================================================================
import os, sys, subprocess, tarfile, urllib.request

TARBALL_URL = "https://dkavqwoolwomouajmcsy.supabase.co/storage/v1/object/sign/clips/worker/clipviral-phone.tar.gz?token=eyJraWQiOiJjOGIyYzk4ZC1iZjg1LTQzYTItYTUxOS1hOGMwMjFmMDhmOWEiLCJhbGciOiJIUzUxMiJ9.eyJ1cmwiOiJjbGlwcy93b3JrZXIvY2xpcHZpcmFsLXBob25lLnRhci5neiIsInNjb3BlIjoiZG93bmxvYWQiLCJpYXQiOjE3OTIyNzgyMzMsImV4cCI6MTgwNzgzMDIzM30.gaVj_zc1GDd5CWqKHfy-LoQjhmkOSNl600nzNyOAYVs19ROxqDjshaQdfHvNVAR5fK1HAaMKUOaHS-Z3eVWTWQ"

ROOT = "/content/clipviral"
BACKEND = f"{ROOT}/backend"

def sh(cmd):
    print("+", cmd, flush=True)
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if r.returncode != 0:
        print((r.stdout or "")[-800:] + (r.stderr or "")[-1500:])
        raise SystemExit(f"step failed: {cmd}")

# ---- 1) system deps: full ffmpeg (libass for captions + NVENC) + fonts ----
try:
    import google.colab  # noqa
    IN_COLAB = True
except Exception:
    IN_COLAB = False

if IN_COLAB:
    sh("apt-get -qq update && apt-get -qq -y upgrade ffmpeg >/dev/null 2>&1 || true")
    sh("apt-get -qq -y install fonts-dejavu-core >/dev/null 2>&1 || true")
    print("ffmpeg:", subprocess.run("ffmpeg -hide_banner -version | head -1",
                                    shell=True, capture_output=True, text=True).stdout.strip())

# ---- 2) python deps ----
sh("pip -q install supabase pydantic-settings yt-dlp requests httpx openai "
   "pillow numpy opencv-python-headless 2>&1 | tail -1 || true")

# ---- 3) download + unpack the ClipViral backend ----
os.makedirs(ROOT, exist_ok=True)
if not os.path.exists(f"{BACKEND}/workers/gpu_daemon.py"):
    print("downloading ClipViral worker...", flush=True)
    urllib.request.urlretrieve(TARBALL_URL, f"{ROOT}/cv.tar.gz")
    with tarfile.open(f"{ROOT}/cv.tar.gz") as tf:
        tf.extractall(BACKEND)
    print("unpacked.", flush=True)

# ---- 4) write .env (gpu_daemon reads Colab Secrets itself; .env is fallback) --
os.makedirs("/content/cvmedia", exist_ok=True)
lines = ["MEDIA_DIR=/content/cvmedia"]
for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "GROQ_API_KEY"):
    v = os.environ.get(k)
    if v:
        lines.append(f"{k}={v}")
open(f"{BACKEND}/.env", "w").write("\n".join(lines) + "\n")

# ---- 5) run the farm with auto-restart supervisor ----
os.chdir(BACKEND)
print("\n=== ClipViral GPU render farm — Ctrl+Stop in Colab to end ===\n", flush=True)
while True:
    rc = subprocess.call([sys.executable, "-m", "workers.gpu_daemon"])
    print(f"worker exited rc={rc} — restarting in 10s", flush=True)
    import time; time.sleep(10)

# ============================================================================
# KAGGLE variant (optional): same steps, minus the apt-get lines (no root).
# Set the three values as Kaggle "Environment variables" (Input cells ->
# Secrets tab is not present; use notebook inputs or hardcode privately),
# skip block 1 entirely, and keep blocks 2-5. NVENC may be unavailable on
# Kaggle -> it auto-falls back to CPU encode (still faster than Render).
# ============================================================================
