"""The pipeline worker: turns one long video into viral short clips.

Order of magic tricks:
1. Read the video's length.
2. Whisper writes down everything said in the video (with timestamps).
3. GPT-4o reads that and picks the 3 most viral moments.
4. FFmpeg cuts each moment into a 9:16 clip with animated captions.
5. Clips + thumbnails are uploaded to Supabase Storage; links saved to the database.
"""

import json
import logging
import os
import shutil
import threading
import time
import uuid
from datetime import datetime, timezone

from app.config import settings
from app.services import captions, highlights, storage, transcription, video_processor
from app.supabase_client import get_admin

logger = logging.getLogger(__name__)

# The free machine is tiny (half a CPU!). Jobs run ONE AT A TIME through a
# priority queue — Pro jobs (priority 1) jump ahead of free jobs (priority 5).
import gc
import queue as _queue

_TASKS: "_queue.PriorityQueue" = _queue.PriorityQueue()
_WORKER_STARTED = threading.Event()
_WORKER_GUARD = threading.Lock()
_INFLIGHT: dict[str, float] = {}          # job_id -> last proof-of-life time
_INFLIGHT_LOCK = threading.Lock()
_RECOVER_LOCK = threading.Lock()
_NIGHT_STARTED = threading.Event()


_PROGRESS_TS: dict[str, float] = {}   # job_id -> last time progress/stage actually moved


def update_job(job_id: str, **fields) -> None:
    """Update a job row + touch updated_at (so watchers know it's alive)."""
    _mark_inflight(job_id)  # proof of life: keeps the recover stamp fresh
    if any(k in fields for k in ("progress", "stage", "status")):
        with _INFLIGHT_LOCK:
            _PROGRESS_TS[job_id] = time.time()
    try:
        fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        get_admin().table("jobs").update(fields).eq("id", job_id).execute()
    except Exception:
        logger.exception("Could not update job %s", job_id)


def _mark_inflight(job_id: str) -> None:
    with _INFLIGHT_LOCK:
        _INFLIGHT[job_id] = time.time()


def _unmark_inflight(job_id: str) -> None:
    with _INFLIGHT_LOCK:
        _INFLIGHT.pop(job_id, None)


def _is_pending_in_queue(job_id: str) -> bool:
    try:
        return any(t[2] == job_id for t in _TASKS.queue)
    except Exception:
        return False


def _queue_worker() -> None:
    while True:  # IMMORTAL: any crash just restarts the loop
        try:
            _queue_worker_once()
        except Exception:
            logger.exception("queue worker crashed - restarting")
            time.sleep(5)


def _queue_worker_once() -> None:
    recover_stuck_safe()
    while True:
        try:
            _prio, _seq, job_id, source_path = _TASKS.get(timeout=20)
        except _queue.Empty:
            recover_stuck_safe()  # periodic sweep — nothing is ever stuck forever
            continue
        while not _mem_ok():  # RAM is scary-high: let gc/finish catch up first
            logger.warning("memory guard: RSS %.0f MB — holding next job", _rss_mb())
            time.sleep(10)
        threading.Thread(target=_run_guarded, args=(job_id, source_path), daemon=True).start()


_LAST_SWEEP = [0.0]


def recover_stuck_safe() -> None:
    """Recovery sweep safe to call from anywhere (API, worker, timers).
    Timestamp gate: a hung sweep can never block future ones."""
    now = time.time()
    with _INFLIGHT_LOCK:
        if now - _LAST_SWEEP[0] < 12:
            return
        _LAST_SWEEP[0] = now
    try:
        _recover_stuck()
    except Exception:
        logger.exception("recover sweep failed")


_SWEEPER_STARTED = threading.Event()


def _sweeper_loop() -> None:
    """Independent watchdog thread: sweeps + keeps the worker alive + runs the Self-Doctor."""
    while True:
        try:
            time.sleep(25)
            recover_stuck_safe()
            ensure_worker_started()
            try:
                from app.services.doctor import tick as doctor_tick

                doctor_tick()
            except Exception:
                logger.exception("doctor tick failed")
        except Exception:
            logger.exception("sweeper iteration failed")


def _render_skips(job_id: str) -> bool:
    """True when the phone worker holds a fresh lease on this job."""
    from app.services.lease import has_fresh_lease

    return has_fresh_lease(job_id)


