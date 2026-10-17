"""OpusClip-Parity feature services — all $0, no extra infra.

Everything OpusClip charges credits for, we do free:
- job options (genre / keywords / custom prompt / clip length / range / aspect)
- collections, duplicate clip, public share links
- AI thumbnails with title overlay
- censor bleep/mute on profanity
- filler-word cutting
- social pack (per-platform title/description/hashtags) + scheduled posts + .ics
- multi-language translation (translated SRT + burned translated re-render)
- brand kits (logo + colours + caption style)

Storage conventions (no schema changes needed):
- job options  -> clips/{job_id}/prefs.json (written at create, read by pipeline)
- social pack  -> clips/{job_id}/clip_N.social.json
- translated   -> clips/{job_id}/clip_N.{lang}.words.json + clip_N.{lang}.mp4
- share pages  -> shares/{share_id}.json  (PUBLIC bucket, read by /share page)
- user data    -> auth user_metadata: collections / schedules / brand_kits
"""

import json
import logging
import os
import re
import subprocess
import tempfile
import time
import uuid

from app.config import settings
from app.supabase_client import get_admin

logger = logging.getLogger(__name__)

BUCKET = "clips"  # settings.clips_bucket == "clips"

# ---------------------------------------------------------------- storage JSON


def _bucket():
    return get_admin().storage.from_(settings.clips_bucket)


def put_json(path: str, obj: dict) -> str:
    """Upload JSON to the public clips bucket (delete-first: same-path is 409)."""
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    try:
        _bucket().remove([path])
    except Exception:
        pass
    _bucket().upload(path, data, {"content-type": "application/json; charset=utf-8"})
    return _bucket().get_public_url(path)


def get_json(path: str) -> dict | None:
    try:
        raw = _bucket().download(path)
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def put_bytes(path: str, data: bytes, content_type: str) -> str:
    try:
        _bucket().remove([path])
    except Exception:
        pass
    _bucket().upload(path, data, {"content-type": content_type})
    return _bucket().get_public_url(path)


# ------------------------------------------------------------ job prefs (create options)


def save_job_prefs(job_id: str, prefs: dict) -> None:
    try:
        put_json(f"{job_id}/prefs.json", prefs)
    except Exception:
        logger.exception("could not save job prefs (non-fatal)")


def load_job_prefs(job_id: str) -> dict:
    return get_json(f"{job_id}/prefs.json") or {}


# ------------------------------------------------------------ user_metadata store
# collections / schedules / brand_kits live in user_metadata (no schema change).


def get_user_meta(user_id: str) -> dict:
    try:
        resp = get_admin().auth.admin.get_user_by_id(user_id)
        return dict(getattr(resp.user, "user_metadata", None) or {})
    except Exception:
        logger.exception("get_user_meta failed")
        return {}


def patch_user_meta(user_id: str, updates: dict) -> dict:
    """Merge `updates` into user_metadata and return the new metadata."""
    meta = get_user_meta(user_id)
    meta.update(updates)
    get_admin().auth.admin.update_user_by_id(user_id, {"user_metadata": meta})
    return meta


# ------------------------------------------------------------ collections


def list_collections(user_id: str) -> list[dict]:
    return list(get_user_meta(user_id).get("collections") or [])


def save_collections(user_id: str, collections: list[dict]) -> list[dict]:
    patch_user_meta(user_id, {"collections": collections})
    return collections


# ------------------------------------------------------------ schedules


def list_schedules(user_id: str) -> list[dict]:
    items = list(get_user_meta(user_id).get("schedules") or [])
    items.sort(key=lambda s: str(s.get("publish_at") or ""))
    return items


def save_schedules(user_id: str, schedules: list[dict]) -> list[dict]:
    patch_user_meta(user_id, {"schedules": schedules})
    return schedules


def schedules_to_ics(schedules: list[dict]) -> str:
    """Calendar file a creator can import into Google/Apple calendar."""
    def esc(t: str) -> str:
        return (t or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//ClipViral//Scheduler//EN"]
    for s in schedules:
        when = str(s.get("publish_at") or "")
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})", when)
        if not m:
            continue
        stamp = f"{m.group(1)}{m.group(2)}{m.group(3)}T{m.group(4)}{m.group(5)}00"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{s.get('id') or uuid.uuid4()}@clipviral",
            f"DTSTAMP:{stamp}",
            f"DTSTART:{stamp}",
            f"SUMMARY:{esc(str(s.get('platform', 'post')).upper())}: {esc(str(s.get('title') or 'Scheduled clip'))}",
            f"DESCRIPTION:{esc(str(s.get('description') or ''))}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


