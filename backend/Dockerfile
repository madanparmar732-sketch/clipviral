# OpusClip Clone — Backend Docker image
# FFmpeg is installed here. This is why we use Docker on Render:
# the server needs FFmpeg (the "video scissors") and this installs it for us.

FROM python:3.11-slim

# Install FFmpeg (video cutting/cropping) and fonts (for burned-in captions)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- YouTube anti-bot armour ---
# Node.js 22 = yt-dlp's JS challenge solver (without it many formats go "missing")
# + the bgutil PO-token provider mints Proof-of-Origin tokens that defeat YouTube's
# "Sign in to confirm you're not a bot" wall on datacenter IPs.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg git \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch 2.0.2 https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /opt/bgutil \
    && cd /opt/bgutil/server \
    && npm ci \
    && npx tsc

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy EVERYTHING (app/ + docker-start.sh) into the box
COPY . .

# Render gives us a PORT number; default to 10000 for local runs
ENV PYTHONUNBUFFERED=1
EXPOSE 10000

# docker-start.sh binds to whatever door Render tells us ($PORT) — never hardcode it
RUN chmod +x docker-start.sh
CMD ["./docker-start.sh"]