def ensure_worker_started() -> None:
    with _WORKER_GUARD:
        if not _WORKER_STARTED.is_set():
            threading.Thread(target=_queue_worker, daemon=True).start()
            _WORKER_STARTED.set()
        if not _SWEEPER_STARTED.is_set():
            threading.Thread(target=_sweeper_loop, daemon=True).start()
            _SWEEPER_STARTED.set()
        if settings.night_batch and not _NIGHT_STARTED.is_set():
            from app.services import assets as _assets

            threading.Thread(target=_assets.night_loop, daemon=True).start()
            _NIGHT_STARTED.set()


def _recover_stuck() -> None:
    """Re-queue jobs lost to a deploy/restart. Nothing stays queued forever."""
    try:
        res = (
            get_admin()
            .table("jobs")
            .select("*")
            .in_("status", ["queued", "processing"])
            .order("created_at")
            .limit(10)
            .execute()
        )
        rows = res.data or []
    except Exception:
        logger.exception("recover: could not list jobs")
        return

    from app.services.lease import has_fresh_lease

    for row in rows:
        job_id = row.get("id")
        if not job_id:
            continue
        if has_fresh_lease(job_id):
            continue  # phone worker owns it — hands off
        with _INFLIGHT_LOCK:
            last_seen = _INFLIGHT.get(job_id)
            if last_seen is not None and (time.time() - last_seen) < 180:
                continue  # alive right now — leave it alone
            if _is_pending_in_queue(job_id):
                _INFLIGHT[job_id] = time.time()  # waiting its turn, refresh stamp
                continue
            _INFLIGHT[job_id] = time.time()  # reserve before enqueue
        fn = row.get("source_filename") or ""
        url = fn.split("|||", 1)[1].strip() if "|||" in fn else ""
        if url.startswith("http"):
            logger.info("recover: re-queuing link job %s", job_id)
            threading.Thread(target=fetch_and_run, args=(job_id, url), daemon=True).start()
            continue
        local = os.path.join(settings.media_dir, job_id, "source.mp4")
        if os.path.exists(local) or storage.download_file_from_storage(f"{job_id}/source.mp4", local):
            logger.info("recover: re-queuing stored-source job %s", job_id)
            run_pipeline(job_id, local)
            continue
        logger.warning("recover: job %s has no recoverable source - failing it", job_id)
        update_job(
            job_id,
            status="failed",
            stage="failed",
            error="The server restarted before this job started and the video was not stored yet. Please add the video again.",
        )
        _unmark_inflight(job_id)


def recaption_clip(clip_id: str, style: str) -> bool:
    """Re-render one stored clip with a NEW caption style (or style='none'
    to strip captions entirely). Keeps the same storage path, so dashboards,
    share links and downloads all update in place."""
    admin = get_admin()
    try:
        clip = (admin.table("clips").select("*").eq("id", clip_id).limit(1).execute().data or [None])[0]
        if not clip or not clip.get("job_id"):
            return False
        job_id = clip["job_id"]
        job = (admin.table("jobs").select("user_id").eq("id", job_id).limit(1).execute().data or [{}])[0]
        user_id = job.get("user_id")
        prefs = _user_prefs(user_id) if user_id else {}
        is_pro = bool(prefs.get("is_pro"))
        workdir = os.path.join(settings.media_dir, job_id, "recaption")
        os.makedirs(workdir, exist_ok=True)
        source = os.path.join(workdir, "source.mp4")
        if not os.path.exists(source):
            if not storage.download_file_from_storage(f"{job_id}/source.mp4", source):
                logger.warning("recaption %s: source not in storage", clip_id[:8])
                return False
        words_raw: dict = {}
        wp = os.path.join(workdir, "words.json")
        if storage.download_file_from_storage(clip.get("storage_path", "").replace(".mp4", ".words.json"), wp):
            try:
                with open(wp, encoding="utf-8") as fh:
                    words_raw = json.load(fh) or {}
            except Exception:
                words_raw = {}
        kept = [tuple(sx) for sx in words_raw.get("kept_segments") or []]
        words = words_raw.get("words") or []
        dur = float(words_raw.get("clip_duration") or 1.0)
        if not kept:
            kept = [(0.0, max(0.5, dur))]
        remapped = captions.remap_words(words, [(float(a), float(b)) for a, b in kept])
        ass_path = os.path.join(workdir, "recap.ass")
        captions.build_ass_captions(remapped, 0.0, max(1.0, dur), ass_path,
                                    style=style, watermark=not is_pro)
        out_path = os.path.join(workdir, "recap.mp4")
        video_processor.cut_and_concat(source, kept, out_path, video_chain="",
                                       ass_path=ass_path, total_seconds=dur)
        thumb_path = os.path.join(workdir, "recap.jpg")
        thumb_url = ""
        try:
            video_processor.make_thumbnail(out_path, thumb_path)
            thumb_url = storage.upload_file_to_storage(thumb_path, clip["storage_path"].replace(".mp4", ".jpg"))
        except Exception:
            logger.exception("recaption thumbnail failed (non-fatal)")
        video_url = storage.upload_file_to_storage(out_path, clip["storage_path"])
        fields = {"video_url": video_url, "storage_path": clip["storage_path"]}
        if thumb_url:
            fields["thumbnail_url"] = thumb_url
        admin.table("clips").update(fields).eq("id", clip_id).execute()
        logger.info("recaption %s done (style=%s)", clip_id[:8], style)
        return True
    except Exception as exc:
        logger.exception("recaption failed for %s", clip_id[:8])
        try:
            admin.table("clips").update({"error": f"Recaption failed: {str(exc)[:160]}"}).eq("id", clip_id).execute()
        except Exception:
            pass
        return False
    finally:
        try:
            shutil.rmtree(workdir, ignore_errors=True)
        except Exception:
            pass


