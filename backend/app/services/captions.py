"""Builds animated captions (ASS subtitle file) from word timestamps.

The style: big bold uppercase words, word-by-word karaoke highlight (yellow),
a little pop-scale animation when each line appears — like OpusClip/ CapCut.
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
    """Bundle words into caption lines: max 4 words, split on long pauses."""
    inside = [
        {
            "start": max(0.0, w["start"] - clip_start),
            "end": max(0.0, w["end"] - clip_start),
            "word": (w.get("word") or "").strip(),
        }
        for w in words
        if w.get("end", 0) > clip_start + 0.05 and w.get("start", 9e9) < clip_end - 0.05
    ]

    lines: list[list[dict]] = []
    current: list[dict] = []
    for word in inside:
        if not word["word"]:
            continue
        if current:
            gap = word["start"] - current[-1]["end"]
            if len(current) >= 4 or gap > 0.8:
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

    for line_words in lines:
        line_start = line_words[0]["start"]
        line_end = line_words[-1]["end"] + 0.12
        if line_end <= line_start:
            continue

        # Line animation: quick fade in + scale pop.
        parts = ["{\\fad(60,50)\\fscx70\\fscy70\\t(0,170,\\fscx112\\fscy112)\\t(170,320,\\fscx100\\fscy100)}"]
        for word in line_words:
            duration_cs = max(1, int(round((word["end"] - word["start"]) * 100)))
            clean = word["word"].upper().replace("{", "(").replace("}", ")")
            # \\kf = karaoke fill: the word fills with the accent color as it is spoken.
            parts.append(f"{{\\kf{duration_cs}}}{clean} ")

        events.append(
            f"Dialogue: 0,{_timestamp(line_start)},{_timestamp(line_end)},Caption,,0,0,0,,{''.join(parts).strip()}"
        )

    if not events:
        # No words found: still create a valid (empty) file so FFmpeg doesn't crash.
        events.append(
            f"Dialogue: 0,{_timestamp(0)},{_timestamp(max(1.0, clip_end - clip_start))},Caption,,0,0,0,, "
        )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(ASS_HEADER)
        f.write("\n".join(events))
        f.write("\n")

    return out_path
