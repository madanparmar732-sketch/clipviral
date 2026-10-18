"""Animated captions (ASS) from word timestamps — 20 CapCut-style templates.

Rewritten from scratch (Oct-2026): the old preset set was removed entirely at
the user's request. Every template leans on the two tricks that make CapCut
captions look like CapCut captions:

  1. word-by-word karaoke fill  (\\kf) — the spoken word lights up in accent
  2. entrance animation per word  (pop / rise / shake / typewriter / slide)

Special style "none": build_ass_captions returns an empty ASS file and the
pipeline skips the burn filter — captions OFF for the clip (and the re-caption
endpoint lets the user strip them from already-rendered clips).

Golden rule kept: caption lines NEVER overlap in time.
"""

FREE_STYLES = ["karaoke", "clean", "yellow_pop"]
DEFAULT_STYLE = "karaoke"

# id: style mechanics.  Colours are ASS &HAABBGGRR.
#   in:  line entrance — pop|slide|fade|typewriter|drop|rise|shake|none
#   act: active-word emphasis — big|rise|shake|none   (used with in:typewriter etc.)
#   kf:  karaoke fill on/off
STYLE_PRESETS: dict[str, dict] = {
    "none":         {"skip": True},
    "karaoke":      {"name": "Karaoke Pop",  "font": "DejaVu Sans", "size": 84, "primary": "&H00FFFFFF", "secondary": "&H0000E1FF", "outline_c": "&H00101010", "back": "&H80000000", "bold": -1, "outline": 5, "shadow": 2, "margin_v": 320, "in": "pop", "kf": True},
    "clean":        {"name": "Clean Sans",   "font": "DejaVu Sans", "size": 66, "primary": "&H00FFFFFF", "secondary": "&H00FFFFFF", "outline_c": "&H00202020", "back": "&H60000000", "bold": 0, "outline": 2, "shadow": 1, "margin_v": 300, "in": "fade", "kf": False},
    "yellow_pop":   {"name": "Yellow Pop",   "font": "DejaVu Sans", "size": 92, "primary": "&H00FFFFFF", "secondary": "&H0000D7FF", "outline_c": "&H00000000", "back": "&H80000000", "bold": -1, "outline": 7, "shadow": 0, "margin_v": 320, "in": "pop", "act": "big", "kf": False},
    "box_highlight":{"name": "Box Highlight","font": "DejaVu Sans", "size": 80, "primary": "&H00101010", "secondary": "&H0000E1FF", "outline_c": "&H00FFFFFF", "back": "&H0000E1FF", "bold": -1, "outline": 3, "shadow": 0, "margin_v": 320, "in": "none", "kf": True, "box": True},
    "neon_glow":    {"name": "Neon Glow",    "font": "DejaVu Sans", "size": 82, "primary": "&H0080FF80", "secondary": "&H0080FF80", "outline_c": "&H00FF00FF", "back": "&HA0000000", "bold": -1, "outline": 6, "shadow": 1, "margin_v": 320, "in": "fade", "kf": False},
    "tilt_shadow":  {"name": "Tilt Shadow",  "font": "DejaVu Sans", "size": 88, "primary": "&H00FFFFFF", "secondary": "&H004040FF", "outline_c": "&H00B48200", "back": "&HA0000000", "bold": -1, "outline": 6, "shadow": 8, "margin_v": 300, "angle": -6, "in": "drop", "kf": True},
    "rise":         {"name": "Rise Up",      "font": "DejaVu Sans", "size": 84, "primary": "&H00FFFFFF", "secondary": "&H0000E1FF", "outline_c": "&H00141414", "back": "&H80000000", "bold": -1, "outline": 4, "shadow": 2, "margin_v": 320, "in": "rise", "act": "rise", "kf": False},
    "shake":        {"name": "Beat Shake",   "font": "DejaVu Sans", "size": 92, "primary": "&H00FFFFFF", "secondary": "&H004040FF", "outline_c": "&H00000000", "back": "&HA0000000", "bold": -1, "outline": 6, "shadow": 2, "margin_v": 320, "in": "shake", "act": "shake", "kf": False},
    "bubble":       {"name": "Bubble Pop",   "font": "DejaVu Sans", "size": 72, "primary": "&H00202020", "secondary": "&H00202020", "outline_c": "&H00FFFFFF", "back": "&H00FFFFFF", "bold": -1, "outline": 2, "shadow": 0, "margin_v": 310, "in": "pop", "box": True, "radius": True, "kf": False},
    "hormozi":      {"name": "Hormozi",      "font": "DejaVu Sans", "size": 104, "primary": "&H0000D7FF", "secondary": "&H0000D7FF", "outline_c": "&H00000000", "back": "&HA0000000", "bold": -1, "outline": 1, "shadow": 6, "margin_v": 330, "caps": True, "in": "pop", "kf": False},
    "white_black":  {"name": "White on Black", "font": "DejaVu Sans", "size": 78, "primary": "&H00FFFFFF", "secondary": "&H0000E1FF", "outline_c": "&H00000000", "back": "&HFF000000", "bold": -1, "outline": 2, "shadow": 0, "margin_v": 260, "in": "slide", "kf": True, "box": True},
    "typewriter":   {"name": "Typewriter",   "font": "DejaVu Sans", "size": 74, "primary": "&H00FFFFFF", "secondary": "&H00FFFFFF", "outline_c": "&H00101010", "back": "&H60000000", "bold": 0, "outline": 3, "shadow": 1, "margin_v": 320, "in": "typewriter", "kf": False},
    "drop":         {"name": "Drop In",      "font": "DejaVu Sans", "size": 86, "primary": "&H00FFFFFF", "secondary": "&H00FFD700", "outline_c": "&H00101010", "back": "&H80000000", "bold": -1, "outline": 5, "shadow": 3, "margin_v": 320, "in": "drop", "kf": True},
    "outline_only": {"name": "Outline Only", "font": "DejaVu Sans", "size": 100, "primary": "&H00000000", "secondary": "&H00000000", "outline_c": "&H00FFFFFF", "back": "&H00000000", "bold": -1, "outline": 4, "shadow": 0, "margin_v": 320, "in": "fade", "kf": False},
    "mini_caps":    {"name": "Mini Caps",    "font": "DejaVu Sans", "size": 54, "primary": "&H00FFFFFF", "secondary": "&H00FFFFFF", "outline_c": "&H00000000", "back": "&HA0000000", "bold": 0, "outline": 0, "shadow": 0, "margin_v": 220, "spacing": 6, "in": "fade", "kf": False},
    "epic_cine":    {"name": "Epic Cinematic", "font": "DejaVu Sans", "size": 70, "primary": "&H00D7E7FF", "secondary": "&H00D7E7FF", "outline_c": "&H00402000", "back": "&H50000000", "bold": 0, "outline": 2, "shadow": 4, "margin_v": 210, "spacing": 2, "in": "fade", "kf": False},
    "green_screen": {"name": "Green Pop",    "font": "DejaVu Sans", "size": 88, "primary": "&H0050FF50", "secondary": "&H0050FF50", "outline_c": "&H00003300", "back": "&HA0000000", "bold": -1, "outline": 6, "shadow": 0, "margin_v": 320, "in": "pop", "act": "big", "kf": False},
    "marker":       {"name": "Marker",       "font": "DejaVu Sans", "size": 80, "primary": "&H00101010", "secondary": "&H00101010", "outline_c": "&H0000E1FF", "back": "&H0000E1FF", "bold": -1, "outline": 9, "shadow": 0, "margin_v": 320, "in": "none", "kf": False, "box": True},
    "italic_sleek": {"name": "Italic Sleek", "font": "DejaVu Sans", "size": 74, "primary": "&H00E8E8E8", "secondary": "&H00E8E8E8", "outline_c": "&H00101010", "back": "&H60000000", "bold": 0, "italic": -1, "outline": 3, "shadow": 2, "margin_v": 290, "spacing": 2, "in": "slide", "kf": False},
    "red_bold":     {"name": "Red Alert",    "font": "DejaVu Sans", "size": 96, "primary": "&H004040FF", "secondary": "&H00FFFFFF", "outline_c": "&H00000000", "back": "&HA0000000", "bold": -1, "outline": 7, "shadow": 3, "margin_v": 320, "in": "pop", "kf": True},
}

