"""HyperFinder — the viral-moment engine (OpusClip-style, $0).

What OpusClip's ClipAnything does (their docs + reviews), rebuilt for free:

1. AUDIO ENERGY PASS   — loudness/energy peaks over sliding windows
                         (their "emotional peaks / environmental sound").
2. LINGUISTIC PASS     — hook patterns from engagement research:
                         open-loop questions, numbers/stats, surprise &
                         disagreement, emotional vocabulary, story beats
                         (their "linguistic patterns of high-performing content").
3. PACING/FLOW         — speech rate & momentum (their "Flow & pacing").
4. TREND               — topical/trendy-word heat (their "Trend" dimension).

Every candidate window gets 4 sub-scores → combined VIRALITY SCORE 0-99,
exactly the dimensions OpusClip publishes (Hook · Flow · Value · Trend).
Runs in ~1 second for ANY video length — no API, no model download.
"""

import logging
import math
import re
import subprocess

logger = logging.getLogger(__name__)

# ---- engagement lexicons (from short-form research; kept small + fast) ----
HOOK_WORDS = {
    "secret", "secrets", "nobody", "never", "always", "mistake", "mistakes", "truth",
    "actually", "stop", "warning", "why", "how", "what if", "imagine", "listen",
    "believe", "crazy", "insane", "shocking", "unbelievable", "wrong", "right",
}
EMOTION_WORDS = {
    "love", "hate", "angry", "furious", "scared", "afraid", "excited", "happy",
    "sad", "crying", "laugh", "funny", "hilarious", "awkward", "embarrassed",
    "proud", "regret", "guilty", "jealous", "panic", "stress", "anxiety",
}
SURPRISE_WORDS = {
    "wow", "whoa", "omg", "suddenly", "unexpected", "twist", "shocked", "surprise",
    "turned out", "plot twist", "no way", "wait", "hold on", "guess what", "finally",
}
STORY_WORDS = {
    "story", "happened", "remember", "once", "years ago", "that day", "that time",
    "moment", "first time", "last time", "after that", "before that", "then i",
}
VALUE_WORDS = {
    "tip", "tips", "hack", "hacks", "lesson", "lessons", "advice", "strategy",
    "steps", "step by step", "framework", "rule", "rules", "reason", "reasons",
    "because", "proof", "research", "study", "data", "percent", "million", "billion",
}
TREND_WORDS = {
    "ai", "chatgpt", "instagram", "youtube", "tiktok", "viral", "trending", "money",
    "crypto", "startup", "fitness", "side hustle", "passive income", "productivity",
    "growth", "mindset", "linkedin", "x", "twitter", "meta", "openai", "india", "us",
}

QUESTION_RE = re.compile(r"\?|^(why|how|what|when|where|who|which|do|does|did|is|are|can|could|would|will)\b", re.I)
NUMBER_RE = re.compile(r"\d+|percent|million|billion|thousand|hundred|lakh|crore", re.I)
NEG_RE = re.compile(r"\b(don'?t|never|no one|nobody|stop|quit|wrong|fail|failed|failure|problem|issue|worst|hate)\b", re.I)


def _segment_text(seg: dict) -> str:
    return (seg.get("text") or "").strip()


def _count_hits(text: str, lexicon: set[str]) -> int:
    low = text.lower()
    return sum(1 for w in lexicon if w in low)


