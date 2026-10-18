"""Script-to-Video (Beta): type a topic/script -> punchy kinetic-typography video.

1. Groq LLM writes/cleans a short punchy script (4-7 lines).
2. Groq TTS (playai-tts) narrates it.
3. FFmpeg builds a vertical video: gradient background + animated text + voice.
"""

import json
import logging
import os

from app.services.ai import chat_model, make_ai_client
from app.services import video_processor

logger = logging.getLogger(__name__)


def _clean_for_drawtext(text: str) -> str:
    return (
        text.replace("\\", "")
        .replace("'", "")
        .replace(":", " -")
        .replace("%", " percent")
        .replace("#", "")
        .strip()[:80]
    )


def script_to_video(script_or_topic: str, workdir: str, style_hint: str = "karaoke") -> dict:
    """Returns {"path": out.mp4, "title": ..., "duration": ...}."""
    os.makedirs(workdir, exist_ok=True)
    client = make_ai_client()

    # 1) Script
    system = (
        "You are a viral short-form scriptwriter. Return ONLY JSON: "
        '{"title": "short title", "lines": ["line 1", "line 2", ...]} '
        "Rules: 4 to 7 SHORT punchy lines (max 8 words each), total speaking time 20-35 seconds, "
        "strong hook in line 1, payoff in the last line. No emojis, no stage directions."
    )
    user_msg = script_or_topic.strip()
    if len(user_msg) < 200 and "?" not in user_msg and "." not in user_msg:
        user_msg = f"Topic: {user_msg}"
    else:
        user_msg = f"Turn this into the script: {user_msg}"

    resp = client.chat.completions.create(
        model=chat_model(),
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
        response_format={"type": "json_object"},
        temperature=0.8,
    )
    data = json.loads(resp.choices[0].message.content or "{}")
    lines = [str(l).strip() for l in (data.get("lines") or []) if str(l).strip()]
    title = str(data.get("title") or "AI Script Video")[:70]
    if not lines:
        raise RuntimeError("The scriptwriter returned an empty script.")

    # 2) TTS narration
    tts_input = ". ".join(lines) + "."
    speech = client.audio.speech.create(
        model="playai-tts",
        voice="Fritz-PlayAI",
        input=tts_input,
    )
    audio_path = os.path.join(workdir, "narration.mp3")
    speech.write_to_file(audio_path) if hasattr(speech, "write_to_file") else open(audio_path, "wb").write(speech.content)

    info = video_processor.probe_video(audio_path)
    total = max(8.0, float(info.get("duration") or 0))

    # 3) per-line timing (proportional to line length)
    weights = [max(2.0, len(l.split())) for l in lines]
    wsum = sum(weights)
    times, cursor = [], 0.0
    for w in weights:
        span = total * w / wsum
        times.append((cursor, cursor + span))
        cursor += span

    # 4) ffmpeg: gradient background + ASS text lines + voice
    def _ts(x: float) -> str:
        h = int(x // 3600); mnt = int((x % 3600) // 60); sc = x % 60
        return f"{h}:{mnt:02d}:{sc:05.2f}"

    ass_events = []
    for line, (a, b) in zip(lines, times):
        txt = _clean_for_drawtext(line).replace("{", "(").replace("}", ")")
        ass_events.append(f"Dialogue: 0,{_ts(a)},{_ts(b)},Line,,0,0,0,,{txt}")
    ass_path = os.path.join(workdir, "script.ass")
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write("""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Line,DejaVu Sans,92,&H00FFFFFF,&H00FFFFFF,&H00201030,&H00000000,-1,0,0,0,100,100,1,0,1,8,3,5,60,60,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""")
        f.write("\n".join(ass_events) + "\n")

    ass_abs = os.path.abspath(ass_path).replace("\\", "/")
    out_path = os.path.join(workdir, "script_video.mp4")
    video_processor._run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", f"gradients=s=1080x1920:c0=1a1040:c1=3b1a6e:d={total:.2f}:speed=0.02",
        "-i", audio_path,
        "-vf", f"ass='{ass_abs}',format=yuv420p",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-threads", "1",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest", "-movflags", "+faststart",
        out_path,
    ])
    return {"path": out_path, "title": title, "duration": total, "lines": lines}