def url_for_job(job_id: str) -> str:
    rows = (get_admin().table("jobs").select("source_filename").eq("id", job_id)
             .limit(1).execute().data or [{}])
    fn = rows[0].get("source_filename") or ""
    return fn.split("|||", 1)[1].strip() if "|||" in fn else ""


def _user_prefs(user_id: str) -> dict:
    from app.services.captions import FREE_STYLES

    prefs = {"is_pro": False, "caption_style": "karaoke", "sfx": False, "enhance": False, "reframe": "face"}
    try:
        _auth = get_admin().auth
        res = getattr(_auth, "admin", _auth).get_user_by_id(user_id)
        user = getattr(res, "user", res)
        meta = (getattr(user, "user_metadata", None) or {}) if user else {}
        for key in prefs:
            if key in meta:
                prefs[key] = meta[key]
        if prefs["caption_style"] not in FREE_STYLES:
            prefs["caption_style"] = "karaoke"  # unknown style -> safe default (all styles are free)
    except Exception:
        logger.exception("Could not read user prefs (using free defaults)")
    return prefs


def run_pipeline(job_id: str, source_path: str) -> None:
    """Entry point used by the upload route. Pro jobs get priority."""
    ensure_worker_started()
    _mark_inflight(job_id)

    threading.Thread(target=_run_guarded, args=(job_id, source_path), daemon=True).start()


def _cdn_fallback(url: str, workdir: str) -> dict | None:
    """When yt-dlp downloads an empty file (X/Twitter bot-wall) or every player
    disguise gets 'not a bot'-walled (YouTube), resolve the direct CDN mp4 URL
    and download it like a browser would. Returns fetch_video-style dict."""
    try:
        import subprocess
        import urllib.request

        is_youtube = any(h in url for h in ("youtube.com", "youtu.be", "youtube-nocookie.com"))
        cmd = ["yt-dlp", "--no-warnings", "--get-url", "-f", "best[height<=720]/best", url]
        if is_youtube:
            # the android player API is the disguise that most often slips past
            cmd += ["--extractor-args", "youtube:player_client=android"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        links = [ln.strip() for ln in (res.stdout or "").splitlines() if ln.strip().startswith("http")]
        if not links:
            return None
        req = urllib.request.Request(
            links[0],
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
                "Referer": "https://www.youtube.com/" if is_youtube else "https://x.com/",
            },
        )
        data = urllib.request.urlopen(req, timeout=180).read()
        if len(data) < 2048:
            return None
        path = os.path.join(workdir, "source.mp4")
        with open(path, "wb") as fh:
            fh.write(data)
        info = video_processor.probe_video(path)
        return {
            "path": path,
            "title": "YouTube video" if is_youtube else "X video",
            "size": len(data),
            "duration": info.get("duration"),
        }
    except Exception:
        logger.exception("cdn fallback failed")
        return None


