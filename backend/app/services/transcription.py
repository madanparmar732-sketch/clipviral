"""Whisper transcription: turns the video's speech into text with timestamps."""

import json
import logging
import os
import subprocess

from app.config import settings
from app.services.ai import make_ai_client, whisper_model

logger = logging.getLogger(__name__)

WHISPER_MAX_BYTES = 22 * 1024 * 1024  # keep safely under the API's 25 MB limit


def _run(command: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(command, capture_output=True, text=True, timeout=900)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(command)}\n{result.stderr[-2000:]}")
    return result


def probe_duration(path: str) -> float:
    result = _run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            path,
        ]
    )
    data = json.loads(result.stdout or "{}")
    try:
        return float(data.get("format", {}).get("duration", 0.0))
    except (TypeError, ValueError):
        return 0.0


def extract_audio(video_path: str, out_path: str) -> str:
    """Rip the sound out of the video (small file, easy to send to Whisper)."""
    _run(
        [
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k",
            out_path,
        ]
    )
    return out_path


def _split_audio(audio_path: str, workdir: str, chunk_seconds: int = 900) -> list[tuple[float, str]]:
    """
    If the audio is too big for one Whisper request, cut it into pieces.
    Returns a list of (start_time_of_piece, path_to_piece).
    """
    if os.path.getsize(audio_path) <= WHISPER_MAX_BYTES:
        return [(0.0, audio_path)]

    pattern = os.path.join(workdir, "audio_chunk_%03d.mp3")
    _run(
        [
            "ffmpeg", "-y", "-i", audio_path,
            "-f", "segment", "-segment_time", str(chunk_seconds),
            "-c", "copy",
            pattern,
        ]
    )
    chunks: list[tuple[float, str]] = []
    offset = 0.0
    index = 0
    while True:
        chunk_path = os.path.join(workdir, f"audio_chunk_{index:03d}.mp3")
        if not os.path.exists(chunk_path):
            break
        chunks.append((offset, chunk_path))
        offset += probe_duration(chunk_path)
        index += 1
    return chunks


def _to_dict(obj) -> dict:
    """Turn OpenAI response objects into plain dictionaries."""
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, list):
        return {"items": obj}
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return dict(obj.__dict__) if hasattr(obj, "__dict__") else {}


def transcribe_video(video_path: str, workdir: str) -> dict:
    """
    Returns:
      {
        "text":     full transcript,
        "segments": [{"start": s, "end": e, "text": "..."}],
        "words":    [{"start": s, "end": e, "word": "..."}],
      }
    """
    logger.info("Extracting audio for Whisper...")
    audio_path = os.path.join(workdir, "audio.mp3")
    if os.path.basename(video_path).startswith("audio.") and video_path != audio_path:
        import shutil
        shutil.move(video_path, audio_path)   # already audio (stream-first mode) — no re-encode
    else:
        extract_audio(video_path, audio_path)

    chunks = _split_audio(audio_path, workdir)
    logger.info("Transcribing %d audio chunk(s)...", len(chunks))

    client = make_ai_client()

    # ---- transcribe ALL chunks in parallel (3 workers) — OpusClip-style concurrency ----
    def _one_chunk(chunk_path: str) -> dict:
        last_exc: Exception | None = None
        for _try in range(2):
            try:
                with open(chunk_path, "rb") as audio_file:
                    response = client.audio.transcriptions.create(
                        model=whisper_model(),
                        file=audio_file,
                        response_format="verbose_json",
                        timestamp_granularities=["word", "segment"],
                    )
                return _to_dict(response)
            except Exception as exc:  # transient API hiccups shouldn't kill the job
                last_exc = exc
        raise last_exc  # type: ignore[misc]

    results: list[dict] = [{}] * len(chunks)
    if len(chunks) == 1:
        results[0] = _one_chunk(chunks[0][1])
    else:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=min(3, len(chunks))) as pool:
            futures = {pool.submit(_one_chunk, cp): i for i, (_cs, cp) in enumerate(chunks)}
            for fut, i in futures.items():
                results[i] = fut.result()

    texts: list[str] = []
    segments: list[dict] = []
    words: list[dict] = []
    offset = 0.0

    for (chunk_start, chunk_path), data in zip(chunks, results):

        texts.append(data.get("text", "") or "")
        for seg in data.get("segments") or []:
            segments.append(
                {
                    "start": offset + float(seg.get("start", 0) or 0),
                    "end": offset + float(seg.get("end", 0) or 0),
                    "text": (seg.get("text") or "").strip(),
                }
            )
        for word in data.get("words") or []:
            word_text = (word.get("word") or word.get("text") or "").strip()
            if not word_text:
                continue
            words.append(
                {
                    "start": offset + float(word.get("start", 0) or 0),
                    "end": offset + float(word.get("end", 0) or 0),
                    "word": word_text,
                }
            )

        offset += probe_duration(chunk_path)

    # Fallback: if Whisper didn't give word timestamps, invent them from segments
    # so captions still work (each word gets an equal slice of the segment time).
    if not words and segments:
        for seg in segments:
            seg_words = seg["text"].split()
            seg_len = max(seg["end"] - seg["start"], 0.01)
            step = seg_len / max(len(seg_words), 1)
            cursor = seg["start"]
            for w in seg_words:
                words.append({"start": cursor, "end": cursor + step, "word": w})
                cursor += step

    return {
        "text": " ".join(t.strip() for t in texts if t).strip(),
        "segments": segments,
        "words": words,
    }
