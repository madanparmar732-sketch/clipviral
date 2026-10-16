"""Builds animated captions (ASS) from word timestamps — with 20 viral styles.

Golden rule: caption lines NEVER overlap in time (the old smash bug).
Free plan gets 3 styles, Pro gets all 20.
"""

FREE_STYLES = ["beast", "minimal", "bold_box"]

# name: (font, size, primary, secondary, outline, back, bold, outline_w, shadow, margin_v, effect)
STYLE_PRESETS: dict[str, dict] = {
    "beast":       {"font": "DejaVu Sans", "size": 88, "primary": "&H00FFFFFF", "secondary": "&H0000FFFF", "outline_c": "&H00101010", "back": "&HA0000000", "bold": -1, "outline": 7, "shadow": 3, "margin_v": 300},
    "mrbeast":     {"font": "DejaVu Sans", "size": 96, "primary": "&H00FFFF00", "secondary": "&H00FFFFFF", "outline_c": "&H00000000", "back": "&H80000000", "bold": -1, "outline": 8, "shadow": 2, "margin_v": 280},
    "tiktok":      {"font": "DejaVu Sans", "size": 80, "primary": "&H00FFFFFF", "secondary": "&H005050FF", "outline_c": "&H00202020", "back": "&HA0000000", "bold": -1, "outline": 5, "shadow": 4, "margin_v": 320},
    "neon":        {"font": "DejaVu Sans", "size": 84, "primary": "&H00FFFF80", "secondary": "&H0080FF00", "outline_c": "&H0000A5FF", "back": "&HA0000000", "bold": -1, "outline": 6, "shadow": 0, "margin_v": 300},
    "minimal":     {"font": "DejaVu Sans", "size": 66, "primary": "&H00FFFFFF", "secondary": "&H00E0E0E0", "outline_c": "&H00303030", "back": "&H00000000", "bold": 0, "outline": 3, "shadow": 1, "margin_v": 260},
    "bold_box":    {"font": "DejaVu Sans", "size": 78, "primary": "&H00FFFFFF", "secondary": "&H0000FFFF", "outline_c": "&H00000000", "back": "&HC0000000", "bold": -1, "outline": 2, "shadow": 0, "margin_v": 300, "box": True},
    "karaoke_bar": {"font": "DejaVu Sans", "size": 82, "primary": "&H00000000", "secondary": "&H0000E7FF", "outline_c": "&H00000000", "back": "&H00FFFFFF", "bold": -1, "outline": 2, "shadow": 0, "margin_v": 300, "box": True},
    "pop_shadow":  {"font": "DejaVu Sans", "size": 90, "primary": "&H00FFFFFF", "secondary": "&H00FFD700", "outline_c": "&H00101010", "back": "&H80000000", "bold": -1, "outline": 4, "shadow": 6, "margin_v": 300},
    "sunset":      {"font": "DejaVu Sans", "size": 86, "primary": "&H00FFFFFF", "secondary": "&H000080FF", "outline_c": "&H00201000", "back": "&HA0000000", "bold": -1, "outline": 6, "shadow": 3, "margin_v": 300},
    "mint":        {"font": "DejaVu Sans", "size": 86, "primary": "&H00FFFFFF", "secondary": "&H0050FF80", "outline_c": "&H00102010", "back": "&HA0000000", "bold": -1, "outline": 6, "shadow": 3, "margin_v": 300},
    "fire":        {"font": "DejaVu Sans", "size": 88, "primary": "&H00FFFFFF", "secondary": "&H004040FF", "outline_c": "&H00000040", "back": "&HA0000000", "bold": -1, "outline": 7, "shadow": 3, "margin_v": 300},
    "royal":       {"font": "DejaVu Sans", "size": 86, "primary": "&H00FFFFFF", "secondary": "&H00D080FF", "outline_c": "&H00300020", "back": "&HA0000000", "bold": -1, "outline": 6, "shadow": 3, "margin_v": 300},
    "bubble":      {"font": "DejaVu Sans", "size": 76, "primary": "&H00202020", "secondary": "&H00FF8080", "outline_c": "&H00FFFFFF", "back": "&H00FFFFFF", "bold": -1, "outline": 1, "shadow": 0, "margin_v": 310, "box": True},
    "stripe":      {"font": "DejaVu Sans", "size": 80, "primary": "&H00FFFFFF", "secondary": "&H0000FF00", "outline_c": "&H00000000", "back": "&HC0000000", "bold": -1, "outline": 3, "shadow": 0, "margin_v": 340, "spacing": 3},
    "impact":      {"font": "DejaVu Sans", "size": 104, "primary": "&H00FFFFFF", "secondary": "&H00FFFF00", "outline_c": "&H00000000", "back": "&H80000000", "bold": -1, "outline": 8, "shadow": 2, "margin_v": 260},
    "lower_third": {"font": "DejaVu Sans", "size": 58, "primary": "&H00FFFFFF", "secondary": "&H00FFCC00", "outline_c": "&H00202020", "back": "&HA0000000", "bold": 0, "outline": 3, "shadow": 2, "margin_v": 170},
    "neon_pink":   {"font": "DejaVu Sans", "size": 84, "primary": "&H00FFB0FF", "secondary": "&H008080FF", "outline_c": "&H00FF0080", "back": "&HA0000000", "bold": -1, "outline": 6, "shadow": 0, "margin_v": 300},
    "ice":         {"font": "DejaVu Sans", "size": 84, "primary": "&H00FFFFFF", "secondary": "&H00FFE0C0", "outline_c": "&H00604020", "back": "&HA0000000", "bold": -1, "outline": 6, "shadow": 2, "margin_v": 300},
    "gold":        {"font": "DejaVu Sans", "size": 88, "primary": "&H0000E5FF", "secondary": "&H00FFFFFF", "outline_c": "&H00003060", "back": "&HA0000000", "bold": -1, "outline": 7, "shadow": 3, "margin_v": 300},
    "mono":        {"font": "DejaVu Sans", "size": 72, "primary": "&H00F0F0F0", "secondary": "&H00B0B0B0", "outline_c": "&H00181818", "back": "&H00000000", "bold": 0, "outline": 4, "shadow": 2, "margin_v": 280},
}