# ------------------------------------------------------------ brand kits


def list_brand_kits(user_id: str) -> list[dict]:
    return list(get_user_meta(user_id).get("brand_kits") or [])


def save_brand_kits(user_id: str, kits: list[dict]) -> list[dict]:
    patch_user_meta(user_id, {"brand_kits": kits})
    return kits


# ------------------------------------------------------------ share links


def make_share_id() -> str:
    return uuid.uuid4().hex[:12]


def write_share(share_id: str, payload: dict) -> str:
    return put_json(f"shares/{share_id}.json", payload)


def read_share(share_id: str) -> dict | None:
    if not re.fullmatch(r"[a-f0-9]{8,32}", share_id or ""):
        return None
    return get_json(f"shares/{share_id}.json")


# ------------------------------------------------------------ SRT / VTT


def _caption_lines(words: list[dict], max_chars: int = 34) -> list[tuple[float, float, str]]:
    """Group word timings into readable caption lines."""
    lines: list[tuple[float, float, str]] = []
    cur: list[dict] = []
    for w in words or []:
        cur.append(w)
        text = " ".join(str(x.get("word", "")).strip() for x in cur).strip()
        long_enough = len(text) >= max_chars
        sentence_end = str(w.get("word", "")).strip().endswith((".", "!", "?", "।"))
        if long_enough or sentence_end:
            if text:
                lines.append((float(cur[0].get("start", 0)), float(cur[-1].get("end", 0)), text))
            cur = []
    if cur:
        text = " ".join(str(x.get("word", "")).strip() for x in cur).strip()
        if text:
            lines.append((float(cur[0].get("start", 0)), float(cur[-1].get("end", 0)), text))
    return lines


