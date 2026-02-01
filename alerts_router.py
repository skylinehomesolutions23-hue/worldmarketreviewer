# alerts_router.py
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

from alerts_db import (
    init_alerts_db,
    get_alert_events,
    get_subscription,
    insert_alert_events,
    list_enabled_subscriptions,
    set_last_sent_at,
    upsert_subscription,
)

from alerts_engine import cooldown_ok, run_alert_check, send_email_alert, smtp_configured

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def _parse_tickers(x: Any) -> List[str]:
    if x is None:
        return []
    if isinstance(x, list):
        raw = [str(v) for v in x]
    else:
        raw = str(x).replace(" ", ",").split(",")
    out: List[str] = []
    seen = set()
    for t in raw:
        tk = (t or "").upper().strip()
        if not tk or tk in seen:
            continue
        seen.add(tk)
        out.append(tk)
    return out[:10]


class SubscribeRequest(BaseModel):
    email: EmailStr
    enabled: bool = True
    tickers: Any
    min_prob_up: float = 0.65
    min_confidence: str = "MEDIUM"  # LOW/MEDIUM/HIGH
    horizon_days: int = 5
    source_pref: str = "auto"  # auto/cache/live
    cooldown_minutes: int = 360  # 6 hours


def _db_info_safe() -> Dict[str, Any]:
    raw = os.getenv("DATABASE_URL") or ""
    raw_stripped = raw.strip()

    info: Dict[str, Any] = {
        "database_url_set": bool(raw),
        "database_url_stripped_differs": raw != raw_stripped,
        "database_url_len": len(raw),
        "database_url_stripped_len": len(raw_stripped),
    }

    try:
        u = urlparse(raw_stripped)
        dbname = (u.path or "").lstrip("/")
        info.update(
            {
                "scheme": u.scheme,
                "host": u.hostname,
                "port": u.port,
                "user": u.username,
                "db_name": dbname,
                "db_name_repr": repr(dbname),
            }
        )
    except Exception as e:
        info["parse_error"] = str(e)

    return info


