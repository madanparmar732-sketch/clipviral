"""Builds animated captions (ASS subtitle file) from word timestamps.

The style: big bold uppercase words, word-by-word karaoke highlight (yellow),
a little pop-scale animation when each line appears — like OpusClip/CapCut.

GOLDEN RULE: caption lines NEVER overlap in time. The instant line N+1
appears, line N is gone. Overlapping events smash letters on top of each
other (that was the "WE FALLI KNOW" bug).
"""

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,DejaVu Sans,88,&H00FFFFFF,&H0000FFFF,&H00101010,&HA0000000,-1,0,0,0,100,100,1,0,1,7,3,2,80,80,300,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _timestamp(seconds: float) -> str:
    """Seconds -> ASS time like 0:01:23.45"""
    if seconds < 0:
        seconds = 0.0
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:05.2f}"


def _group_words_into_lines(words: list[dict], clip_start: float, clip_end: float) -> list[list[dict]]:
    """Bundle words into caption lines: max 4 words, split on long pauses.

    Also forces word times to be strictly increasing — Whisper sometimes
    reports tiny overlapping word timestamps, which smash the karaoke timer.
    """
    inside = []
    for w in words:
        text = (w.get("word") or "").strip()
        if not text:
            continue
        s = max(0.0, float(w.get("start", 0.0)) - clip_start)
        e = max(0.0, float(w.get("end", 0.0)) - clip_start)
        if e <= s:
            e = s + 0.12
        inside.append({"start": s, "end": e, "word": text})
    inside.sort(key=lambda w: w["start"])

    fixed: list[dict] = []
    for w in inside:
        if fixed and w["start"] < fixed[-1]["start"] + 0.02:
            w["start"] = fixed[-1]["start"] + 0.02
        if w["end"] < w["start"] + 0.05:
            w["end"] = w["start"] + 0.12
        fixed.append(w)

    lines: list[list[dict]] = []
    current: list[dict] = []
    for word in fixed:
        if current:
            gap = word["start"] - current[-1]["end"]
            if len(current) >= 4 or gap > 0.7:
                lines.append(current)
                current = []
        current.append(word)
    if current:
        lines.append(current)
    return lines


def build_ass_captions(words: list[dict], clip_start: float, clip_end: float, out_path: str) -> str:
    """Write an animated .ass subtitle file for one clip."""
    lines = _group_words_into_lines(words, clip_start, clip_end)
    events: list[str] = []
    clip_len = max(0.5, clip_end - clip_start)

    for idx, line_words in enumerate(lines):
        line_start = line_words[0]["start"]
        natural_end = line_words[-1]["end"] + 0.10

        if idx + 1 < len(lines):
            next_start = lines[idx + 1][0]["start"]
            # NEVER live past the next line's first appearance — this is the
            # fix for captions stacking on top of each other.
            line_end = min(natural_end, next_start)
            if line_end - line_start < 0.12:
                line_end = min(line_start + 0.12, next_start)
        else:
            line_end = min(natural_end + 0.15, clip_len)

        if line_end <= line_start:
            continue

        # Karaoke slots: each word owns the time until the NEXT word starts,
        # so the yellow highlight lands exactly when that word is spoken
        # (no more mid-word lag when people talk with gaps).
        parts = ["{\\fad(50,40)\\fscx70\\fscy70\\t(0,160,\\fscx112\\fscy112)\\t(160,300,\\fscx100\\fscy100)}"]
        n = len(line_words)
        for i, word in enumerate(line_words):
            if i < n - 1:
                slot = line_words[i + 1]["start"] - word["start"]
            else:
                slot = line_end - word["start"]
            duration_cs = max(1, int(round(slot * 100)))
            clean = word["word"].upper().replace("{", "(").replace("}", ")")
            parts.append(f"{{\\kf{duration_cs}}}{clean} ")

        events.append(
            f"Dialogue: 0,{_timestamp(line_start)},{_timestamp(line_end)},Caption,,0,0,0,,{''.join(parts).strip()}"
        )

    if not events:
        # No words found: still create a valid (empty) file so FFmpeg doesn't crash.
        events.append(
            f"Dialogue: 0,{_timestamp(0)},{_timestamp(max(1.0, clip_len))},Caption,,0,0,0,, "
        )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(ASS_HEADER)
        f.write("\n".join(events))
        f.write("\n")

    return out_path


def remap_words(words: list[dict], kept_segments: list[tuple[float, float]]) -> list[dict]:
    """Rewrite absolute word timestamps onto the PAUSE-FREE timeline.

    kept_segments are ABSOLUTE times (inside the source video) that survive the
    pause-removal cuts. Words inside a kept segment get shifted so the first kept
    second becomes t=0 and removed pauses disappear from the timeline.
    Words that fall inside a removed pause are dropped.
    """
    remapped: list[dict] = []
    offset = 0.0
    for seg_a, seg_b in kept_segments:
        seg_len = seg_b - seg_a
        for w in words:
            ws, we = float(w.get("start", 0)), float(w.get("end", 0))
            if we <= seg_a or ws >= seg_b:
                continue  # fully outside this kept segment
            new_start = max(0.0, ws - seg_a) + offset
            new_end = min(seg_len, we - seg_a) + offset
            if new_end - new_start < 0.03:
                continue
            remapped.append(
                {"start": round(new_start, 3), "end": round(new_end, 3), "word": w.get("word", "")}
            )
        offset += seg_len
    return remapped