def _ts(seconds: float, sep: str) -> str:
    ms = int(max(0.0, seconds) * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def words_to_srt(words: list[dict]) -> str:
    out = []
    for i, (a, b, text) in enumerate(_caption_lines(words), 1):
        out += [str(i), f"{_ts(a, ',')} --> {_ts(b, ',')}", text, ""]
    return "\n".join(out)


def words_to_vtt(words: list[dict]) -> str:
    out = ["WEBVTT", ""]
    for a, b, text in _caption_lines(words):
        out += [f"{_ts(a, '.')} --> {_ts(b, '.')}", text, ""]
    return "\n".join(out)


# ------------------------------------------------------------ filler words & profanity

FILLER_WORDS = {
    "um", "uh", "uhm", "erm", "hmm", "mmm", "ah", "eh",
    "like", "basically", "actually", "literally", "you know", "i mean", "so yeah",
}

PROFANITY = {
    "fuck", "fucking", "fucker", "shit", "bullshit", "bitch", "bastard", "asshole",
    "damn", "goddamn", "dick", "cock", "piss", "crap", "wtf", "stfu", "ass",
    "bc", "bkl", "chutiya", "madarchod", "bhosdike", "randi", "harami", "kutta",
}


def find_filler_ranges(words: list[dict]) -> list[tuple[float, float]]:
    return _word_ranges(words, FILLER_WORDS)


def find_profanity_ranges(words: list[dict]) -> list[tuple[float, float]]:
    return _word_ranges(words, PROFANITY)


def _word_ranges(words: list[dict], lexicon: set[str]) -> list[tuple[float, float]]:
    ranges: list[tuple[float, float]] = []
    for w in words or []:
        clean = re.sub(r"[^a-z']", "", str(w.get("word", "")).lower())
        if clean in lexicon:
            try:
                ranges.append((float(w["start"]), float(w["end"])))
            except Exception:
                pass
    return ranges


def merge_ranges(ranges: list[tuple[float, float]], gap: float = 0.08) -> list[tuple[float, float]]:
    """Merge tiny gaps so ffmpeg gets one clean enable expression."""
    merged: list[list[float]] = []
    for a, b in sorted(ranges or []):
        if merged and a <= merged[-1][1] + gap:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return [(a, b) for a, b in merged]


# ------------------------------------------------------------ social pack (AI copy)


def build_social_pack(title: str, hook: str, transcript_snippet: str, hashtags: list[str],
                      prompt: str = "", lang: str = "en") -> dict:
    """Platform-optimised post copy — OpusClip's social-copy-jobs, free via Groq."""
    from app.services import ai

    client = ai.make_ai_client()
    tag_str = " ".join(f"#{t.lstrip('#')}" for t in (hashtags or [])[:8])
    user = (
        f"Clip title: {title}\nHook: {hook}\nTranscript snippet: {transcript_snippet[:600]}\n"
        f"Existing hashtags: {tag_str}\nLanguage for the copy: {lang}\n"
        f"Extra style instruction: {prompt or 'none'}"
    )
    system = (
        "You are a short-form video social copywriter. Return ONLY JSON with keys "
        "youtube, tiktok, instagram, x, linkedin, facebook. Each value is an object with "
        "keys: title (max 90 chars, hooky), description (2-3 sentences + 3-5 hashtags), "
        "hashtags (array of 5-8 strings without #). Match each platform's tone: YouTube SEO-friendly, "
        "TikTok casual, Instagram visual, X punchy under 200 chars, LinkedIn professional, Facebook friendly."
    )
    try:
        resp = client.chat.completions.create(
            model=ai.chat_model(),
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.7,
            max_tokens=900,
        )
        raw = resp.choices[0].message.content or "{}"
        m = re.search(r"\{.*\}", raw, re.S)
        data = json.loads(m.group(0)) if m else {}
        out = {}
        for plat in ("youtube", "tiktok", "instagram", "x", "linkedin", "facebook"):
            v = data.get(plat) or {}
            out[plat] = {
                "title": str(v.get("title") or title)[:120],
                "description": str(v.get("description") or hook)[:800],
                "hashtags": [str(t).lstrip("#") for t in (v.get("hashtags") or [])][:8],
            }
        return out
    except Exception:
        logger.exception("social pack AI failed — using fallback")
        return {
            p: {"title": title, "description": f"{hook} {' '.join(tag_str.split()[:5])}", "hashtags": hashtags[:6]}
            for p in ("youtube", "tiktok", "instagram", "x", "linkedin", "facebook")
        }


# ------------------------------------------------------------ translation


def translate_words(words: list[dict], lang: str) -> list[dict]:
    """Translate word-by-word while KEEPING timings (chunked Groq call)."""
    from app.services import ai

    client = ai.make_ai_client()
    out: list[dict] = []
    chunk = 90
    for i in range(0, len(words or []), chunk):
        part = words[i:i + chunk]
        text = " ".join(str(w.get("word", "")) for w in part)
        try:
            resp = client.chat.completions.create(
                model=ai.chat_model(),
                messages=[
                    {"role": "system", "content":
                        f"Translate the text to language code '{lang}'. Keep word order natural. "
                        "Return ONLY the translated words separated by spaces — no punctuation added, no notes."},
                    {"role": "user", "content": text},
                ],
                temperature=0.2,
                max_tokens=800,
            )
            translated = (resp.choices[0].message.content or "").split()
        except Exception:
            logger.exception("translate chunk failed — copying words through")
            translated = [str(w.get("word", "")) for w in part]
        # spread translated tokens across the original timings proportionally
        n_src, n_tgt = len(part), max(1, len(translated))
        for j, w in enumerate(part):
            a, b = j * n_tgt // n_src, (j + 1) * n_tgt // n_src
            token = " ".join(translated[a:b]) or str(w.get("word", ""))
            out.append({"word": token, "start": w.get("start", 0), "end": w.get("end", 0)})
    return out


# ------------------------------------------------------------ thumbnails


def _run(cmd: list[str], timeout: int = 180) -> None:
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if res.returncode != 0:
        raise RuntimeError((res.stderr or "ffmpeg failed")[-300:])


def make_thumbnail_candidates(clip_video_local: str, title: str, out_dir: str,
                              when_seconds: list[float] | None = None) -> list[str]:
    """3 thumbnail jpgs: best-ish frames + big title overlay (Opus generative thumbs, $0)."""
    os.makedirs(out_dir, exist_ok=True)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", clip_video_local],
        capture_output=True, text=True, timeout=60,
    )
    try:
        dur = float((probe.stdout or "0").strip() or 0)
    except ValueError:
        dur = 0.0
    if dur <= 0.2:
        dur = 3.0
    whens = when_seconds or [dur * 0.15, dur * 0.5, dur * 0.85]

    ass_path = os.path.join(out_dir, "title.ass")
    safe_title = (title or "Viral moment")[:48]
    with open(ass_path, "w", encoding="utf-8") as fh:
        fh.write(
            "[Script Info]\nPlayResX: 720\nPlayResY: 1280\nWrapStyle: 0\n\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Outline, Shadow, Alignment\n"
            "Style: T,DejaVu Sans,64,&H00FFFFFF,&H00000000,&H80000000,-1,4,2,8\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Text\n"
            f"Dialogue: 0,0:00:00.00,0:00:05.00,T,{safe_title.replace(',', '，')}\n"
        )

    paths = []
    for i, at in enumerate(whens):
        out = os.path.join(out_dir, f"thumb_{i + 1}.jpg")
        # ':' inside the ass path must be escaped or libass parses it as a filter arg
        ass_arg = os.path.abspath(ass_path).replace(":", "\\:")
        _run([
            "ffmpeg", "-y", "-threads", "1", "-ss", f"{at:.2f}", "-i", clip_video_local,
            "-frames:v", "1",
            "-vf", f"scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,ass='{ass_arg}'",
            "-q:v", "4", out,
        ], timeout=120)
        paths.append(out)
    return paths


