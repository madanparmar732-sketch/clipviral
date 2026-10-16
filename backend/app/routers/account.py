"""Account: Free vs Pro plan, preferences, and Pro code redemption.

The plan lives in Supabase auth user_metadata (NO extra tables needed):
  {is_pro: bool, caption_style, sfx, enhance, reframe, dub}
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import get_current_user
from app.config import settings
from app.services.captions import FREE_STYLES, STYLE_PRESETS
from app.supabase_client import get_admin

router = APIRouter()


def _admin_auth():
    """Supabase admin API — lives under auth.admin in newer clients."""
    auth = get_admin().auth
    return getattr(auth, "admin", auth)


def read_prefs(user) -> dict:
    meta = getattr(user, "user_metadata", None) or {}
    return {
        "is_pro": bool(meta.get("is_pro", False)),
        "caption_style": str(meta.get("caption_style") or "beast"),
        "sfx": bool(meta.get("sfx", False)),
        "enhance": bool(meta.get("enhance", False)),
        "reframe": str(meta.get("reframe") or "face"),
        "dub": str(meta.get("dub") or "off"),
    }


@router.get("/api/account")
def get_account(user=Depends(get_current_user)):
    prefs = read_prefs(user)
    # videos used this calendar month
    from datetime import datetime, timezone

    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    res = (
        get_admin()
        .table("jobs")
        .select("id", count="exact")
        .eq("user_id", user.id)
        .gte("created_at", month_start)
        .execute()
    )
    used = res.count if getattr(res, "count", None) is not None else len(res.data or [])
    limit = None  # everything is FREE now; Pro = no ads + speed boost only
    return {
        "email": getattr(user, "email", ""),
        "plan": "pro" if prefs["is_pro"] else "free",
        "videos_used_this_month": used,
        "videos_limit": limit,
        "caption_style": prefs["caption_style"],
        "sfx": prefs["sfx"],
        "enhance": prefs["enhance"],
        "reframe": prefs["reframe"],
        "dub": prefs["dub"],
        "free_styles": list(STYLE_PRESETS.keys()),
        "all_styles": list(STYLE_PRESETS.keys()),
    }


class PrefsRequest(BaseModel):
    caption_style: str | None = None
    sfx: bool | None = None
    enhance: bool | None = None
    reframe: str | None = None
    dub: str | None = None


@router.post("/api/account/prefs")
def save_prefs(payload: PrefsRequest, user=Depends(get_current_user)):
    current = read_prefs(user)
    meta = dict(getattr(user, "user_metadata", None) or {})
    is_pro = current["is_pro"]

    if payload.caption_style is not None:
        meta["caption_style"] = payload.caption_style if payload.caption_style in STYLE_PRESETS else "beast"
    if payload.sfx is not None:
        meta["sfx"] = payload.sfx
    if payload.enhance is not None:
        meta["enhance"] = payload.enhance
    if payload.reframe is not None and payload.reframe in ("face", "center"):
        meta["reframe"] = payload.reframe
    if payload.dub is not None:
        meta["dub"] = payload.dub

    _admin_auth().update_user_by_id(user.id, {"user_metadata": meta})
    return {"ok": True}


class RedeemRequest(BaseModel):
    code: str


@router.post("/api/account/redeem")
def redeem_code(payload: RedeemRequest, user=Depends(get_current_user)):
    code = (payload.code or "").strip().upper()
    valid = {c.strip().upper() for c in (settings.pro_codes or "").split(",") if c.strip()}
    if code not in valid:
        raise HTTPException(status_code=400, detail="That Pro code is not valid. Check with the owner.")
    meta = dict(getattr(user, "user_metadata", None) or {})
    meta["is_pro"] = True
    meta["plan"] = "pro"
    _admin_auth().update_user_by_id(user.id, {"user_metadata": meta})
    return {"ok": True, "message": "Welcome to ClipViral Pro! 🎉 Ads off, watermark off, speed boost ON."}
