"""AI highlight detection: finds the truly VIRAL moments, not just the first 30 seconds.

Big fix vs v1: when the AI answer failed we silently cut the video into equal
sequential blocks from the start ("3x30s from 0:00") — that is NOT viral.
Now: (a) the prompt DEMANDS hook-based, spread-out picks with a worked example,
(b) JSON parsing is bulletproof, (c) we re-ask the AI once if its picks look
like lazy sequential blocks, (d) the fallback scatters windows through the
whole video instead of tiling from 0.
"""

import json
import logging
import re
import time

from app.config import settings
from app.services.ai import chat_model, make_ai_client

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a world-class short-form video producer who finds viral moments in long videos \
(podcasts, interviews, trailers, talks, coaching calls).

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
- IDEAL length is 20-35 seconds (hard limits {min_s}-{max_s}). Shorter punchy clips beat long rambles. "start" and "end" are \
seconds inside the video, within [0, {duration}].
- PICK HOOKS, NOT SECTIONS: a clip starts at a bold claim, a question, a shocking \
fact, a punchline setup, a story turning point, or a burst of emotion — NEVER just \
because it is near the beginning of the video.
- The first 1-2 seconds of each clip must grab a stranger by the collar. If a \
candidate moment starts flat, start it earlier or pick a different moment.
- SPREAD THEM OUT: the {n} picks should come from DIFFERENT parts of the video. \
NEVER return three sequential blocks that tile the video from 0:00.
- END ON THE PAYLOAD: finish right after the payoff/punchline lands. Never end mid-sentence.
- Snap "start" and "end" to spoken word boundaries (use the transcript timestamps) \
and leave 0.2-0.3 seconds of breathing room before the first word.
- Clips must be self-contained: understandable without seeing the rest of the video.
- Do not overlap clips.
- "score" is an integer 1-100 virality estimate (hook strength, emotion, shareability).
- "hashtags": 3-5 tags that fit the topic, each starting with #.
- Never invent facts that are not in the transcript.

EXAMPLE of great picks for a 10-minute interview:
  {"clips": [
    {"title": "He said WHAT about his first job?!", "hook": "\"I got fired on day one.\"", "start": 74.2, "end": 118.9, "score": 92, "hashtags": ["#career", "#storytime"]},
    {"title": "The million-dollar mistake", "hook": "\"We lost everything in one weekend.\"", "start": 402.5, "end": 448.0, "score": 88, "hashtags": ["#business", "#lessons"]},
    {"title": "Nobody talks about this part", "hook": "\"Everyone skips this and regrets it later.\"", "start": 551.1, "end": 590.3, "score": 81, "hashtags": ["#advice", "#viral"]}
  ]}

