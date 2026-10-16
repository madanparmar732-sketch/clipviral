"""THE SELF-DOCTOR — the platform watches and heals itself.

Every few minutes it checks every working part (ffmpeg, AI, storage, database,
the job worker). If anything is broken it:
  1. tries to FIX it automatically (restart worker, unstick jobs, clear leaks),
  2. writes a report to storage (health/status.json) so anyone can see it,
  3. puts a red "⚠️ System check" card on the dashboard with the exact error.

No permission needed. It just does it.
"""

import json
import logging
import os
import subprocess
import time

from app.config import settings

logger = logging.getLogger(__name__)

STATUS_KEY = "health/status.json"
_LAST = {"quick": 0.0, "deep": 0.0}
_STUCK: dict[str, int] = {}
_LAST_INCIDENT = {"hash": ""}


# ---------------------------------------------------------------- helpers
def _run(cmd: list[str], timeout: int = 60) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-300:] or "command failed")


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------- auto-fix
def auto_fixes() -> list[str]:
    """Heal anything healable. Returns a list of what it fixed."""
    fixes: list[str] = []
    from app.supabase_client import get_admin

    admin = get_admin()

    # 1) worker + sweeper must be alive
    try:
        from app.workers import pipeline as pl

        if not pl._WORKER_STARTED.is_set() or time.time() - pl._LAST_SWEEP[0] > 300:
            pl.ensure_worker_started()
            fixes.append("restarted job worker")
    except Exception:
        logger.exception("auto-fix: worker")

    # 2) stuck jobs -> recovery sweep
    try:
        from app.workers.pipeline import recover_stuck_safe

        recover_stuck_safe()
    except Exception:
        logger.exception("auto-fix: recover")

    # 3) stale inflight marks (leaks) -> clear
    try:
        from app.workers import pipeline as pl

        with pl._INFLIGHT_LOCK:
            dead = [k for k, ts in pl._INFLIGHT.items() if time.time() - ts > 900]
            for k in dead:
                pl._INFLIGHT.pop(k, None)
        if dead:
            fixes.append(f"cleared {len(dead)} leaked job lock(s)")
    except Exception:
        logger.exception("auto-fix: inflight")

    # 4) editor render rows stuck in 'processing' for > 20 min -> mark failed
    try:
        cutoff = _now_iso()
        rows = (
            admin.table("jobs")
            .select("id,source_filename,updated_at,created_at")
            .eq("status", "processing")
            .limit(30)
            .execute()
            .data
            or []
        )
        from datetime import datetime, timedelta, timezone

        limit = datetime.now(timezone.utc) - timedelta(minutes=20)
        for r in rows:
            name = str(r.get("source_filename") or "")
            if not (name.startswith("Editor render") or name.startswith("Re-cut")):
                continue
            stamp = r.get("updated_at") or r.get("created_at") or ""
            try:
                when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            except Exception:
                continue
            if when < limit:
                admin.table("jobs").update(
                    {"status": "failed", "stage": "failed", "error": "Render timed out automatically — please try again.", "updated_at": cutoff}
                ).eq("id", r["id"]).execute()
                fixes.append("timed out a stuck editor render")
    except Exception:
        logger.exception("auto-fix: editor rows")

    # 5) FROZEN jobs (no progress for 6+ min) -> auto-retry, then fail cleanly
    try:
        from app.workers import pipeline as pl

        rows = (
            admin.table("jobs")
            .select("id,stage,source_filename")
            .in_("status", ["queued", "processing"])
            .limit(20)
            .execute()
            .data
            or []
        )
        for r in rows:
            jid = r.get("id")
            name = str(r.get("source_filename") or "")
            if not jid or name.startswith("⚠️ System check"):
                continue
            with pl._INFLIGHT_LOCK:
                ts = pl._PROGRESS_TS.get(jid)
            if not ts or time.time() - ts < 360:
                continue
            count = _STUCK.get(jid, 0) + 1
            _STUCK[jid] = count
            with pl._INFLIGHT_LOCK:
                pl._PROGRESS_TS.pop(jid, None)
                pl._INFLIGHT.pop(jid, None)
            if count <= 1:
                admin.table("jobs").update(
                    {"status": "queued", "stage": "queued", "progress": 0, "error": "", "updated_at": _now_iso()}
                ).eq("id", jid).execute()
                fixes.append(f"auto-retried a frozen job ({name[:30]})")
            else:
                admin.table("jobs").update(
                    {
                        "status": "failed",
                        "stage": "failed",
                        "error": "Rendering hung twice on this video - the clip may be corrupt. Try a different video or retry later.",
                        "updated_at": _now_iso(),
                    }
                ).eq("id", jid).execute()
                fixes.append(f"failed a double-frozen job ({name[:30]})")
    except Exception:
        logger.exception("auto-fix: frozen jobs")

    # 6) old doctor cards (> 48h) -> delete
    try:
        rows = (
            admin.table("jobs")
            .select("id,source_filename,created_at")
            .eq("status", "failed")
            .limit(50)
            .execute()
            .data
            or []
        )
        from datetime import datetime, timedelta, timezone

        limit = datetime.now(timezone.utc) - timedelta(hours=48)
        for r in rows:
            if not str(r.get("source_filename") or "").startswith("⚠️ System check"):
                continue
            try:
                when = datetime.fromisoformat(str(r.get("created_at")).replace("Z", "+00:00"))
            except Exception:
                continue
            if when < limit:
                admin.table("jobs").delete().eq("id", r["id"]).execute()
    except Exception:
        logger.exception("auto-fix: doctor rows")

    return fixes


