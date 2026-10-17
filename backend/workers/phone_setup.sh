#!/data/data/com.termux/files/usr/bin/bash
# ClipViral phone worker installer for Termux.
# usage: bash phone_setup.sh <SUPABASE_URL> <SERVICE_ROLE_KEY> <GROQ_KEY>
set -e
SB_URL="$1"; SB_KEY="***"; GROQ="$3"
[ -z "$SB_URL" ] && { echo "usage: bash phone_setup.sh URL SERVICE_KEY GROQ_KEY"; exit 1; }

echo "[1/4] installing packages (ffmpeg + python, ~3 min)..."
pkg update -y >/dev/null 2>&1 || true
pkg install -y python ffmpeg curl tar coreutils >/dev/null 2>&1 || pkg install -y python ffmpeg curl tar

echo "[2/4] python deps (~2 min)..."
pip install --quiet supabase pydantic-settings yt-dlp requests httpx openai pillow numpy || { echo "   retrying without --quiet..."; pip install supabase pydantic-settings yt-dlp requests httpx openai pillow numpy; }
# optional (face-aware reframe / recap) — safe to skip if these fail on Termux:
pip install --quiet opencv-python-headless moviepy 2>/dev/null || echo "   (opencv/moviepy skipped — center-crop reframe still works)"

echo "[3/4] writing .env ..."
cd "$(dirname "$0")"
cat > .env <<ENV
SUPABASE_URL=$SB_URL
SUPABASE_SERVICE_ROLE_KEY=$SB_KEY
GROQ_API_KEY=$GROQ
AI_PROVIDER=groq
MEDIA_DIR=$HOME/clipviral-media
PHONE_WORKER=1
ENV

echo "[4/4] wakelock (keeps CPU alive when screen is off)..."
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock && echo "   blocked deep sleep ✓" || echo "   (run 'termux-wake-lock' manually)"

echo
echo "✅ installed. Starting worker in background..."
nohup python -m workers.phone_daemon > "$HOME/worker.log" 2>&1 &
sleep 6
tail -5 "$HOME/worker.log" 2>/dev/null || true
echo
echo "Watch the log any time:  tail -f ~/worker.log"
