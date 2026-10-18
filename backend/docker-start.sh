#!/bin/bash
set -e
# THE one way to start the machine. Binds to Render's $PORT (10000 on Render, 8000 locally).

# YouTube PO-token provider (bgutil) on :4416 — yt-dlp's plugin auto-finds it.
# Background + tolerant: if it ever dies, the site still runs (links just retry).
node /opt/bgutil/server/build/main.js >/tmp/bgutil.log 2>&1 &
sleep 1

# Python frees memory back to the OS aggressively (glibc arena trim) — without
# this, RSS only ever climbs and Render OOM-restarts us mid-job.
export MALLOC_ARENA_MAX=2
export PYTHONMALLOC=malloc
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}" --limit-concurrency 32 --backlog 64