# ---------------------------------------------------------------- checks
def quick_checks() -> dict:
    """Fast health probes — every working part, no heavy lifting."""
    from app.supabase_client import get_admin

    out: dict = {}

    # ffmpeg / ffprobe present
    for tool in ("ffmpeg", "ffprobe"):
        try:
            _run([tool, "-version"], timeout=15)
            out[tool] = "ok"
        except Exception as exc:
            out[tool] = f"FAIL: {str(exc)[:120]}"

    # YouTube PO-token provider (bgutil server on :4416) — the bot-wall breaker
    try:
        import json as _json
        import urllib.request as _ur

        req = _ur.Request(
            "http://127.0.0.1:4416/get_pot",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = _json.loads(_ur.urlopen(req, timeout=25).read().decode())
        out["yt_pot"] = "ok" if resp.get("poToken") else "FAIL: no poToken in response"
    except Exception as exc:
        out["yt_pot"] = f"FAIL: {str(exc)[:120]}"

    # database
    try:
        get_admin().table("jobs").select("id").limit(1).execute()
        out["database"] = "ok"
    except Exception as exc:
        out["database"] = f"FAIL: {str(exc)[:120]}"

    # storage round-trip
    try:
        bucket = get_admin().storage.from_(settings.clips_bucket)
        probe = f"health/probe-{int(time.time())}.txt"
        bucket.upload(probe, b"ok", {"content-type": "text/plain"})
        data = bucket.download(probe)
        bucket.remove([probe])
        out["storage"] = "ok" if data else "FAIL: empty read"
    except Exception as exc:
        out["storage"] = f"FAIL: {str(exc)[:120]}"

    # job worker alive
    try:
        from app.workers import pipeline as pl

        if pl._WORKER_STARTED.is_set() and time.time() - pl._LAST_SWEEP[0] < 420:
            out["job_worker"] = "ok"
        else:
            out["job_worker"] = "FAIL: worker/sweeper silent"
    except Exception as exc:
        out["job_worker"] = f"FAIL: {str(exc)[:120]}"

    # recent job failures = THE thing users care about most
    try:
        from datetime import datetime, timedelta, timezone

        rows = (
            get_admin()
            .table("jobs")
            .select("id,source_filename,error,created_at")
            .eq("status", "failed")
            .limit(10)
            .execute()
            .data
            or []
        )
        limit = datetime.now(timezone.utc) - timedelta(minutes=45)
        recent = []
        for r in rows:
            name = str(r.get("source_filename") or "")
            if name.startswith("⚠️ System check"):
                continue
            try:
                when = datetime.fromisoformat(str(r.get("created_at")).replace("Z", "+00:00"))
            except Exception:
                continue
            if when >= limit:
                recent.append(f"{name[:30]}: {str(r.get('error') or '')[:80]}")
        out["job_failures"] = "ok" if not recent else "FAIL: " + " | ".join(recent[:2])
    except Exception as exc:
        out["job_failures"] = f"FAIL: watcher error {str(exc)[:100]}"

    # AI brain (Groq) — one tiny word
    try:
        from app.services.ai import chat_model, make_ai_client

        client = make_ai_client()
        client.chat.completions.create(
            model=chat_model(),
            messages=[{"role": "user", "content": "Reply with the single word: ok"}],
            max_tokens=4,
        )
        out["ai_groq"] = "ok"
    except Exception as exc:
        out["ai_groq"] = f"FAIL: {str(exc)[:120]}"

    return out


def deep_canary() -> dict:
    """Full render-path test: synthetic video -> captions -> ffmpeg render -> probe.
    Only runs when no real job is processing (never steals CPU from users)."""
    from app.supabase_client import get_admin

    try:
        busy = (
            get_admin().table("jobs").select("id").eq("status", "processing").limit(1).execute().data or []
        )
        if busy:
            return {"render_pipeline": "skipped (busy)"}
    except Exception:
        pass

    workdir = os.path.join(settings.media_dir, "health-canary")
    os.makedirs(workdir, exist_ok=True)
    try:
        from app.services import video_processor
        from app.services.captions import build_ass_captions

        src = os.path.join(workdir, "c.mp4")
        out = os.path.join(workdir, "o.mp4")
        ass = os.path.join(workdir, "c.ass")
        _run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=navy:s=720x1280:d=4",
             "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
             "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", src],
            timeout=120,
        )
        words = [{"start": 0.5, "end": 1.0, "word": "system"}, {"start": 1.2, "end": 1.7, "word": "check"}]
        build_ass_captions(words, 0.0, 4.0, ass, style="beast", watermark=False)
        chain = video_processor.clip_video_chain(src, 0, 4, aspect="9:16")
        video_processor.cut_and_concat(src, [(0, 4)], out, video_chain=chain, ass_path=ass)
        info = video_processor.probe_video(out)
        w, h = int(info.get("width") or 0), int(info.get("height") or 0)
        result = {"render_pipeline": "ok" if (w, h) == (720, 1280) else f"FAIL: output is {w}x{h}, expected 720x1280"}
        # --- code-path canary: run the REAL highlight picker on a fake transcript ---
        try:
            from app.services.highlights import detect_highlights

            fake = {
                "segments": [
                    {"start": 0.0, "end": 2.0, "text": "I never thought this would happen."},
                    {"start": 2.0, "end": 4.5, "text": "But then everything changed in one day."},
                    {"start": 4.5, "end": 8.0, "text": "And honestly, I would do it all again."},
                ]
            }
            picks = detect_highlights(fake, 8.0, n=2)
            result["ai_pipeline"] = "ok" if picks else "FAIL: no clips picked"
            for c in picks:
                if c["end"] <= c["start"]:
                    result["ai_pipeline"] = "FAIL: invalid clip window"
                    break
        except Exception as exc:
            result["ai_pipeline"] = f"FAIL: {str(exc)[:160]}"
        return result
    except Exception as exc:
        return {"render_pipeline": f"FAIL: {str(exc)[:160]}"}
    finally:
        import shutil

        shutil.rmtree(workdir, ignore_errors=True)


