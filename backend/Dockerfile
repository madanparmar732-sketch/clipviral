# OpusClip Clone — Backend Docker image
# FFmpeg is installed here. This is why we use Docker on Render:
# the server needs FFmpeg (the "video scissors") and this installs it for us.

FROM python:3.11-slim

# Install FFmpeg (video cutting/cropping) and fonts (for burned-in captions)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Render gives us a PORT number; default to 10000 for local runs
ENV PYTHONUNBUFFERED=1
EXPOSE 10000

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}