Output JSON only. No markdown, no commentary."""


def _build_user_prompt(transcript_segments: list[dict], duration: float, prefs: dict | None = None,
                       candidates: list[dict] | None = None) -> str:
    prefs = prefs or {}
    lines = []
    cand_rounds = {round(float(c["start"])) for c in (candidates or [])}
    for seg in transcript_segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        star = " ★" if round(float(seg.get("start", 0))) in cand_rounds else ""
        lines.append(f"[{seg['start']:.1f}-{seg['end']:.1f}]{star} {text}")
    body = "\n".join(lines)
    extras = []
    if candidates:
        top = sorted(candidates, key=lambda c: -c["score"])[:10]
        win = "\n".join(
            f"- [{c['start']:.1f}-{c['end']:.1f}] score {c['score']} "
            f"(hook {c['hook']}, flow {c['flow']}, value {c['value']}, trend {c['trend']}): {c['text'][:110]}"
            for c in top
        )
        extras.append(
            "Our fast virality engine pre-scored these windows (★ marks them in the "
            "transcript) — treat them as strong hints:\n" + win
        )
    if prefs.get("genre"):
        extras.append(f"Video genre: {prefs['genre']}.")
    if prefs.get("topic_keywords"):
        kw = ", ".join(str(k) for k in prefs["topic_keywords"][:8])
        extras.append(f"IMPORTANT — prioritise moments about: {kw}.")
    if prefs.get("custom_prompt"):
        extras.append(f"User's custom instruction: {prefs['custom_prompt']}")
    if prefs.get("clip_durations"):
        try:
            lo, hi = prefs["clip_durations"][0]
            extras.append(f"Each clip must be between {int(lo)} and {int(hi)} seconds long.")
        except Exception:
            pass
    extras_txt = ("\n" + "\n".join(extras) + "\n") if extras else ""
    return (
        f"Video duration: {duration:.1f} seconds.\n\n"
        f"Transcript:\n{body}\n\n"
        f"{extras_txt}"
        f"Find the {settings.top_n_clips} most viral clips. Remember: JSON only, "
        f"hook-based starts, spread across the video."
    )


def _extract_json(raw: str) -> dict | list | None:
    """Pull JSON out of an LLM answer even if it wraps it in text or code fences."""
    text = (raw or "").strip()
    if not text:
        return None
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


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


def _looks_sequential(clips: list[dict], duration: float) -> bool:
    """Detect the lazy pattern: blocks that tile the video starting at 0:00."""
    if len(clips) < 2:
        return False
    ordered = sorted(clips, key=lambda c: c["start"])
    if ordered[0]["start"] > 6.0:
        return False  # first clip is not from the beginning — fine
    # Do they nearly touch each other AND cover at least 70% of the video?
    gaps_ok = all(ordered[i + 1]["start"] - ordered[i]["end"] < 8 for i in range(len(ordered) - 1))
    covered = sum(c["end"] - c["start"] for c in ordered)
    return gaps_ok and covered > 0.7 * min(duration, sum(c["end"] for c in ordered))


def _fallback_clips(segments: list[dict], duration: float, n: int) -> list[dict]:
    """Last resort when the AI is unreachable: pick the word-densest window in
    n DIFFERENT zones spread across the video (NOT sequential blocks from 0:00)."""
    if duration <= 0 or not segments:
        return []

    clips: list[dict] = []
    zone = duration / (2 * n + 1)  # odd number of zones -> we can skip the edges
    window = min(float(settings.clip_max_seconds), 30.0)

    for i in range(n):
        zone_start = (2 * i + 1) * zone          # zones at 1,3,5... avoid the very start
        zone_end = min(duration, zone_start + 2 * zone)
        best_start, best_words = zone_start, -1

        probe = zone_start
        while probe + window <= duration + 1 and probe < zone_end + 1:
            count = sum(
                1 for seg in segments
                if seg["start"] < min(probe + window, zone_end) and seg["end"] > probe
            )
            if count > best_words:
                best_words = count
                best_start = probe
            probe += 4

        clip_end = min(duration, best_start + window)
        if clip_end - best_start < settings.clip_min_seconds:
            best_start = max(0.0, clip_end - settings.clip_min_seconds)
        clips.append(
            {
                "title": f"Highlight #{i + 1}",
                "hook": "",
                "start": round(best_start, 2),
                "end": round(min(duration, best_start + window), 2),
                "score": 55 - i,
                "hashtags": [],
            }
        )
    return clips


def _ask_ai(client, system_prompt: str, user_prompt: str) -> list[dict]:
    response = client.chat.completions.create(
        model=chat_model(),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.6,
    )
    raw = response.choices[0].message.content if response.choices else ""
    data = _extract_json(raw)
    if isinstance(data, dict):
        data = data.get("clips") or []
    if not isinstance(data, list):
        return []
    out = []
    for i, clip in enumerate(data):
        if isinstance(clip, dict):
            clamped = _clamp_clip(clip, float(_ask_ai.last_duration), i)
            if clamped:
                out.append(clamped)
    return out


def _snap_to_sentences(clips: list[dict], segments: list[dict], duration: float) -> list[dict]:
    """Move each clip's edges to sentence/segment boundaries — never cut mid-word."""
    if not segments:
        return clips
    starts = [float(sg.get("start", 0)) for sg in segments]
    ends = [float(sg.get("end", 0)) for sg in segments]
    for c in clips:
        st, en = float(c.get("start", 0)), float(c.get("end", 0))
        for i, (a, b) in enumerate(zip(starts, ends)):
            if a < st < b:
                st = a
                break
        for a, b in zip(starts, ends):
            if a < en < b:
                en = b
                break
        c["start"] = round(max(0.0, st - 0.15), 2)
        c["end"] = round(min(float(duration), en + 0.1), 2)
    return clips


