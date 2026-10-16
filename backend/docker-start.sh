#!/bin/bash
set -e
# THE one way to start the machine. Binds to Render's $PORT (10000 on Render, 8000 locally).
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}"
