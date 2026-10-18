"""Downloads a video from a link (YouTube, Facebook, X, Instagram, ...) using yt-dlp.

Security first: the URL is checked so nobody can make the server fetch its own
internal files/addresses (this is called an SSRF attack).

YouTube sometimes shows a "confirm you're not a bot" wall to cloud servers.
That is why we try several PLAYER DISGUISES (android, tv, ios, ...) until one
gets through — like trying on different outfits at a bouncer. 🎭
"""

import glob
import ipaddress
import logging
import os
import socket
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

MAX_LINK_BYTES = 500 * 1024 * 1024  # never fetch more than 500 MB
MAX_LINK_SECONDS = 2 * 60 * 60      # never more than 2 hours of video

BLOCKED_HOSTNAMES = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal"}

# Each disguise = a different YouTube "player". The bot wall knows some of them,
# not all. Order matters: android punched through the exact video that failed
# on Render, so it goes first.
YOUTUBE_STRATEGIES: list[tuple[str, list[str] | None]] = [
    ("android", ["android"]),
    # PO-token flow combo (yt-dlp issue #253): when the first client gets
    # LOGIN_REQUIRED, this mix walks yt-dlp into the clients that USE PO tokens
    # (the bgutil provider mints them). This is the flagged-IP wall breaker.
    ("po_combo", ["mweb", "tv", "web_safari"]),
    ("web", ["web"]),
    ("tv", ["tv"]),
    ("ios", ["ios"]),
    ("android_vr", ["android_vr"]),
    ("web_embedded", ["web_embedded"]),
    ("mweb", ["mweb"]),
    ("default", None),
]

_FORMAT = "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]/b"


def validate_url(url: str) -> str:
    """Make sure the URL is a real public http(s) link. Returns the cleaned URL."""
    cleaned = (url or "").strip()
    if not cleaned:
        raise ValueError("Please paste a video link.")
    parsed = urlparse(cleaned)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Please paste a normal video link starting with http:// or https://")
    host = (parsed.hostname or "").lower()
    if not host or host in BLOCKED_HOSTNAMES:
        raise ValueError("That address is not allowed.")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise ValueError("Could not find that website. Check the link.") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError("That address is not allowed.")
    return cleaned


def _human_error(err: Exception) -> str:
    """Turn yt-dlp's wall of text into one friendly sentence."""
    text = str(err)
    low = text.lower()
    if "sign in to confirm" in low or "not a bot" in low:
        return (
            "YouTube showed a 'confirm you're not a bot' wall for this video. "
            "Please try: a different video, another platform (Facebook/X/Instagram), "
            "or upload the video file directly."
        )
    if "age" in low and "restrict" in low:
        return (
            "This video is age-restricted (needs a YouTube login), so we can't fetch it. "
            "Please upload the video file directly."
        )
    if "private video" in low or "video is private" in low:
        return "This video is private — only public links can be fetched."
    if "unsupported url" in low or "no video found" in low or "not a valid url" in low:
        return "That link doesn't contain a downloadable video. Please check the URL."
    if "max_filesize" in low or "file is larger" in low:
        return "That video is over the 500 MB limit. Please try a shorter one or upload directly."
    if "max_duration" in low:
        return "That video is longer than 2 hours. Please try a shorter one."
    last = text.strip().splitlines()[-1] if text.strip() else "unknown error"
    return f"Could not fetch that video: {last[:150]}"


def _err_code(exc: Exception) -> str:
    """One tiny word per failure kind, so ALL disguises fit in one job error."""
    low = str(exc).lower()
    if "not a bot" in low or "sign in to confirm" in low:
        return "botwall"
    if "format is not available" in low:
        return "nofmt"
    if "reloaded" in low:
        return "reload"
    if "unavailable" in low:
        return "unavail"
    if "private" in low:
        return "private"
    if "age" in low and "restrict" in low:
        return "age"
    if "timed out" in low or "timeout" in low:
        return "timeout"
    return "err"


# Optional escape hatch: a YouTube cookies file defeats the bot-wall completely.
# Source order: Supabase storage health/yt_cookies.txt (changeable WITHOUT a
# redeploy) -> YT_COOKIES_B64 env var. Cached 10 minutes.
_COOKIE_CACHE: tuple[str | None, float] = (None, 0.0)