def _rss_mb() -> float:
    """Our own RAM use in MB (from /proc — no psutil needed)."""
    try:
        with open("/proc/self/status") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024.0
    except Exception:
        pass
    return 0.0


def _mem_ok() -> bool:
    return _rss_mb() < float(getattr(settings, "max_rss_mb", 430))


def _run_guarded(job_id: str, source_path: str) -> None:
    if _render_skips(job_id):
        logger.info("Job %s leased to the phone worker - render side skipping.", job_id)
        return
    """Run one job in this thread with heartbeat + crash-proofing."""
    _mark_inflight(job_id)
    stop = threading.Event()

    def _beat() -> None:
        while not stop.wait(30):
            _mark_inflight(job_id)  # proof of life during long transcriptions

    threading.Thread(target=_beat, daemon=True).start()
    try:
        _run_pipeline_unserialized(job_id, source_path)
    except Exception as exc:
        logger.exception("Pipeline crashed for job %s", job_id)
        try:
            update_job(job_id, status="failed", stage="failed", error=f"Processing crashed: {str(exc)[:200]}")
        except Exception:
            pass
    finally:
        stop.set()
        _unmark_inflight(job_id)
        gc.collect()
        try:
            import ctypes
            ctypes.CDLL("libc.so.6").malloc_trim(0)   # hand RAM back to the OS
        except Exception:
            pass
        logger.info("job %s done - RSS now %.0f MB", job_id[:8], _rss_mb())