# quick labels for the settings API (kept tiny; the UI reads all_styles too)
STYLE_NAMES = {k: v.get("name", k) for k, v in STYLE_PRESETS.items() if not v.get("skip")}


def _valid(style: str) -> str:
    return style if style in STYLE_PRESETS and not STYLE_PRESETS[style].get("skip") else DEFAULT_STYLE


def _header(style_name: str, size_scale: float = 1.0, pos: str = "bottom") -> str:
    p = STYLE_PRESETS.get(_valid(style_name))
    border_style = 3 if p.get("box") else 1
    outline = p.get("outline", 5)
    if pos == "top":
        alignment, margin_v = 8, 140
    elif pos == "center":
        alignment, margin_v = 5, 0
    else:
        alignment, margin_v = 2, p.get("margin_v", 320)
    font_size = max(28, int(p["size"] * size_scale))
    italic = p.get("italic", 0)
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{p['font']},{font_size},{p['primary']},{p['secondary']},{p['outline_c']},{p['back']},{p['bold']},{italic},0,0,100,100,{p.get('spacing', 1)},{p.get('angle', 0)},{border_style},{outline},{p.get('shadow', 2)},{alignment},80,80,{margin_v},1
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


def _line_start_tags(style: str) -> str:
    """Per-line entrance animation tags."""
    p = STYLE_PRESETS.get(_valid(style), {})
    mode = p.get("in", "pop")
    if mode == "none":
        return ""
    if mode == "slide":
        return "{\\fad(120,60)\\move(1080,400,540,400,0,140)}"
    if mode == "drop":
        return "{\\fad(60,60)\\move(540,-160,540,400,0,180)\\fscx78\\fscy78\\t(0,180,\\fscx100\\fscy100)}"
    if mode == "rise":
        return "{\\fad(90,60)\\t(0,140,\\y0)}"
    if mode == "shake":
        return "{\\fad(40,40)\\t(0,90,\\fscx118\\fscy118)\\t(90,170,\\fscx100\\fscy100)\\move(546,398,534,402,0,90)}"
    if mode == "typewriter":
        return "{\\fad(0,80)}"
    # pop (default): classic CapCut punch-in
    return "{\\fad(50,40)\\fscx70\\fscy70\\t(0,160,\\fscx112\\fscy112)\\t(160,300,\\fscx100\\fscy100)}"


