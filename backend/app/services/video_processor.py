"""FFmpeg + MoviePy: the actual video scissors.

- FFmpeg cuts each clip, crops it to 9:16 (TikTok/Reels shape) and burns
  the animated captions right into the picture.
- MoviePy stitches the clips into an optional "recap reel" (RECAP_ENABLED=true).
"""

import json
import logging
import os
import subprocess

logger = logging.getLogger(__name__)


def _run(command: list[str]) -> subprocess.CompletedProcess:
    logger.info("Running: %s", " ".join(command))
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(command)}\n{result.stderr[-2000:]}")
    return result


def probe_video(path: str) -> dict:
    result = _run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration:stream=width,height",
            "-of", "json",
            path,
        ]
    )
    data = json.loads(result.stdout or "{}")
    width = height = 0
    for stream in data.get("streams") or []:
        if stream.get("width"):
            width = int(stream["width"])
            height = int(stream["height"])
            break
    try:
        duration = float(data.get("format", {}).get("duration", 0.0))
    except (TypeError, ValueError):
        duration = 0.0
    return {"width": width, "height": height, "duration": duration}


def _crop_geometry(width: int, height: int) -> tuple[int, int, int, int]:
    """
    Figure out the biggest 9:16 window centered in the frame.
    Returns (crop_w, crop_h, x, y). Sizes are made even (video encoders demand it).
    """
    if width <= 0 or height <= 0:
        return 1080, 1920, 0, 0

    crop_w = min(width, int(height * 9 / 16))
    crop_h = int(crop_w * 16 / 9)
    crop_w -= crop_w % 2
    crop_h -= crop_h % 2
    x = max(0, (width - crop_w) // 2)
    y = max(0, (height - crop_h) // 2)
    return crop_w, crop_h, x, y


def render_clip(source_path: str, start: float, end: float, ass_path: str, out_path: str) -> str:
    """
    Cut one clip:
    1. Jump to `start`, record for (end - start) seconds.
    2. Crop to 9:16 (centered), scale to 1080x1920.
    3. Burn the animated captions into the video.
    4. Normalize loudness so it's not too quiet or too loud.
    """
    info = probe_video(source_path)
    crop_w, crop_h, x, y = _crop_geometry(info["width"], info["height"])

    video_filters = (
        f"crop={crop_w}:{crop_h}:{x}:{y},"
        f"scale=1080:1920:flags=lanczos,"
        f"setsar=1,"
        f"ass='{os.path.abspath(ass_path)}',"
        f"format=yuv420p"
    )

    duration = max(0.5, end - start)
    _run(
        [
            "ffmpeg", "-y",
            "-ss", f"{start:.2f}",
            "-i", source_path,
            "-t", f"{duration:.2f}",
            "-vf", video_filters,
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
            "-movflags", "+faststart",
            out_path,
        ]
    )
    return out_path


def make_thumbnail(clip_path: str, out_path: str, at_seconds: float = 1.5) -> str:
    """Snapshot from the finished clip for the dashboard cards."""
    _run(
        [
            "ffmpeg", "-y",
            "-ss", f"{at_seconds:.2f}",
            "-i", clip_path,
            "-frames:v", "1",
            "-vf", "scale=720:1280",
            "-q:v", "4",
            out_path,
        ]
    )
    return out_path


def make_recap_moviepy(clip_paths: list[str], out_path: str) -> str:
    """
    Optional bonus: MoviePy glues all clips together into one recap video
    with small fade in/out transitions. Needs more RAM, so it is off by default
    (turn on with RECAP_ENABLED=true).
    """
    from moviepy.editor import VideoFileClip, concatenate_videoclips, vfx  # imported lazily

    clips = []
    try:
        for path in clip_paths:
            clip = VideoFileClip(path).fx(vfx.fadein, 0.4).fx(vfx.fadeout, 0.4)
            clips.append(clip)
        final = concatenate_videoclips(clips, method="chain")
        final.write_videofile(
            out_path,
            codec="libx264",
            audio_codec="aac",
            preset="veryfast",
            threads=2,
            fps=30,
            logger=None,
        )
        final.close()
    finally:
        for clip in clips:
            try:
                clip.close()
            except Exception:
                pass
    return out_path