# ------------------------------------------------------------ censor render


def apply_censor(input_mp4: str, out_mp4: str, ranges: list[tuple[float, float]],
                 beep: bool = False) -> str:
    """Silence (or bleep) the given time ranges inside an existing clip."""
    ranges = merge_ranges(ranges)
    if not ranges:
        _run(["ffmpeg", "-y", "-threads", "1", "-i", input_mp4, "-c", "copy", out_mp4])
        return out_mp4
    enable = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in ranges)
    if not beep:
        filt = f"[0:a]volume=0:enable='{enable}'[aout]"
        cmd = ["ffmpeg", "-y", "-threads", "1", "-i", input_mp4,
               "-filter_complex", filt, "-map", "0:v", "-map", "[aout]",
               "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", out_mp4]
    else:
        # original muted in ranges + 1 kHz tone gated ON inside ranges
        gate = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in ranges)
        filt = (
            f"[0:a]volume=0:enable='{enable}'[orig];"
            f"[1:a]volume=volume='if({gate},1,0)':eval=frame[beep];"
            f"[orig][beep]amix=inputs=2:duration=first:dropout_transition=0[aout]"
        )
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", input_mp4],
            capture_output=True, text=True, timeout=60,
        )
        dur = float((probe.stdout or "5").strip() or 5.0)
        cmd = ["ffmpeg", "-y", "-threads", "1", "-i", input_mp4,
               "-f", "lavfi", "-i", f"sine=frequency=1000:sample_rate=44100:duration={dur:.2f}",
               "-filter_complex", filt, "-map", "0:v", "-map", "[aout]",
               "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", out_mp4]
    _run(cmd, timeout=300)
    return out_mp4


# ------------------------------------------------------------ brand logo overlay


def overlay_logo(video_path: str, logo_path: str) -> None:
    """Burn the brand logo into the top-right corner (post-render pass)."""
    tmp = video_path + ".logo.mp4"
    _run([
        "ffmpeg", "-y", "-threads", "1", "-i", video_path, "-i", logo_path,
        "-filter_complex", "[1:v]scale=140:-1[lg];[0:v][lg]overlay=W-w-24:24[v]",
        "-map", "[v]", "-map", "0:a",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-c:a", "copy", tmp,
    ], timeout=300)
    os.replace(tmp, video_path)


# ------------------------------------------------------------ webhook notify


def fire_webhook(url: str, payload: dict) -> None:
    if not url or not str(url).startswith(("http://", "https://")):
        return
    try:
        import urllib.request

        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        logger.exception("webhook delivery failed (non-fatal)")