def score_segments(segments: list[dict]) -> list[dict]:
    """Score EVERY transcript segment on 4 virality dimensions (ms-fast)."""
    # first pass: collect speech rates so Flow can be scored RELATIVE to the
    # video's own median pace (momentum spikes — OpusClip's "Flow & pacing")
    rates = []
    prepared = []
    for i, seg in enumerate(segments):
        text = _segment_text(seg)
        if not text:
            continue
        words = max(1, len(text.split()))
        dur = max(0.3, float(seg.get("end", 0)) - float(seg.get("start", 0)))
        rate = words / dur
        rates.append(rate)
        prepared.append((i, seg, text, rate))
    median_rate = sorted(rates)[len(rates) // 2] if rates else 3.0

    scored = []
    for i, seg, text, rate in prepared:
        hook = (
            2.2 * _count_hits(text, HOOK_WORDS)
            + 2.0 * (1 if QUESTION_RE.search(text) else 0)
            + 1.6 * (1 if NEG_RE.search(text) else 0)
        )
        # momentum vs this video's own baseline (spikes = exciting delivery)
        flow = max(0.0, min(25.0, (rate / max(0.5, median_rate) - 0.85) * 14.0))
        value = 1.8 * _count_hits(text, VALUE_WORDS) + 1.4 * (1 if NUMBER_RE.search(text) else 0)
        trend = 1.5 * _count_hits(text, TREND_WORDS) + 1.2 * _count_hits(text, SURPRISE_WORDS) + 1.3 * _count_hits(text, EMOTION_WORDS) + 1.4 * _count_hits(text, STORY_WORDS)

        # normalise each to 0..25 → total 0..99 like OpusClip
        h = min(25.0, hook * 3.4)
        f = flow
        v = min(25.0, value * 3.2)
        t = min(24.0, trend * 2.6)
        total = int(min(99, round(h + f + v + t)))
        scored.append({**seg, "idx": i, "hook": round(h, 1), "flow": round(f, 1),
                       "value": round(v, 1), "trend": round(t, 1), "score": total})
    return scored


def audio_energy_peaks(media_path: str, buckets: int = 60, duration: float | None = None) -> list[tuple[float, float]]:
    """Loudness per bucket via one fast ffmpeg astats pass (their audio-sentiment
    signal). Returns [(start, energy01), ...]. Falls back to [] on any error."""
    try:
        res = subprocess.run(
            ["ffmpeg", "-hide_banner", "-nostats", "-i", media_path,
             "-af", f"astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
             "-f", "null", "-"],
            capture_output=True, text=True, timeout=60,
        )
        lines = (res.stdout or "").splitlines()
        ts_vals: list[tuple[float, float]] = []
        t = None
        for ln in lines:
            m = re.search(r"pts_time:([0-9.]+)", ln)
            if m:
                t = float(m.group(1))
                continue
            m = re.search(r"RMS_level=([-0-9.]+|-inf)", ln)
            if m and t is not None:
                raw = m.group(1)
                val = 0.0 if raw == "-inf" else max(0.0, float(raw) + 60.0)  # -60dB → 0
                ts_vals.append((t, val))
                t = None
        if not ts_vals:
            return []
        peak = max(v for _, v in ts_vals) or 1.0
        normalised = [(tt, v / peak) for tt, v in ts_vals]
        # fold into buckets for a smooth curve
        out: list[tuple[float, float]] = []
        per = max(1, len(normalised) // buckets)
        for i in range(0, len(normalised), per):
            group = normalised[i:i + per]
            out.append((group[0][0], sum(v for _, v in group) / len(group)))
        return out
    except Exception:
        logger.exception("audio energy pass failed (non-fatal)")
        return []


def build_candidates(segments: list[dict], n: int = 6, min_len: float = 15.0,
                     max_len: float = 40.0, media_path: str | None = None) -> list[dict]:
    """Merge the 4 scoring passes into n candidate windows — the FAST finder.

    Returns [{start, end, score, hook, flow, value, trend, text}, ...] sorted by
    score. Total cost: ~1s for any video length.
    """
    scored = score_segments(segments)
    if not scored:
        return []

    energy = audio_energy_peaks(media_path) if media_path else []
    energy_bonus = {}
    if energy:
        span = max(1e-6, energy[-1][0] - energy[0][0])
        for tt, ev in energy:
            energy_bonus[int(tt)] = ev

    # rolling window of ~min_len..max_len seconds around each strong segment
    candidates: list[dict] = []
    used_ranges: list[tuple[float, float]] = []
    for s in sorted(scored, key=lambda x: -x["score"]):
        mid = (float(s["start"]) + float(s["end"])) / 2.0
        start = max(0.0, mid - min_len / 2.0)
        end = start + min_len
        # stretch toward the higher-scored neighbours up to max_len
        near = [x for x in scored if start - 1 <= float(x["start"]) <= end + max_len]
        near.sort(key=lambda x: -x["score"])
        if near:
            end = min(end + max_len - min_len, max(float(x["end"]) for x in near[:4]))
        if end - start > max_len:
            end = start + max_len
        if any(not (end <= a or start >= b) for a, b in used_ranges):
            continue
        used_ranges.append((start, end))

        inside = [x for x in scored if float(x["start"]) >= start - 0.5 and float(x["end"]) <= end + 0.5]
        if not inside:
            continue
        agg = {k: sum(x[k] for x in inside) / len(inside) for k in ("hook", "flow", "value", "trend")}
        ebonus = 0.0
        if energy_bonus:
            ebonus = 2.5 * (sum(energy_bonus.get(int(t), 0.0) for t in
                                [start + (end - start) * f / 4 for f in range(5)]) / 5.0)
        total = int(min(99, round(agg["hook"] + agg["flow"] + agg["value"] + agg["trend"] + ebonus)))
        text = " ".join(_segment_text(x) for x in inside)[:400]
        candidates.append({
            "start": round(start, 2), "end": round(end, 2), "score": total,
            "hook": round(agg["hook"], 1), "flow": round(agg["flow"], 1),
            "value": round(agg["value"], 1), "trend": round(agg["trend"], 1),
            "text": text,
        })
        if len(candidates) >= max(n * 2, 10):
            break

    candidates.sort(key=lambda c: -c["score"])
    # spread picks across the video (OpusClip: clips spread, not clustered)
    picked: list[dict] = []
    for c in candidates:
        if all(abs(c["start"] - p["start"]) > (end - start) * 0.6 for p in picked):
            picked.append(c)
        if len(picked) >= n:
            break
    return picked
