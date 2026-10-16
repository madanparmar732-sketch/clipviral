"""GPT-4o highlight detection: reads the transcript and finds the 3 most viral moments."""

import json
import logging

from app.config import settings
from app.services.ai import chat_model, make_ai_client

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a world-class short-form video producer who finds viral moments in long videos \
(podcasts, interviews, talks, coaching calls).

You will receive a transcript with timestamps in the form [start-end] text.

Return ONLY valid JSON with exactly this shape:
{
  "clips": [
    {
      "title": "curiosity-driven title, max 70 characters",
      "hook": "one punchy sentence shown at the start of the clip, max 120 characters",
      "start": 123.4,
      "end": 156.7,
      "score": 87,
      "hashtags": ["#tag1", "#tag2", "#tag3"]
    }
  ]
}

Rules:
- Return exactly {n} clips, ranked best-first.
- Each clip must be between {min_s} and {max_s} seconds long.
- "start" and "end" are seconds inside the video, must be within [0, {duration}].
- START STRONG: the clip's first words must be a hook — a bold claim, a question, a surprising \
fact, or the natural beginning of a story. NEVER start mid-thought or mid-sentence.
- END CLEAN: finish right after the payoff or punchline lands. Never mid-sentence.
- Clips must be self-contained: understandable without seeing the rest of the video.
- Snap "start" to the beginning of a spoken phrase (check the transcript timestamps) and leave \
0.2-0.3 seconds of breathing room before the first word.
- Do not overlap clips.
- "score" is an integer 1-100 virality estimate (hook strength, emotion, shareability).
- "hashtags": 3-5 tags that fit the topic, each starting with #.
- Never invent facts that are not in the transcript.
- Output JSON only. No markdown, no commentary."""


def _build_user_prompt(transcript_segments: list[dict], duration: float) -> str:
    lines = []
    for seg in transcript_segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        lines.append(f"[{seg['start']:.1f}-{seg['end']:.1f}] {text}")
    body = "\n".join(lines)
    return (
        f"Video duration: {duration:.1f} seconds.\n\n"
        f"Transcript:\n{body}\n\n"
        f"Find the {settings.top_n_clips} most viral clips. Remember: JSON only."
    )


def _clamp_clip(clip: dict, duration: float, index: int) -> dict | None:
    try:
        start = float(clip["start"])
        end = float(clip["end"])
    except (KeyError, TypeError, ValueError):
        return None

    start = max(0.0, min(start, duration))
    end = max(0.0, min(end, duration))
    # Breathing room before the first word so clips never start abruptly mid-breath.
    start = max(0.0, start - 0.25)

    length = end - start
    if length < settings.clip_min_seconds:
        end = min(duration, start + settings.clip_min_seconds)
    if end - start > settings.clip_max_seconds:
        end = start + settings.clip_max_seconds
    if end - start < 5:
        return None

    return {
        "title": str(clip.get("title") or f"Viral moment #{index + 1}")[:70],
        "hook": str(clip.get("hook") or "")[:120],
        "start": round(start, 2),
        "end": round(end, 2),
        "score": int(max(1, min(100, int(clip.get("score", 70))))),
        "hashtags": [str(t) for t in (clip.get("hashtags") or [])][:5],
    }


def _fallback_clips(segments: list[dict], duration: float, n: int) -> list[dict]:
    """
    If the AI answer can't be used, pick the word-densest window in each
    equal part of the video. Simple, but the show must go on.
    """
    if duration <= 0 or not segments:
        return []

    clips = []
    part = duration / n
    for i in range(n):
        window_start = i * part
        window_end = min(duration, window_start + part)
        best_start, best_words = window_start, -1

        probe = window_start
        while probe + 30 <= window_end + 1:
            count = sum(
                1
                for seg in segments
                if seg["start"] < min(probe + 30, window_end) and seg["end"] > probe
            )
            if count > best_words:
                best_words = count
                best_start = probe
            probe += 5

        clip_end = min(duration, best_start + 30)
        clips.append(
            {
                "title": f"Highlight #{i + 1}",
                "hook": "",
                "start": round(best_start, 2),
                "end": round(clip_end, 2),
                "score": 60 - i,
                "hashtags": [],
            }
        )
    return clips


def detect_highlights(transcript: dict, duration: float) -> list[dict]:
    """Ask GPT-4o for the top viral moments. Falls back to a simple heuristic if needed."""
    segments = transcript.get("segments") or []
    n = settings.top_n_clips

    if not segments or duration <= 0:
        return []

    client = make_ai_client()
    # NOTE: we use .replace() instead of .format() because the prompt contains
    # literal JSON example braces that .format() would try to interpret.
    prompt = (
        SYSTEM_PROMPT
        .replace("{n}", str(n))
        .replace("{min_s}", str(settings.clip_min_seconds))
        .replace("{max_s}", str(settings.clip_max_seconds))
        .replace("{duration}", f"{duration:.1f}")
    )

    clips: list[dict] = []
    try:
        response = client.chat.completions.create(
            model=chat_model(),
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": _build_user_prompt(segments, duration)},
            ],
            response_format={"type": "json_object"},
            temperature=settings.chat_temperature,
            max_tokens=3072,
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        raw_clips = parsed.get("clips") or []
        for i, raw in enumerate(raw_clips):
            clamped = _clamp_clip(raw, duration, i)
            if clamped:
                clips.append(clamped)
    except Exception:
        logger.exception("AI highlight detection failed — using fallback")

    # Remove overlaps: keep the higher-scored clip intact, trim the weaker one.
    clips.sort(key=lambda c: c["score"], reverse=True)
    cleaned: list[dict] = []
    for clip in clips:
        conflict = False
        for kept in cleaned:
            if clip["start"] < kept["end"] and clip["end"] > kept["start"]:
                conflict = True
                break
        if not conflict:
            cleaned.append(clip)
        if len(cleaned) == n:
            break

    if len(cleaned) < n:
        cleaned.extend(_fallback_clips(segments, duration, n)[len(cleaned):])

    return cleaned[:n]
