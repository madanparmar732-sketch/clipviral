"""Phone-worker leases — lets a Termux worker on the user's own phone take
over video rendering without ever double-running with the Render box.

Schema (run once in Supabase SQL editor, see supabase/phone_worker.sql):
  jobs.lease_owner     text
  jobs.lease_heartbeat timestamptz

Rules:
  * phone claims  -> lease_owner='phone', heartbeat=now  (atomic .eq swap)
  * render skips any job whose lease is fresh while settings.phone_worker=1
  * heartbeat goes stale (30 min)  -> the job is fair game again (phone died)
All functions fail OPEN: if the columns don't exist yet, everything returns
"no lease" so the normal Render worker path keeps working untouched.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

PHONE = "phone"
LEASE_FRESH_MINUTES = 30


def _fresh(row_heartbeat: str | None) -> bool:
    if not row_heartbeat:
        return False
    try:
        ts = datetime.fromisoformat(row_heartbeat.replace("Z", "+00:00"))
    except ValueError:
        return False
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts > datetime.now(timezone.utc) - timedelta(minutes=LEASE_FRESH_MINUTES)


def has_fresh_lease(job_id: str) -> bool:
    """Render side: should I LEAVE this job alone because the phone owns it?"""
    try:
        from app.config import settings

        if not getattr(settings, "phone_worker", False):
            return False
        from app.supabase_client import get_admin

        res = (
            get_admin()
            .table("jobs")
            .select("lease_owner,lease_heartbeat")
            .eq("id", job_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            return False
        row = rows[0]
        return row.get("lease_owner") == PHONE and _fresh(row.get("lease_heartbeat"))
    except Exception:
        return False  # columns missing / transient — behave like before this feature


# ---------------------------------------------------------------- phone side

def claim_any() -> str | None:
    """Atomically grab the oldest queued job nobody owns yet."""
    from app.supabase_client import get_admin

    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=LEASE_FRESH_MINUTES)).isoformat()
    try:
        res = (
            get_admin()
            .table("jobs")
            .select("id")
            .eq("status", "queued")
            .or_(f"lease_owner.is.null,lease_owner.neq.{PHONE},lease_heartbeat.lt.{cutoff}")
            .order("created_at")
            .limit(1)
            .execute()
        )
        rows = res.data or []
    except Exception as exc:
        logger.error("lease claim query failed: %s", exc)
        return None
    for row in rows:
        job_id = row.get("id")
        if not job_id:
            continue
        # compare-and-swap: only wins if nobody grabbed it in the last few ms
        upd = (
            get_admin()
            .table("jobs")
            .update({"lease_owner": PHONE, "lease_heartbeat": datetime.now(timezone.utc).isoformat()})
            .eq("id", job_id)
            .or_(f"lease_owner.is.null,lease_owner.neq.{PHONE},lease_heartbeat.lt.{cutoff}")
            .execute()
        )
        if upd.data:
            return job_id
    return None


def claim_orphan_processing() -> str | None:
    """Adopt a Render job that died mid-run (processing, stale heartbeat)."""
    from app.supabase_client import get_admin

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    try:
        res = (
            get_admin()
            .table("jobs")
            .select("id")
            .eq("status", "processing")
            .or_(f"lease_owner.is.null,lease_owner.neq.{PHONE}")
            .lt("updated_at", cutoff)
            .order("updated_at")
            .limit(1)
            .execute()
        )
        rows = res.data or []
    except Exception:
        return None
    for row in rows:
        job_id = row.get("id")
        if not job_id:
            continue
        upd = (
            get_admin()
            .table("jobs")
            .update({"lease_owner": PHONE, "lease_heartbeat": datetime.now(timezone.utc).isoformat(),
                     "status": "queued", "stage": "queued", "progress": 1})
            .eq("id", job_id)
            .execute()
        )
        if upd.data:
            return job_id
    return None


def heartbeat(job_id: str) -> None:
    from app.supabase_client import get_admin

    try:
        (
            get_admin()
            .table("jobs")
            .update({"lease_heartbeat": datetime.now(timezone.utc).isoformat()})
            .eq("id", job_id)
            .eq("lease_owner", PHONE)
            .execute()
        )
    except Exception:
        pass  # heartbeat must never kill a live render


def release(job_id: str) -> None:
    from app.supabase_client import get_admin

    try:
        get_admin().table("jobs").update({"lease_owner": None}).eq("id", job_id).eq("lease_owner", PHONE).execute()
    except Exception:
        pass
