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


# ==================== GPU RENDER FARM SUPPORT ====================
# When the job is executed by a GPU worker (Colab/Kaggle notebook running
# workers/gpu_daemon.py, which sets CLIPVIRAL_GPU=1 after proving the box can
# really encode), we switch to NVIDIA's hardware encoder and unlock CPU
# threads. On the tiny Render box the old slow-path stays untouched.

def _gpu_encode_ready() -> bool:
    if os.environ.get("CLIPVIRAL_GPU", "") != "1":
        return False
    if "_ok" in globals().get("_GPU_ENC_CACHE", {}):
        return globals()["_GPU_ENC_CACHE"]["_ok"]
    ok = False
    try:
        probe = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"],
                               capture_output=True, text=True, timeout=30)
        if "h264_nvenc" in (probe.stdout or ""):
            # real encode of 5 black frames — proves the NVENC driver libs exist
            test = subprocess.run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                 "-f", "lavfi", "-i", "color=black:s=256x256:d=0.2",
                 "-c:v", "h264_nvenc", "-f", "null", "-"],
                capture_output=True, text=True, timeout=60)
            ok = test.returncode == 0
    except Exception:
        ok = False
    globals()["_GPU_ENC_CACHE"] = {"_ok": ok}
    logger.info("GPU encode available: %s", ok)
    return ok


def encode_args() -> list[str]:
    """Encoder flags for every clip render. libx264/ultrafast/1-thread on the
    free Render CPU; NVENC + all cores on a GPU worker."""
    if _gpu_encode_ready():
        return ["-c:v", "h264_nvenc", "-preset", "p1", "-tune", "ll",
                "-rc", "vbr", "-cq", "26", "-b:v", "0"]
    return ["-threads", "1", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23"]


def copy_cut_feasible(source_path: str, start: float, end: float,
                      tolerance: float = 2.0) -> float | None:
    """The 20x-cheap cut path: stream-copy video (NO re-encode) + fresh audio.

    Works only when the cut lands within `tolerance` seconds after a keyframe —
    anything else starts gray/glitchy. Returns the keyframe time to use, or
    None when this clip must go through the full encoder."""
    span = max(0.5, end - start)
    if span < 4 or start <= 0.05:
        return None  # tiny clips / from-zero cuts are already cheap-accurate? no: keep simple
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-skip_frame", "nokey",
             "-show_entries", "frame=pts_time",
             "-read_intervals", f"{max(0.0, start - 12)}%{end + 1}",
             "-of", "csv=p=0", source_path],
            capture_output=True, text=True, timeout=60)
    except Exception:
        return None
    keys: list[float] = []
    for line in (probe.stdout or "").splitlines():
        try:
            keys.append(float(line.strip()))
        except ValueError:
            continue
    earlier = [k for k in keys if k <= start + 0.25]
    if not earlier:
        return None
    kf = max(earlier)
    return kf if start - kf <= tolerance else None


def copy_cut_video(source_path: str, start: float, end: float, out_path: str) -> str:
    """Near-instant clip: input seeking + video stream copy + re-encoded audio."""
    dur = max(1.0, end - start)
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-ss", f"{start:.3f}", "-i", source_path, "-t", f"{dur:.3f}",
         "-c:v", "copy", "-an",
         "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
         "-movflags", "+faststart", out_path],
        check=True, capture_output=True, text=True, timeout=300)
    return out_path


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

        # LOADING THE CASCADE COSTS 1-2s — do it ONCE per process, reuse per clip.
        global _FACE_CASCADE
        cascade = globals().get("_FACE_CASCADE")
        if cascade is None:
            cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
            globals()["_FACE_CASCADE"] = cascade
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
        + (f"ass='{os.path.abspath(ass_path)}'," if os.path.getsize(ass_path) else "")
        + f"format=yuv420p"
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
        *encode_args(),
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


# ==================== PAUSE-REMOVAL + CUT ENGINE ====================

def detect_silences(path: str, start: float, end: float,
                    noise_db: float = -35.0, min_silence: float = 0.45) -> list[tuple[float, float]]:
    """Find silent stretches inside [start, end] using ffmpeg's silencedetect."""
    result = _run(
        [
            "ffmpeg", "-hide_banner",
            "-ss", f"{start:.2f}", "-i", path, "-t", f"{max(0.1, end - start):.2f}",
            "-af", f"silencedetect=noise={noise_db}dB:d={min_silence}",
            "-f", "null", "-",
        ]
    )
    silences: list[tuple[float, float]] = []
    s_start = None
    for line in (result.stderr or "").splitlines():
        line = line.strip()
        if "silence_start:" in line:
            try:
                s_start = float(line.split("silence_start:")[1].split()[0]) + start
            except ValueError:
                s_start = None
        elif "silence_end:" in line and s_start is not None:
            try:
                s_end = float(line.split("silence_end:")[1].split()[0].rstrip("|")) + start
                silences.append((s_start, s_end))
            except ValueError:
                pass
            s_start = None
    return silences