def _header(style_name: str) -> str:
    p = STYLE_PRESETS.get(style_name) or STYLE_PRESETS["beast"]
    border_style = 3 if p.get("box") else 1
    outline = p.get("outline", 7)
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{p['font']},{p['size']},{p['primary']},{p['secondary']},{p['outline_c']},{p['back']},{p['bold']},0,0,0,100,100,{p.get('spacing', 1)},0,{border_style},{outline},{p.get('shadow', 3)},2,80,80,{p.get('margin_v', 300)},1
Style: Mark,DejaVu Sans,42,&H96FFFFFF,&H00FFFFFF,&H00202020,&H00000000,0,0,0,0,100,100,1,0,1,3,1,3,28,28,42,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _timestamp(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:05.2f}"


def _group_words_into_lines(words: list[dict], clip_start: float, clip_end: float) -> list[list[dict]]:
    """Bundle words into caption lines: max 4 words, split on long pauses.
    Forces word times to be strictly increasing (Whisper overlap fix)."""
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


def build_ass_captions(words: list[dict], clip_start: float, clip_end: float, out_path: str,
                       style: str = "beast", watermark: bool = False) -> str:
    """Write an animated .ass subtitle file for one clip, in the chosen style."""
    lines = _group_words_into_lines(words, clip_start, clip_end)
    events: list[str] = []
    clip_len = max(0.5, clip_end - clip_start)

    for idx, line_words in enumerate(lines):
        line_start = line_words[0]["start"]
        natural_end = line_words[-1]["end"] + 0.10

        if idx + 1 < len(lines):
            next_start = lines[idx + 1][0]["start"]
            line_end = min(natural_end, next_start)  # NEVER overlap the next line
            if line_end - line_start < 0.12:
                line_end = min(line_start + 0.12, next_start)
        else:
            line_end = min(natural_end + 0.15, clip_len)

        if line_end <= line_start:
            continue

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
        events.append(f"Dialogue: 0,{_timestamp(0)},{_timestamp(max(1.0, clip_len))},Caption,,0,0,0,, ")

    if watermark:
        # Free plan: tiny badge in the corner (ASS layer — works on every ffmpeg build!)
        events.append(f"Dialogue: 0,{_timestamp(0)},{_timestamp(clip_len)},Mark,,0,0,0,,ClipViral")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(_header(style))
        f.write("\n".join(events))
        f.write("\n")
    return out_path


def remap_words(words: list[dict], kept_segments: list[tuple[float, float]]) -> list[dict]:
    """Rewrite absolute word timestamps onto the PAUSE-FREE timeline."""
    remapped: list[dict] = []
    offset = 0.0
    for seg_a, seg_b in kept_segments:
        seg_len = seg_b - seg_a
        for w in words:
            ws, we = float(w.get("start", 0)), float(w.get("end", 0))
            if we <= seg_a or ws >= seg_b:
                continue
            new_start = max(0.0, ws - seg_a) + offset
            new_end = min(seg_len, we - seg_a) + offset
            if new_end - new_start < 0.03:
                continue
            remapped.append({"start": round(new_start, 3), "end": round(new_end, 3), "word": w.get("word", "")})
        offset += seg_len
    return remapped


def line_start_times(words: list[dict]) -> list[float]:
    """Start time of every caption line — used to place SFX pops."""
    starts = []
    current_len = 0
    for w in words:
        if current_len == 0:
            starts.append(float(w.get("start", 0)))
        current_len += 1
        if current_len >= 4:
            current_len = 0
    return starts