def _word_tags(style: str, dur_cs: int) -> list[str]:
    """Per-word tag stack for the chosen style."""
    p = STYLE_PRESETS.get(_valid(style), {})
    tags: list[str] = []
    mode = p.get("in", "pop")
    act = p.get("act")
    if p.get("kf") and mode != "typewriter":
        tags.append(f"\\kf{dur_cs}")
    if mode == "typewriter":
        tags.append("\\fad(0,30)")          # words simply appear, one by one
    if act == "big" and mode == "pop":
        tags.append(f"\\t(0,90,\\fscx116\\fscy116)\\t(90,210,\\fscx100\\fscy100)")
    elif act == "rise":
        tags.append("\\t(0,110,\\fy0)\\t(110,240,\\fy-14)")
    elif act == "shake":
        tags.append("\\move(0,0,14,-10,0,70)\\move(14,-10,-12,8,70,160)\\move(-12,8,0,0,160,240)")
    return tags


def build_ass_captions(words: list[dict], clip_start: float, clip_end: float, out_path: str,
                       style: str = DEFAULT_STYLE, watermark: bool = False,
                       pos: str = "bottom", size_scale: float = 1.0, caps: bool | None = None) -> str:
    """Write an animated .ass subtitle file for one clip, in the chosen style.

    style="none" (or the preset being removed) writes an EMPTY file — the
    render paths treat a zero-size .ass as 'no captions'."""
    preset = STYLE_PRESETS.get(style) or {}
    if preset.get("skip"):
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("")
        return out_path
    if caps is None:
        caps = bool(preset.get("caps", True))

    lines = _group_words_into_lines(words, clip_start, clip_end)
    events: list[str] = []
    clip_len = max(0.5, clip_end - clip_start)
    line_tags = _line_start_tags(style)

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

        parts = ([line_tags] if line_tags else [])
        n = len(line_words)
        for i, word in enumerate(line_words):
            if i < n - 1:
                slot = line_words[i + 1]["start"] - word["start"]
            else:
                slot = line_end - word["start"]
            duration_cs = max(1, int(round(slot * 100)))
            raw_word = word["word"].replace("{", "(").replace("}", ")")
            clean = raw_word.upper() if caps else raw_word
            wt = _word_tags(style, duration_cs)
            if wt:
                parts.append("{" + "".join(wt) + "}")
            parts.append(f"{clean} ")

        events.append(
            f"Dialogue: 0,{_timestamp(line_start)},{_timestamp(line_end)},Caption,,0,0,0,,{''.join(parts).strip()}"
        )

    if not events:
        events.append(f"Dialogue: 0,{_timestamp(0)},{_timestamp(max(1.0, clip_len))},Caption,,0,0,0,, ")

    if watermark:
        # Free plan: tiny badge in the corner (ASS layer — works on every ffmpeg build!)
        events.append(f"Dialogue: 0,{_timestamp(0)},{_timestamp(clip_len)},Mark,,0,0,0,,ClipViral")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(_header(style, size_scale=size_scale, pos=pos))
        f.write("\n".join(events))
        f.write("\n")
    return out_path


def captions_are_none(style: str | None) -> bool:
    return not style or str(style) == "none" or bool((STYLE_PRESETS.get(str(style)) or {}).get("skip"))


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