def silences_from_words(words: list[dict], start: float, end: float,
                        min_gap: float = 0.62, max_gap: float = 2.5) -> list[tuple[float, float]]:
    """Dead air from the transcript's own gaps — computed in microseconds instead
    of a full ffmpeg decode pass (detect_silences). Big render-speed win.
    A gap must be >= min_gap to count; long pauses are trimmed to max_gap so we
    keep a beat of silence but never dead air."""
    inside: list[tuple[float, float]] = []
    for w in words or []:
        try:
            s, e = float(w["start"]), float(w["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if e > start and s < end:
            inside.append((max(s, start), min(e, end)))
    if not inside:
        return []
    inside.sort()
    silences: list[tuple[float, float]] = []
    prev_end = inside[0][1]
    for s, e in inside[1:]:
        if s - prev_end >= min_gap:
            silences.append((prev_end, min(s, prev_end + max_gap)))
        prev_end = max(prev_end, e)
    return silences


def build_kept_segments(start: float, end: float, silences: list[tuple[float, float]],
                        pad: float = 0.12, min_keep: float = 0.22) -> list[tuple[float, float]]:
    """Complement of the silences = the parts we KEEP. Padding keeps a breath
    so words never get clipped mid-syllable."""
    cuts = sorted((max(start, s - pad), min(end, e + pad)) for s, e in silences)
    kept: list[tuple[float, float]] = []
    cursor = start
    for s, e in cuts:
        if s - cursor >= min_keep:
            kept.append((cursor, min(s, end)))
        cursor = max(cursor, e)
        if cursor >= end:
            break
    if end - cursor >= min_keep:
        kept.append((cursor, end))
    if not kept:
        kept = [(start, end)]
    return kept


def cut_and_concat(source_path: str, segments: list[tuple[float, float]], out_path: str,
                   video_chain: str = "", ass_path: str | None = None,
                   total_seconds: float | None = None, on_progress=None,
                   post_vf: str = "", audio_chain: str = "") -> str:
    """Cut the listed time ranges out of the source and glue them into ONE video.

    - video_chain: extra per-segment video filters (crop/scale) for fresh renders.
    - ass_path: burn captions AFTER gluing (None = captions already in the file).
    Used both by the pause-removal pipeline and the transcript editor.
    """
    segments = [(a, b) for a, b in segments if b - a > 0.05]
    if not segments:
        raise RuntimeError("Nothing left to render after cutting.")
    if len(segments) == 1 and not video_chain and not ass_path:
        raise RuntimeError("Nothing to cut.")  # identical copy, pointless

    parts_v, parts_a, labels = [], [], []
    for i, (a, b) in enumerate(segments):
        vf = f"trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS"
        if video_chain:
            vf += "," + video_chain
        parts_v.append(f"[0:v]{vf}[v{i}]")
        af = f"atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS"
        if audio_chain:
            af += "," + audio_chain
        parts_a.append(f"[0:a]{af}[a{i}]")
        labels.append(f"[v{i}][a{i}]")

    concat_in = "".join(labels)
    fc = ";".join(parts_v + parts_a) + f";{concat_in}concat=n={len(segments)}:v=1:a=1[vc][ac]"

    vsrc = "[vc]"
    if post_vf:
        fc += f";[vc]{post_vf}[vz]"
        vsrc = "[vz]"
    if ass_path and os.path.getsize(ass_path) > 0:
        ass_abs = os.path.abspath(ass_path).replace("\\", "/")
        fc += f";{vsrc}ass='{ass_abs}',format=yuv420p[vo]"
    else:
        fc += f";{vsrc}format=yuv420p[vo]"
    vout = "[vo]"

    command = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", source_path,
        "-filter_complex", fc,
        "-map", vout, "-map", "[ac]",
        *encode_args(),
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-movflags", "+faststart",
    ]

    if on_progress is None:
        _run(command + [out_path])
    else:
        total = total_seconds or sum(b - a for a, b in segments)
        _run_progress(command + ["-progress", "pipe:1", "-nostats", out_path], total, on_progress)
    return out_path


WATERMARK_VF = (
    "drawtext=text='ClipViral':font=Sans:fontsize=26:fontcolor=white@0.65:"
    "x=w-tw-20:y=h-th-18:box=1:boxcolor=black@0.22:boxborderw=8"
)


ASPECT_SIZES = {"9:16": (720, 1280), "1:1": (720, 720), "16:9": (1280, 720), "4:5": (720, 900)}
ASPECT_SIZES_HD = {"9:16": (1080, 1920), "1:1": (1080, 1080), "16:9": (1920, 1080), "4:5": (1080, 1350)}


def eq_filter(brightness: float = 0.0, contrast: float = 1.0, saturation: float = 1.0) -> str:
    if abs(brightness) < 0.005 and abs(contrast - 1.0) < 0.005 and abs(saturation - 1.0) < 0.005:
        return ""
    return f"eq=brightness={brightness:.3f}:contrast={contrast:.3f}:saturation={saturation:.3f}"


def pad_post_filter(out_w: int, out_h: int) -> str:
    """Blur-pad layout: video centered on a blurred full-screen copy (OpusClip style)."""
    return (
        f"split=2[bg0][fg0];"
        f"[bg0]scale={out_w}:{out_h}:force_original_aspect_ratio=increase,crop={out_w}:{out_h},boxblur=24:6[bg1];"
        f"[fg0]scale={out_w}:{out_h}:force_original_aspect_ratio=decrease[fg1];"
        f"[bg1][fg1]overlay=(W-w)/2:(H-h)/2:format=auto"
    )


def clip_video_chain(source_path: str, start: float, end: float, *, out_w: int = 720, out_h: int = 1280,
                     reframe: str = "face", enhance: bool = False, watermark: bool = False,
                     aspect: str = "9:16", layout: str = "full",
                     brightness: float = 0.0, contrast: float = 1.0, saturation: float = 1.0) -> str:
    """The crop/scale filter chain for one clip.

    - reframe 'face' = face-aware crop (falls back to center), 'center' = classic center crop.
    - enhance = upscale to 1080x1920 + sharpen (the 'Upscale' Pro feature).
    - watermark = burn the ClipViral badge (free plan).
    """
    info = probe_video(source_path)
    crop_w, crop_h, center_x, y = _crop_geometry(info["width"], info["height"])
    if reframe == "face":
        x = _smart_crop_x(source_path, start, end, info["width"], info["height"], crop_w)
    else:
        x = center_x
    size_map = ASPECT_SIZES_HD if enhance else ASPECT_SIZES
    out_w, out_h = size_map.get(aspect, size_map["9:16"])
    grade = eq_filter(brightness, contrast, saturation)
    if layout == "pad":
        return grade
    chain = f"crop={crop_w}:{crop_h}:{x}:{y},scale={out_w}:{out_h}:flags=bilinear,setsar=1"
    if enhance:
        chain += ",unsharp=5:5:0.9:5:5:0.0"
    if grade:
        chain += "," + grade
    return chain


def make_sfx(workdir: str) -> dict:
    """Synthesize tiny royalty-free sound effects (pop + whoosh) with ffmpeg."""
    sfx = {}
    pop = os.path.join(workdir, "sfx_pop.wav")
    whoosh = os.path.join(workdir, "sfx_whoosh.wav")
    _run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "sine=frequency=880:duration=0.14",
        "-af", "afade=t=out:st=0.03:d=0.11,volume=0.5", pop,
    ])
    _run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "anoisesrc=d=0.5:c=pink",
        "-af", "highpass=f=800,afade=t=in:st=0:d=0.12,afade=t=out:st=0.28:d=0.22,volume=0.35", whoosh,
    ])
    sfx["pop"] = pop
    sfx["whoosh"] = whoosh
    return sfx


def mix_sfx(video_path: str, out_path: str, sfx_paths: list[str], times: list[float]) -> str:
    """Mix tiny sound effects into the clip at the given moments (Auto SFX)."""
    if not sfx_paths or not times:
        raise RuntimeError("Nothing to mix.")
    inputs = ["-i", video_path]
    labels, filters = [], []
    for i, (sfx, t) in enumerate(zip(sfx_paths, times)):
        ms = int(max(0, t) * 1000)
        inputs += ["-i", sfx]
        filters.append(f"[{i + 1}:a]adelay={ms}|{ms}[s{i}]")
        labels.append(f"[s{i}]")
    n = len(times)
    filters.append(f"{''.join(labels)}amix=inputs={n + 1}:duration=first:normalize=0[mx]")
    fc = ";".join(filters)
    _run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        *inputs, "-filter_complex", fc,
        "-map", "0:v", "-map", "[mx]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
        out_path,
    ])
    return out_path