def _cookiefile() -> str | None:
    global _COOKIE_CACHE
    import base64
    import tempfile
    import time as _time

    now = _time.time()
    if _COOKIE_CACHE[0] and now - _COOKIE_CACHE[1] < 600:
        return _COOKIE_CACHE[0]
    path = None
    try:  # Supabase storage first — owner can rotate cookies without redeploying
        from app.config import settings
        from app.supabase_client import get_admin

        data = get_admin().storage.from_(settings.clips_bucket).download("health/yt_cookies.txt")
        if data and b"youtube.com" in data[:8000]:
            path = os.path.join(tempfile.gettempdir(), "yt_cookies.txt")
            with open(path, "wb") as fh:
                fh.write(data)
    except Exception:
        path = None
    if not path:
        b64 = os.environ.get("YT_COOKIES_B64", "")
        if b64:
            try:
                path = os.path.join(tempfile.gettempdir(), "yt_cookies.txt")
                with open(path, "wb") as fh:
                    fh.write(base64.b64decode(b64))
            except Exception:
                path = None
    _COOKIE_CACHE = (path, now)
    return path


def fetch_video(url: str, workdir: str, on_progress=None) -> dict:
    """Download the video into workdir.

    Returns {"path": ..., "title": ..., "duration": ..., "size": ...}.
    """
    import yt_dlp  # lazy import so the API boots fast

    os.makedirs(workdir, exist_ok=True)
    is_youtube = any(h in url for h in ("youtube.com", "youtu.be", "youtube-nocookie.com"))
    strategies = YOUTUBE_STRATEGIES if is_youtube else [("default", None)]

    def hook(d):
        if on_progress and d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            if total:
                try:
                    on_progress(min(99, int(done / total * 100)))
                except Exception:
                    pass

    last_err: Exception | None = None
    info = None
    errs: list[str] = []  # forensic digest -> lands in the job error so we can see remote failures

    class _PotProbe:
        """Counts PO-token activity inside yt-dlp so the job error proves whether
        the bgutil provider was actually used during the attempt."""

        def __init__(self) -> None:
            self.pot = 0

        def debug(self, msg) -> None:
            low = str(msg).lower()
            if "pot" in low and ("generat" in low or "request" in low):
                self.pot += 1

        info = debug

        def warning(self, msg) -> None:
            pass

        def error(self, msg) -> None:
            pass

    pot_probe = _PotProbe()
    cookiefile = _cookiefile()

    for name, clients in strategies:
        # clean leftovers from a previous attempt
        for f in glob.glob(os.path.join(workdir, "source.*")):
            try:
                os.remove(f)
            except OSError:
                pass

        # Two format passes per disguise: first the pretty format, then ANY single
        # file. Some disguises only carry a low-res muxed file — without the
        # fallback yt-dlp says "Requested format is not available" and we would
        # skip a disguise that actually WORKS (hit this with ios/mweb).
        for fmt in (_FORMAT, "b"):
            opts = {
                "format": fmt,
                "outtmpl": os.path.join(workdir, "source.%(ext)s"),
                "merge_output_format": "mp4",
                "noplaylist": True,
                "max_filesize": MAX_LINK_BYTES,
                "max_duration": MAX_LINK_SECONDS,
                "quiet": True,
                "no_warnings": True,
                "buffersize": 8192,
                "http_chunk_size": 262144,
                "progress_hooks": [hook],
                "logger": pot_probe,
            }
            if clients:
                opts["extractor_args"] = {"youtube": {"player_client": clients}}
            if cookiefile:
                opts["cookiefile"] = cookiefile

            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                logger.info("Link fetch succeeded with disguise %r fmt %r", name, fmt)
                break
            except Exception as exc:
                last_err = exc
                digest = f"{name}:{_err_code(exc)}"
                if digest not in errs:  # both fmt passes usually say the same thing
                    errs.append(digest)
                logger.warning("Link fetch disguise %r fmt %r failed: %s", name, fmt, str(exc)[:160])
        if info is not None:
            break

    if info is None:
        ver = getattr(getattr(yt_dlp, "version", None), "__version__", "?")
        debug = "; ".join(errs)[:220]
        raise RuntimeError(
            f"{_human_error(last_err or Exception('unknown error'))} [debug ytdlp={ver} pot={pot_probe.pot} | {debug}]"
        )

    if info.get("_type") == "playlist":
        entries = info.get("entries") or []
        if not entries:
            raise RuntimeError("No downloadable video found at that link.")
        info = entries[0]

    title = (info.get("title") or "Linked video").strip()[:120] or "Linked video"
    try:
        duration = float(info.get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0

    # Find the downloaded file on disk.
    path = ""
    for req in info.get("requested_downloads") or []:
        if req.get("filepath"):
            path = req["filepath"]
            break
    if not path or not os.path.exists(path):
        candidates = [
            c for c in sorted(glob.glob(os.path.join(workdir, "source.*")))
            if not c.endswith((".part", ".ytdl", ".json", ".temp"))
        ]
        if not candidates:
            raise RuntimeError("Could not save the downloaded video.")
        path = candidates[0]

    size = os.path.getsize(path)
    if size <= 0:
        raise RuntimeError("The downloaded video is empty.")
    if size > MAX_LINK_BYTES:
        raise RuntimeError("That video is over the 500 MB limit.")

    return {"path": path, "title": title, "duration": duration, "size": size}


# ============ STREAM-FIRST MODE (no full download for link jobs) ============
# A 1-hour video over Render's free pipe took an hour to download. Instead:
#   - fetch ONLY the audio stream (a few MB) for Whisper, and
#   - resolve the direct 720p CDN URL; ffmpeg streams just the seconds it
#     needs for each clip via HTTP range requests.
# If any of this fails, the caller falls back to the classic full download.

_AUDIO_EXTS = (".m4a", ".mp3", ".opus", ".webm", ".aac")


def _common_opts(clients, cookiefile, extra):
    opts = {
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "buffersize": 8192,          # tiny RAM buffers (default 128KB x many)
        "http_chunk_size": 262144,    # 256KB at a time — never holds the video
        "concurrent_fragment_downloads": 1,
    }
    if clients:
        opts["extractor_args"] = {"youtube": {"player_client": clients}}
    if cookiefile:
        opts["cookiefile"] = cookiefile
    opts.update(extra)
    return opts


def stream_audio(url: str, workdir: str, on_progress=None) -> dict:
    """Download ONLY the audio stream. Returns {path,title,duration,size}."""
    import yt_dlp

    os.makedirs(workdir, exist_ok=True)
    is_yt = any(h in url for h in ("youtube.com", "youtu.be", "youtube-nocookie.com"))
    strategies = YOUTUBE_STRATEGIES if is_yt else [("default", None)]
    cookiefile = _cookiefile()

    def hook(d):
        if on_progress and d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            if total:
                try:
                    on_progress(min(99, int(done / total * 100)))
                except Exception:
                    pass

    last_err: Exception | None = None
    for name, clients in strategies:
        opts = _common_opts(clients, cookiefile, {
            "format": "ba/bestaudio/b",
            "outtmpl": os.path.join(workdir, "audio.%(ext)s"),
            "max_filesize": 80 * 1024 * 1024,   # audio only — 80MB ceiling
            "progress_hooks": [hook],
        })
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
            import glob as _g
            cands = [f for f in _g.glob(os.path.join(workdir, "audio.*"))
                     if f.lower().endswith(_AUDIO_EXTS + (".part",)) and not f.endswith(".part")]
            if not cands:
                raise RuntimeError("audio file missing after download")
            path = max(cands, key=os.path.getsize)
            size = os.path.getsize(path)
            if size < 2048:
                raise RuntimeError("audio file empty")
            logger.info("audio-only fetch ok via %r (%.1f MB)", name, size / 1e6)
            return {"path": path,
                    "title": (info or {}).get("title") or "link video",
                    "duration": float((info or {}).get("duration") or 0),
                    "size": size}
        except Exception as exc:
            last_err = exc
            logger.info("audio fetch failed via %r: %s", name, str(exc)[:120])
    if last_err:
        raise last_err
    raise RuntimeError("no strategies")


def resolve_direct_url(url: str) -> str:
    """The best <=720p DIRECT media URL (ffmpeg reads its byte ranges)."""
    import yt_dlp

    is_yt = any(h in url for h in ("youtube.com", "youtu.be", "youtube-nocookie.com"))
    strategies = YOUTUBE_STRATEGIES if is_yt else [("default", None)]
    cookiefile = _cookiefile()
    for name, clients in strategies:
        opts = _common_opts(clients, cookiefile, {
            "format": "b[height<=720][ext=mp4]/b[height<=720]/b[ext=mp4]/b",
            "noprogress": True,
        })
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                entries = info.get("entries") if info and info.get("_type") == "playlist" else [info]
                entry = next((e for e in (entries or []) if e), None)
                if not entry:
                    continue
                want = "720" if "youtube" in url else None
                for fmt in entry.get("formats") or []:
                    if not fmt.get("url"):
                        continue
                    if not str(fmt.get("ext", "")).lower() in ("mp4", "m4s", "webm", "mov"):
                        continue
                    h = int(fmt.get("height") or 0)
                    if h and h > 720:
                        continue
                    if want and str(fmt.get("format_note", "")) and want not in str(fmt.get("format_id", "")) + str(fmt.get("resolution", "")) + str(fmt.get("height", "")):
                        pass  # prefer loosely; take the first fit
                    return fmt["url"]
                # nothing <=720: last resort, the smallest video format
                small = min((f for f in entry.get("formats") or [] if f.get("url") and (f.get("height") or 9999) <= 1080),
                            key=lambda f: (f.get("height") or 0), default=None)
                if small:
                    return small["url"]
        except Exception as exc:
            logger.info("direct-url resolve failed via %r: %s", name, str(exc)[:120])
            continue
    return ""