def _run_pipeline_unserialized(job_id: str, source_path: str) -> None:
    """Runs in a background thread after the upload response is sent."""
    workdir = os.path.dirname(source_path)
    _remote = os.path.join(workdir, ".direct.txt")
    _remote_url = ""
    if os.path.exists(_remote):
        try:
            _remote_url = open(_remote).read().strip()
        except Exception:
            _remote_url = ""
        if os.path.basename(source_path).startswith("audio."):
            source_path = _remote_url or source_path   # stream mode: render from CDN
    admin = get_admin()

    try:
        job_res = admin.table("jobs").select("*").eq("id", job_id).limit(1).execute()
        job_rows = job_res.data or []
        user_id = job_rows[0].get("user_id") if job_rows else None
        prefs = _user_prefs(user_id) if user_id else {"is_pro": False, "caption_style": "karaoke", "sfx": False, "enhance": False, "reframe": "face"}
        # ---- OpusClip-parity create options (genre/keywords/aspect/brand/...) ----
        from app.services import parity as _parity

        opts = _parity.load_job_prefs(job_id)
        cap_style = str(opts.get("caption_style") or prefs.get("caption_style") or "karaoke")
        brand_logo_local = ""
        if opts.get("brand_kit_id") and user_id:
            for kit in _parity.list_brand_kits(user_id):
                if kit.get("id") == opts.get("brand_kit_id"):
                    cap_style = str(kit.get("caption_style") or cap_style)
                    logo_url = kit.get("logo_url") or ""
                    if logo_url:
                        try:
                            import urllib.request

                            brand_logo_local = os.path.join(workdir, "brand_logo.img")
                            with open(brand_logo_local, "wb") as fh:
                                fh.write(urllib.request.urlopen(logo_url, timeout=30).read())
                        except Exception:
                            brand_logo_local = ""
                    break
        is_pro = bool(prefs.get("is_pro"))

        # Keep a copy of the SOURCE so the Pro editor can re-render in full quality
        try:
            if os.path.getsize(source_path) <= 250 * 1024 * 1024:
                storage.upload_file_to_storage(source_path, f"{job_id}/source.mp4")
        except Exception:
            logger.exception("source upload failed (not fatal)")

        # ---------- Step 1: measure the video ----------
        if _is_cancelled(job_id):
            logger.info("Job %s was cancelled - stopping.", job_id)
            return
        update_job(job_id, status="processing", stage="measuring_video", progress=5)
        _stored_dur = float(job_rows[0].get("duration_seconds") or 0) if job_rows else 0.0
        if _stored_dur > 1:
            duration, info = _stored_dur, {"duration": _stored_dur, "width": 0, "height": 0}
        else:
            info = video_processor.probe_video(source_path)
            duration = info["duration"]
        update_job(job_id, duration_seconds=duration)
        logger.info("Job %s: video is %.1f seconds long", job_id, duration)

        # ---------- Step 2: Whisper transcription ----------
        update_job(job_id, stage="transcribing_audio", progress=15)
        transcript = transcription.transcribe_video(source_path, workdir)
        if not transcript["segments"]:
            raise RuntimeError("No speech found in the video, so there is nothing to clip.")
        logger.info("Job %s: transcript has %d segments", job_id, len(transcript["segments"]))

        # ---------- Step 3: GPT-4o highlight detection ----------
        update_job(job_id, stage="finding_viral_moments", progress=40)
        # media_path lets HyperFinder run its audio-energy pass (OpusClip's
        # "emotional peaks" signal) — run it on the 16kHz mono audio we already
        # extracted (decodes ~500x realtime; on the video file it would be slow).
        audio_for_energy = os.path.join(workdir, "audio.mp3")
        if not os.path.exists(audio_for_energy):
            audio_for_energy = source_path
        clips = highlights.detect_highlights(transcript, duration, prefs=opts, media_path=audio_for_energy)
        if not clips:
            raise RuntimeError("The AI could not find any good moments to clip.")
        logger.info("Job %s: AI picked %d moments", job_id, len(clips))

        # ---------- Step 4 & 5: cut, caption, upload ----------
        saved_clips = []
        for index, clip in enumerate(clips):
            if _is_cancelled(job_id):
                logger.info("Job %s was cancelled mid-render - stopping.", job_id)
                return
            update_job(
                job_id,
                stage=f"rendering_clip_{index + 1}_of_{len(clips)}",
                progress=42 + 16 * index,
            )

            # Live progress WHILE ffmpeg renders (the bar keeps moving!)
            base_progress = 42 + 16 * index
            last_touch = [0.0]

            def _clip_progress(frac: float, _base=base_progress, _last=last_touch) -> None:
                now = time.time()
                if now - _last[0] < 2.0 and frac < 0.99:
                    return  # don't hammer the database
                _last[0] = now
                update_job(job_id, progress=_base + int(14 * max(0.0, min(1.0, frac))))

            # ---------- NIGHT/LAZY mode: card instantly, encode tonight ----------
            if settings.night_batch and index >= settings.night_copy_first:
                try:
                    _lz_sil = video_processor.silences_from_words(
                        transcript.get("words") or [], clip["start"], clip["end"])
                    if opts.get("remove_fillers"):
                        from app.services import parity as _pz

                        _lz_rng = [
                            {"start": w["start"], "end": w["end"], "word": w.get("word", "")}
                            for w in transcript.get("words") or []
                            if float(w.get("start", 0)) >= clip["start"] - 0.01
                            and float(w.get("end", 0)) <= clip["end"] + 0.01
                        ]
                        _lz_sil = list(_lz_sil) + _pz.find_filler_ranges(_lz_rng)
                    _lz_kept = video_processor.build_kept_segments(
                        clip["start"], clip["end"], _lz_sil)
                    _lz_words = [
                        {"start": round(w["start"], 3), "end": round(w["end"], 3),
                         "word": w.get("word", "")}
                        for w in captions.remap_words(
                            transcript["words"], _lz_kept)
                    ]
                    _lz_cid = str(uuid.uuid4())
                    from app.services import assets as _assets

                    if _assets.queue_night_render(
                            job_id=job_id, clip_id=_lz_cid, user_id=user_id,
                            clip_index=index + 1,
                            payload={
                                "kept": [[round(a, 3), round(b, 3)] for a, b in _lz_kept],
                                "words": _lz_words,
                                "style": cap_style,
                                "reframe": str(prefs.get("reframe") or "face"),
                                "enhance": False, "watermark": not is_pro,
                                "sfx": bool(prefs.get("sfx")) and is_pro,
                                "aspect": str(opts.get("aspect") or "9:16"),
                                "title": clip["title"], "hook": clip["hook"],
                                "score": clip["score"], "hashtags": clip["hashtags"],
                                "start": clip["start"], "end": clip["end"],
                            }):
                        admin.table("clips").insert({
                            "id": _lz_cid, "job_id": job_id, "user_id": user_id,
                            "title": clip["title"], "hook": clip["hook"],
                            "score": clip["score"],
                            "start_seconds": clip["start"],
                            "end_seconds": clip["end"],
                            "video_url": "", "thumbnail_url": "",
                            "storage_path": f"{job_id}/clip_{index + 1}.mp4",
                            "hashtags": clip["hashtags"],
                        }).execute()
                        continue
                except Exception:
                    logger.exception("lazy card failed - full-rendering clip %s now", index + 1)

            clip_id = str(uuid.uuid4())
            ass_path = os.path.join(workdir, f"clip_{index + 1}.ass")
            clip_path = os.path.join(workdir, f"clip_{index + 1}.mp4")
            thumb_path = os.path.join(workdir, f"clip_{index + 1}.jpg")
            words_path = os.path.join(workdir, f"clip_{index + 1}.words.json")

            # ---- AUTOMATIC PAUSE-REMOVAL: dead air gets cut out ----
            # From transcript gaps = instant (an ffmpeg silencedetect pass per clip
            # used to re-decode the video — the biggest hidden slowdown).
            try:
                silences = video_processor.silences_from_words(
                    transcript.get("words") or [], clip["start"], clip["end"])
            except Exception:
                silences = []
            if opts.get("remove_fillers"):
                try:
                    in_range = [
                        {"start": w["start"], "end": w["end"], "word": w.get("word", "")}
                        for w in transcript.get("words") or []
                        if float(w.get("start", 0)) >= clip["start"] - 0.01 and float(w.get("end", 0)) <= clip["end"] + 0.01
                    ]
                    silences = list(silences) + _parity.find_filler_ranges(in_range)
                except Exception:
                    logger.exception("filler detection failed (non-fatal)")
            kept_segments = video_processor.build_kept_segments(clip["start"], clip["end"], silences)

            # Captions follow the NEW pause-free timeline
            remapped = captions.remap_words(transcript["words"], kept_segments)
            kept_len = sum(b - a for a, b in kept_segments)
            captions.build_ass_captions(remapped, 0.0, max(1.0, kept_len), ass_path,
                                        style=cap_style,
                                        watermark=not is_pro)
            if captions.captions_are_none(cap_style):
                open(ass_path, "w").close()  # empty .ass -> nothing burned in

            chain = video_processor.clip_video_chain(
                source_path, clip["start"], clip["end"],
                reframe=str(prefs.get("reframe") or "face"),
                enhance=bool(prefs.get("enhance")) and is_pro,
                watermark=not is_pro,
                aspect=str(opts.get("aspect") or "9:16"),
            )
            video_processor.cut_and_concat(
                source_path, kept_segments, clip_path,
                video_chain=chain, ass_path=ass_path,
                total_seconds=kept_len, on_progress=_clip_progress,
            )
            if brand_logo_local:
                try:
                    _parity.overlay_logo(clip_path, brand_logo_local)
                except Exception:
                    logger.exception("brand logo overlay failed (non-fatal)")

            if is_pro and prefs.get("sfx"):
                try:
                    sfx = video_processor.make_sfx(workdir)
                    starts = captions.line_start_times(remapped)[:12]
                    if starts:
                        paths, times = [], []
                        for i, t in enumerate(starts):
                            paths.append(sfx["whoosh"] if i == 0 else sfx["pop"])
                            times.append(t)
                        video_processor.mix_sfx(clip_path, clip_path + ".sfx.mp4", paths, times)
                        os.replace(clip_path + ".sfx.mp4", clip_path)
                except Exception:
                    logger.exception("Auto SFX failed (not fatal)")

            # Words JSON for the transcript-based editor
            try:
                with open(words_path, "w", encoding="utf-8") as wf:
                    json.dump(
                        {
                            "clip_duration": round(kept_len, 3),
                            "source_start": clip["start"],
                            "source_end": clip["end"],
                            "kept_segments": [[round(a, 3), round(b, 3)] for a, b in kept_segments],
                            "style": str(prefs.get("caption_style") or "karaoke"),
                            "words": [
                                {"start": round(w["start"], 3), "end": round(w["end"], 3), "word": w.get("word", "")}
                                for w in remapped
                            ],
                        },
                        wf,
                    )
            except Exception:
                logger.exception("words json write failed (not fatal)")
            try:
                if source_path.startswith("http"):
                    _aud = next((os.path.join(workdir, f) for f in os.listdir(workdir) if f.startswith("audio.")), source_path)
                    video_processor.make_thumbnail(_aud, thumb_path)
                else:
                    video_processor.make_thumbnail(clip_path, thumb_path)
            except Exception:
                logger.exception("Thumbnail failed (not fatal)")
                thumb_path = ""

            clip_storage_path = f"{job_id}/clip_{index + 1}.mp4"
            video_url = storage.upload_file_to_storage(clip_path, clip_storage_path)
            thumb_url = ""
            if thumb_path and os.path.exists(thumb_path):
                thumb_url = storage.upload_file_to_storage(
                    thumb_path, f"{job_id}/clip_{index + 1}.jpg"
                )
            if os.path.exists(words_path):
                try:
                    storage.upload_file_to_storage(words_path, f"{job_id}/clip_{index + 1}.words.json")
                except Exception:
                    logger.exception("words json upload failed (not fatal)")

            clip_row = {
                "id": clip_id,
                "job_id": job_id,
                "user_id": user_id,
                "title": clip["title"],
                "hook": clip["hook"],
                "score": clip["score"],
                "start_seconds": clip["start"],
                "end_seconds": clip["end"],
                "video_url": video_url,
                "thumbnail_url": thumb_url,
                "storage_path": clip_storage_path,
                "hashtags": clip["hashtags"],
            }
            admin.table("clips").insert(clip_row).execute()
            saved_clips.append(clip_path)

        # ---------- Optional: MoviePy recap reel ----------
        if settings.recap_enabled and len(saved_clips) > 1:
            update_job(job_id, stage="making_recap", progress=92)
            try:
                recap_path = os.path.join(workdir, "recap.mp4")
                video_processor.make_recap_moviepy(saved_clips, recap_path)
                recap_url = storage.upload_file_to_storage(recap_path, f"{job_id}/recap.mp4")
                admin.table("clips").insert(
                    {
                        "id": str(uuid.uuid4()),
                        "job_id": job_id,
                        "user_id": user_id,
                        "title": "All highlights recap",
                        "hook": "Every best moment in one reel",
                        "score": 0,
                        "start_seconds": 0,
                        "end_seconds": 0,
                        "video_url": recap_url,
                        "thumbnail_url": "",
                        "storage_path": f"{job_id}/recap.mp4",
                        "hashtags": ["#recap"],
                    }
                ).execute()
            except Exception:
                logger.exception("Recap render failed (not fatal)")

        update_job(job_id, status="completed", stage="done", progress=100, error=None)
        # OpusClip parity: conclusionActions-style webhook
        try:
            if opts.get("webhook_url"):
                _parity.fire_webhook(str(opts.get("webhook_url")), {
                    "event": "job.completed",
                    "job_id": job_id,
                    "clips": len(saved_clips),
                    "title": str((job_rows[0].get("source_filename") if job_rows else "") or "")[:120],
                })
        except Exception:
            logger.exception("webhook failed (non-fatal)")

        # Janitor: keep only the newest 4 videos per account, auto-delete older ones
        try:
            from app.services.janitor import cleanup_old_jobs
            if user_id:
                cleanup_old_jobs(user_id)
        except Exception:
            logger.exception("Janitor failed (not fatal)")
        logger.info("Job %s completed with %d clips", job_id, len(saved_clips))

    except Exception as exc:
        logger.exception("Job %s failed", job_id)
        update_job(job_id, status="failed", stage="failed", error=str(exc)[:1000])

    finally:
        # Free disk space: delete the working folder (clips are already in Supabase).
        shutil.rmtree(workdir, ignore_errors=True)