@router.get("/health")
def alerts_health():
    init_alerts_db()
    return {
        "ok": True,
        "smtp_configured": smtp_configured(),
        "cron_key_set": bool((os.getenv("ALERTS_CRON_KEY") or "").strip()),
        "time_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


@router.get("/db_info")
def db_info():
    return {"ok": True, "db": _db_info_safe()}


@router.get("/smtp_info")
def smtp_info():
    host = (os.getenv("SMTP_HOST") or "").strip()
    port = (os.getenv("SMTP_PORT") or "").strip()
    user = (os.getenv("SMTP_USER") or "").strip()
    pwd = (os.getenv("SMTP_PASS") or "").strip()
    from_email = (os.getenv("SMTP_FROM_EMAIL") or os.getenv("SMTP_USER") or "").strip()
    use_tls = (os.getenv("SMTP_USE_TLS") or "1").strip() not in ("0", "false", "False")

    return {
        "ok": True,
        "SMTP_HOST_set": bool(host),
        "SMTP_PORT_set": bool(port),
        "SMTP_USER_set": bool(user),
        "SMTP_PASS_set": bool(pwd),
        "SMTP_FROM_EMAIL_set": bool(from_email),
        "SMTP_USE_TLS": use_tls,
        "SMTP_USER_value": user,
        "SMTP_FROM_EMAIL_value": from_email,
    }


# ✅ Keep ONE debug endpoint (query params)
@router.post("/debug_check")
def debug_check(
    email: str,
    tickers: str = "SPY,QQQ",
    min_prob_up: float = 0.0,
    min_confidence: str = "LOW",
    horizon_days: int = 5,
    source_pref: str = "auto",
    max_parallel: int = 2,
):
    tickers_list = [t.strip().upper() for t in tickers.replace(" ", ",").split(",") if t.strip()]
    out = run_alert_check(
        email=email,
        tickers=tickers_list,
        min_prob_up=min_prob_up,
        min_confidence=min_confidence,
        horizon_days=horizon_days,
        source_pref=source_pref,
        max_parallel=max_parallel,
        retrain=False,
    )
    return {"tickers_list": tickers_list, "out": out}


@router.post("/subscribe")
def subscribe(req: SubscribeRequest):
    init_alerts_db()

    tickers = _parse_tickers(req.tickers)
    if not tickers:
        return {"ok": False, "error": "tickers is required (up to 10)"}

    sub = upsert_subscription(
        {
            "email": (req.email or "").strip().lower(),
            "enabled": bool(req.enabled),
            "tickers": ",".join(tickers),
            "min_prob_up": float(req.min_prob_up),
            "min_confidence": (req.min_confidence or "MEDIUM").upper().strip(),
            "horizon_days": int(req.horizon_days),
            "source_pref": (req.source_pref or "auto").lower().strip(),
            "cooldown_minutes": int(req.cooldown_minutes),
        }
    )

    if isinstance(sub, dict):
        sub["tickers_list"] = _parse_tickers(sub.get("tickers"))

    return {"ok": True, "subscription": sub}


@router.get("/subscription")
def subscription(email: str):
    init_alerts_db()

    sub = get_subscription(email)
    if not sub:
        return {"ok": False, "error": "Not found"}
    sub["tickers_list"] = _parse_tickers(sub.get("tickers"))
    return {"ok": True, "subscription": sub}


@router.get("/subscriptions")
def subscriptions(limit: int = 200) -> Dict[str, Any]:
    init_alerts_db()

    limit = max(1, min(2000, int(limit)))
    rows = list_enabled_subscriptions(limit=limit) or []

    for r in rows:
        r["tickers_list"] = _parse_tickers(r.get("tickers"))

    return {"ok": True, "returned": len(rows), "items": rows}


@router.get("/events")
def events(email: str, limit: int = 100):
    init_alerts_db()

    limit = max(1, min(2000, int(limit)))
    rows = get_alert_events(email, limit=limit)
    return {
        "ok": True,
        "email": (email or "").strip().lower(),
        "returned": len(rows),
        "events": rows,
    }


# ✅ Add overrides so you can force a test email without relying on DB values
@router.post("/run")
def run_all(
    key: Optional[str] = None,
    email: Optional[str] = None,
    max_parallel: int = 4,
    # overrides (optional)
    override_min_prob_up: Optional[float] = None,
    override_min_confidence: Optional[str] = None,
):
    init_alerts_db()

    cron_key = (os.getenv("ALERTS_CRON_KEY") or "").strip()
    if cron_key and (key or "").strip() != cron_key:
        return {"ok": False, "error": "Unauthorized (bad key)"}

    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    sent = 0
    checked = 0
    total_hits = 0

    subs: List[Dict[str, Any]] = []
    if email:
        sub = get_subscription(email)
        if not sub or not bool(sub.get("enabled", True)):
            return {"ok": True, "note": "No enabled subscription found for that email.", "time_utc": now}
        subs = [sub]
    else:
        subs = list_enabled_subscriptions(limit=500)

    results: List[Dict[str, Any]] = []
    for sub in subs:
        checked += 1

        em = (sub.get("email") or "").strip().lower()
        tickers_csv = (sub.get("tickers") or "").strip()
        tickers_list = [t.strip().upper() for t in tickers_csv.replace(" ", ",").split(",") if t.strip()][:10]

        min_prob_up = float(sub.get("min_prob_up") or 0.65)
        min_confidence = (sub.get("min_confidence") or "MEDIUM").upper().strip()

        # apply overrides for testing
        if override_min_prob_up is not None:
            min_prob_up = float(override_min_prob_up)
        if override_min_confidence is not None:
            min_confidence = (override_min_confidence or "LOW").upper().strip()

        horizon_days = int(sub.get("horizon_days") or 5)
        source_pref = (sub.get("source_pref") or "auto").lower().strip()
        cm = sub.get("cooldown_minutes")
        cooldown_minutes = int(360 if cm is None else cm)

        last_sent_at = sub.get("last_sent_at")

        allow_send = cooldown_ok(last_sent_at, cooldown_minutes)

        run = run_alert_check(
            email=em,
            tickers=tickers_list,
            min_prob_up=min_prob_up,
            min_confidence=min_confidence,
            horizon_days=horizon_days,
            source_pref=source_pref,
            max_parallel=max_parallel,
            retrain=False,
        )

        if not run.get("ok"):
            results.append(
                {
                    "email": em,
                    "hits": 0,
                    "cooldown_ok": allow_send,
                    "emailed": False,
                    "smtp_configured": smtp_configured(),
                    "email_result": None,
                    "errors": run.get("errors") or {},
                    "note": "run_alert_check failed",
                }
            )
            continue

        hits = run.get("hits") or []
        total_hits += len(hits)

        if hits:
            insert_alert_events(em, hits)

        did_send = False
        email_result = None

        if hits and allow_send:
            subject = f"WorldMarketReviewer Alerts ({len(hits)})"
            lines: List[str] = [
                f"Alert trigger time (UTC): {now}",
                f"Rule: prob_up≥{min_prob_up:.2f} & conf≥{min_confidence}",
                f"Horizon: {horizon_days} trading days",
                "",
            ]
            for h in hits[:20]:
                lines.append(
                    f"- {h.get('ticker')} | prob_up={(h.get('prob_up') or 0):.2f} | conf={h.get('confidence')} | as_of={h.get('as_of_date')} | source={h.get('source')}"
                )
            lines += ["", "Tip: Too many emails? Increase cooldown_minutes in your subscription."]

            email_result = send_email_alert(em, subject, "\n".join(lines))
            if isinstance(email_result, dict) and email_result.get("ok"):
                did_send = True
                sent += 1
                set_last_sent_at(em, now)

        results.append(
            {
                "email": em,
                "hits": len(hits),
                "cooldown_ok": allow_send,
                "emailed": did_send,
                "smtp_configured": smtp_configured(),
                "email_result": email_result,
                "errors": run.get("errors") or {},
            }
        )

    return {
        "ok": True,
        "time_utc": now,
        "checked": checked,
        "emails_sent": sent,
        "total_hits": total_hits,
        "results_sample": results[:25],
        "note": "Use Render Cron to call /api/alerts/run?key=... on a schedule.",
    }