# ---------------------------------------------------------------- report
def _report(checks: dict, fixes: list[str]) -> None:
    from app.supabase_client import get_admin

    admin = get_admin()
    bad = {k: v for k, v in checks.items() if isinstance(v, str) and v.startswith("FAIL")}
    status = {"time": _now_iso(), "ok": not bad, "checks": checks, "fixes": fixes}

    # 1) write the public status file
    try:
        admin.storage.from_(settings.clips_bucket).upload(
            STATUS_KEY, json.dumps(status).encode("utf-8"), {"content-type": "application/json"}
        )
    except Exception:
        logger.exception("doctor: could not write status file")

    # 2) dashboard card — AT MOST ONE ever; removed when healthy again
    try:
        existing = (
            admin.table("jobs")
            .select("id")
            .like("source_filename", "⚠️ System check%")
            .limit(5)
            .execute()
            .data
            or []
        )
        if bad:
            if not existing:
                admin.table("jobs").insert(
                    {
                        "user_id": None,
                        "status": "failed",
                        "stage": "failed",
                        "source_filename": f"⚠️ System check: {', '.join(sorted(bad))}"[:80],
                        "source_size_bytes": 0,
                        "error": "; ".join(f"{k}: {v}" for k, v in bad.items())[:220],
                    }
                ).execute()
            else:
                # update the ONE card instead of creating more
                admin.table("jobs").update(
                    {
                        "source_filename": f"⚠️ System check: {', '.join(sorted(bad))}"[:80],
                        "error": "; ".join(f"{k}: {v}" for k, v in bad.items())[:220],
                    }
                ).eq("id", existing[0]["id"]).execute()
        else:
            for r in existing:
                admin.table("jobs").delete().eq("id", r["id"]).execute()
    except Exception:
        logger.exception("doctor: incident card")


def tick(force: bool = False) -> dict | None:
    """Called by the sweeper. Quick checks every 5 min, deep render canary hourly."""
    now = time.time()
    do_quick = force or now - _LAST["quick"] > 300
    do_deep = force or now - _LAST["deep"] > 3600
    if not do_quick and not do_deep:
        return None

    fixes = auto_fixes()
    checks: dict = {}
    if do_quick:
        _LAST["quick"] = now
        checks.update(quick_checks())
    if do_deep:
        _LAST["deep"] = now
        checks.update(deep_canary())
    _report(checks, fixes)
    return {"checks": checks, "fixes": fixes}