def detect_highlights(transcript: dict, duration: float, n: int | None = None, prefs: dict | None = None,
                      media_path: str | None = None) -> list[dict]:
    """Ask the AI for the top viral moments. Smart fallback if the AI is unreachable.

    SPEED: a local virality engine (moment_finder) pre-scores candidate windows in
    ~1s (audio energy + hook/emotion/trend linguistics + pacing — the same signals
    OpusClip's ClipBasic/ClipAnything use), then the LLM just confirms/refines.
    """
    prefs = prefs or {}
    segments = transcript.get("segments") or []
    # OpusClip parity: range {startSec,endSec} — only curate inside that window
    rng = prefs.get("range") or {}
    try:
        if rng.get("startSec") is not None or rng.get("endSec") is not None:
            lo = float(rng.get("startSec") or 0)
            hi = float(rng.get("endSec") or duration)
            segments = [
                s for s in segments
                if float(s.get("end", 0)) > lo and float(s.get("start", 0)) < hi
            ]
            duration = max(1.0, hi - lo)
    except Exception:
        logger.exception("range filter failed — using full video")
    n = n or settings.top_n_clips
    n = max(2, min(n, int(duration / 40) or 2))  # ~one clip per 40s of video
    clip_dur = None
    try:
        if prefs.get("clip_durations"):
            clip_dur = (int(prefs["clip_durations"][0][0]), int(prefs["clip_durations"][0][1]))
    except Exception:
        clip_dur = None

    if not segments or duration <= 0:
        return []

    # ---- HyperFinder: local virality engine (~1s, any video length) ----
    finder_cands: list[dict] = []
    try:
        from app.services import moment_finder

        t_finder = time.time()
        finder_cands = moment_finder.build_candidates(
            segments,
            n=n,
            min_len=float(clip_dur[0] if clip_dur else settings.clip_min_seconds),
            max_len=float(clip_dur[1] if clip_dur else settings.clip_max_seconds),
            media_path=media_path,
        )
        logger.info("HyperFinder scored %d candidate windows in %.2fs", len(finder_cands), time.time() - t_finder)
    except Exception:
        logger.exception("moment_finder failed (non-fatal) — LLM only")

    # NOTE: .replace() not .format() — the prompt contains literal JSON braces.
    prompt = (
        SYSTEM_PROMPT
        .replace("{n}", str(n))
        .replace("{min_s}", str(clip_dur[0] if clip_dur else settings.clip_min_seconds))
        .replace("{max_s}", str(clip_dur[1] if clip_dur else settings.clip_max_seconds))
        .replace("{duration}", f"{duration:.1f}")
    )
    user_prompt = _build_user_prompt(segments, duration, prefs=prefs, candidates=finder_cands)

    clips: list[dict] = []
    try:
        client = make_ai_client()
        _ask_ai.last_duration = duration
        clips = _ask_ai(client, prompt, user_prompt)

        # One corrective retry if the picks look like lazy sequential blocks.
        if clips and _looks_sequential(clips, duration):
            logger.info("AI picks looked sequential — asking once more for real hooks")
            fix_prompt = user_prompt + (
                "\n\nYour previous picks were sequential blocks from the start of the video. "
                "That is NOT viral. Pick DIFFERENT hook moments spread across the whole video."
            )
            retry = _ask_ai(client, prompt, fix_prompt)
            if retry and not _looks_sequential(retry, duration):
                clips = retry

    except Exception:
        logger.exception("AI highlight detection failed; using smart fallback")
        clips = []

    if not clips:
        # Prefer the pre-scored HyperFinder windows (already viral-shaped);
        # the old segment fallback is the last resort.
        if finder_cands:
            clips = [
                {
                    "title": (c.get("text") or "Viral moment")[:70].strip(),
                    "hook": (c.get("text") or "").split(".")[0][:90],
                    "start": c["start"],
                    "end": c["end"],
                    "score": c["score"],
                    "hashtags": [],
                }
                for c in sorted(finder_cands, key=lambda x: -x["score"])[:n]
            ]
        else:
            clips = _fallback_clips(segments, duration, n)

    # Never overlap: keep the higher-scored clip when two collide.
    clips.sort(key=lambda c: -c.get("score", 0))
    kept: list[dict] = []
    for clip in clips:
        if all(clip["end"] <= k["start"] + 1 or clip["start"] >= k["end"] - 1 for k in kept):
            kept.append(clip)
    kept.sort(key=lambda c: c["start"])
    kept = _snap_to_sentences(kept, segments, duration)
    return kept[:n]