def fetch_and_run(job_id: str, url: str) -> None:
    if _render_skips(job_id):
        logger.info("Job %s leased to the phone worker - render side skipping.", job_id)
        return
    """Background task: fetch the video from the link, then run the normal pipeline.

    A heartbeat keeps the inflight stamp FRESH for the whole fetch (multi-minute
    retries included) — so a recovery sweep can never mistake this run for a
    dead one and double-spawn it (double-spawn = one run deletes the other's
    source file mid-flight; that bit us on 2026-10-17).
    """
    _mark_inflight(job_id)
    _fetch_stop = threading.Event()

    def _fetch_beat() -> None:
        while not _fetch_stop.wait(20):
            _mark_inflight(job_id)

    _hb = threading.Thread(target=_fetch_beat, daemon=True)
    _hb.start()
    try:
        _fetch_and_run_inner(job_id, url)
    except Exception as exc:
        logger.exception("fetch_and_run crashed for job %s", job_id)
        try:
            update_job(job_id, status="failed", stage="failed", error=f"Could not process that link: {str(exc)[:220]}")
        except Exception:
            pass
    finally:
        _fetch_stop.set()
        _unmark_inflight(job_id)


def _fetch_and_run_inner(job_id: str, url: str) -> None:
    from app.services import link_fetcher

    workdir = os.path.join(settings.media_dir, job_id)
    os.makedirs(workdir, exist_ok=True)

    def on_progress(percent: int) -> None:
        update_job(job_id, stage="fetching_link", progress=max(2, min(20, 2 + percent // 6)))

    try:
        if _is_cancelled(job_id):
            logger.info("Job %s was cancelled - stopping.", job_id)
            return
        update_job(job_id, status="processing", stage="fetching_link", progress=2)

        # ---- STREAM-FIRST: audio-only for Whisper + direct CDN URL for clips.
        # No full-video download => no hour-long "fetching" on the free box.
        audio = None
        _aexc: Exception | None = None
        for attempt in range(2):
            try:
                audio = link_fetcher.stream_audio(url, workdir, on_progress=on_progress)
                break
            except Exception as exc:
                _aexc = exc
                update_job(job_id, stage="fetching_link", progress=max(2, 8 * (attempt + 1)))
                time.sleep(2)
        if audio:
            try:
                direct = link_fetcher.resolve_direct_url(url)
            except Exception:
                direct = ""
            with open(os.path.join(workdir, ".direct.txt"), "w") as fh:
                fh.write(direct or "")          # empty = stream-mode, no 720p url
            update_job(job_id, stage="link_fetched", progress=22,
                       source_filename=f"{audio['title']}|||{url}",
                       source_size_bytes=audio["size"],
                       duration_seconds=audio.get("duration") or 0)
            logger.info("Job %s: STREAM mode (audio %.1f MB, direct=%s)",
                        job_id, audio["size"] / 1e6, bool(direct))
            run_pipeline(job_id, audio["path"])
            return
        if _aexc:
            logger.info("stream mode failed (%s) -> full download", str(_aexc)[:120])
        update_job(job_id, stage="downloading_full", progress=3)
        # X/YouTube CDNs flake sometimes — ALWAYS retry before giving up.
        result = None
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                cand = link_fetcher.fetch_video(url, workdir, on_progress=on_progress)
                if cand and float(cand.get("size") or 0) > 2048:
                    result = cand
                    break
                last_exc = RuntimeError("The downloaded file is empty (site hiccup)")
                update_job(job_id, stage="fetching_link", progress=max(2, 6 * (attempt + 1)))
            except Exception as exc:
                last_exc = exc
                update_job(job_id, stage="fetching_link", progress=max(2, 6 * (attempt + 1)))
            if result is None:
                alt = _cdn_fallback(url, workdir)  # browser-style direct download
                if alt:
                    result = alt
                    break
            time.sleep(3 * (attempt + 1))
        if result is None:
            raise last_exc or RuntimeError("Could not fetch that video link")
        fields = {
            "stage": "link_fetched",
            "progress": 22,
            "source_filename": f"{result['title']}|||{url}",
            "source_size_bytes": result["size"],
        }
        if result.get("duration"):
            fields["duration_seconds"] = result["duration"]
        update_job(job_id, **fields)
        logger.info("Job %s: fetched link video %r (%.1f MB)", job_id, result["title"], result["size"] / 1024 / 1024)
    except Exception as exc:
        logger.exception("Link fetch failed for job %s", job_id)
        update_job(
            job_id,
            status="failed",
            stage="failed",
            error=f"Could not fetch that video link: {str(exc)}",  # FULL text — debug digest lives at the end
        )
        shutil.rmtree(workdir, ignore_errors=True)
        return

    # We are ALREADY on a background thread — run the pipeline right here
    # (a thread-hop would let the inflight claim lapse mid-handoff and a
    # second recover could double-run the job).
    try:
        _run_guarded(job_id, result["path"])
    except Exception:
        shutil.rmtree(workdir, ignore_errors=True)
        raise


def _is_cancelled(job_id: str) -> bool:
    """True if the user cancelled this job."""
    try:
        row = get_admin().table("jobs").select("status").eq("id", job_id).limit(1).execute().data
        return bool(row and row[0].get("status") == "cancelled")
    except Exception:
        return False
