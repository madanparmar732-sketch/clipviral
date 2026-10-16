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
    result = subprocess.run(command, capture_output=True, text=True, timeout=900)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(command)}\n{result.stderr[-2000:]}")
    return result


def _run_progress(command: list[str], total_seconds: float, on_progress) -> None:
    """Run ffmpeg and report progress (0.0-1.0) while it works,
    so the job progress bar NEVER freezes mid-clip."""
    logger.info("Running: %s", " ".join(command))
    proc = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    assert proc.stdout is not None
    last_frac = -1.0
    for line in proc.stdout:
        line = line.strip()
        frac = None
        if line.startswith("out_time_ms="):
            try:
                frac = (int(line.split("=", 1)[1]) / 1_000_000.0) / max(0.1, total_seconds)
            except ValueError:
                continue
        elif line.startswith("out_time="):
            try:
                h, m, s = line.split("=", 1)[1].split(":")
                frac = (int(h) * 3600 + int(m) * 60 + float(s)) / max(0.1, total_seconds)
            except ValueError:
                continue
        if frac is None:
            continue
        frac = max(0.0, min(1.0, frac))
        if frac - last_frac >= 0.02:  # report every ~2%
            last_frac = frac
            try:
                on_progress(frac)
            except Exception:
                pass
    _stdout, stderr = proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(command)}\n{(stderr or '')[-2000:]}")


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


def _smart_crop_x(source_path: str, start: float, end: float, width: int, height: int, crop_w: int) -> int:
    """Face-aware horizontal crop: keep the speaking face in the MIDDLE of the
    9:16 window instead of blindly center-cutting. Falls back to center."""
    center_x = max(0, (width - crop_w) // 2)
    if width <= crop_w:
        return 0
    try:
        import cv2  # lazy: only loaded when a clip is actually rendered

        cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        cap = cv2.VideoCapture(source_path)
        face_xs: list[float] = []
        span = max(0.2, end - start)
        for frac in (0.1, 0.35, 0.6, 0.85):
            cap.set(cv2.CAP_PROP_POS_MSEC, (start + span * frac) * 1000.0)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            small = cv2.resize(gray, (0, 0), fx=0.5, fy=0.5)
            found = cascade.detectMultiScale(
                small, scaleFactor=1.1, minNeighbors=5, minSize=(24, 24)
            )
            for (fx, _fy, fw, _fh) in found:
                face_xs.append((fx + fw / 2.0) * 2.0)  # back to full-res x
        cap.release()

        if not face_xs:
            return center_x

        # Densest cluster of face positions wins (one stray false detection can't).
        face_xs.sort()
        best_cluster: list[float] = []
        cluster: list[float] = [face_xs[0]]
        for x in face_xs[1:]:
            if x - cluster[-1] <= width * 0.15:
                cluster.append(x)
            else:
                if len(cluster) > len(best_cluster):
                    best_cluster = cluster
                cluster = [x]
        if len(cluster) > len(best_cluster):
            best_cluster = cluster

        focus = sum(best_cluster) / len(best_cluster)
        x = int(round(focus - crop_w / 2.0))
        x = max(0, min(x, width - crop_w))
        return x - (x % 2)
    except Exception:
        logger.warning("Smart crop unavailable; using center crop")
        return center_x


def render_clip(source_path: str, start: float, end: float, ass_path: str, out_path: str, on_progress=None) -> str:
    """
    Cut one clip:
    1. Jump to `start`, record for (end - start) seconds.
    2. Crop to 9:16 (centered), scale to 1080x1920.
    3. Burn the animated captions into the video.
    4. Normalize loudness so it's not too quiet or too loud.
    """
    info = probe_video(source_path)
    crop_w, crop_h, _center_x, y = _crop_geometry(info["width"], info["height"])
    # Face-aware horizontal position (falls back to center when no face found)
    x = _smart_crop_x(source_path, start, end, info["width"], info["height"], crop_w)

    video_filters = (
        f"crop={crop_w}:{crop_h}:{x}:{y},"
        f"scale=720:1280:flags=bilinear,"
        f"setsar=1,"
        f"ass='{os.path.abspath(ass_path)}',"
        f"format=yuv420p"
    )

    duration = max(0.5, end - start)
    command = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{start:.2f}",
        "-i", source_path,
        "-t", f"{duration:.2f}",
        "-vf", video_filters,
        # SPEED MODE for the tiny free machine:
        # -threads 1  -> one encode thread (two fight over half a CPU!)
        # no loudnorm -> we skip the expensive audio normalization pass
        # ultrafast   -> fastest x264 preset (captions are burned by the ass filter)
        "-threads", "1",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-movflags", "+faststart",
    ]
    if on_progress is None:
        _run(command + [out_path])
    else:
        _run_progress(
            command + ["-progress", "pipe:1", "-nostats", out_path],
            duration,
            on_progress,
        )
    return out_path


def make_thumbnail(clip_path: str, out_path: str, at_seconds: float = 1.5) -> str:
    """Snapshot from the finished clip for the dashboard cards."""
    _run(
        [
            "ffmpeg", "-y", "-threads", "1",
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
