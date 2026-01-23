import os
from datetime import datetime
from typing import Any, Dict, List, Optional

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


@router.get("/health")
def alerts_health():
    # Ensure DB exists + schema created
    init_alerts_db()
    return {
        "ok": True,
        "smtp_configured": smtp_configured(),
        "cron_key_set": bool((os.getenv("ALERTS_CRON_KEY") or "").strip()),
        "time_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


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
    # normalize tickers to list for client convenience
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


@router.post("/run")
def run_all(
    key: Optional[str] = None,
    email: Optional[str] = None,
    max_parallel: int = 4,
):
    """
    Cron-safe endpoint.
    - If email provided: run only for that subscription.
    - Otherwise runs for all enabled subscriptions.
    Protect with ALERTS_CRON_KEY on Render.

    Render Cron calls:
      /api/alerts/run?key=ALERTS_CRON_KEY
    """
    init_alerts_db()

    cron_key = (os.getenv("ALERTS_CRON_KEY") or "").strip()
    if cron_key:
        if (key or "").strip() != cron_key:
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
        tickers_list = [t for t in tickers_csv.replace(" ", ",").split(",") if t.strip()]
        tickers_list = [t.upper().strip() for t in tickers_list if t.strip()][:10]

        min_prob_up = float(sub.get("min_prob_up") or 0.65)
        min_confidence = (sub.get("min_confidence") or "MEDIUM").upper().strip()
        horizon_days = int(sub.get("horizon_days") or 5)
        source_pref = (sub.get("source_pref") or "auto").lower().strip()
        cooldown_minutes = int(sub.get("cooldown_minutes") or 360)
        last_sent_at = sub.get("last_sent_at")

        # Only email if cooldown passed
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

        hits = run.get("hits") or []
        total_hits += len(hits)

        if hits:
            # store hits
            insert_alert_events(em, hits)

        did_send = False
        email_result = None

        if hits and allow_send:
            subject = f"WorldMarketReviewer Alerts ({len(hits)})"
            lines: List[str] = []
            lines.append(f"Alert trigger time (UTC): {now}")
            lines.append(f"Rule: prob_up≥{min_prob_up:.2f} & conf≥{min_confidence}")
            lines.append(f"Horizon: {horizon_days} trading days")
            lines.append("")
            for h in hits[:20]:
                lines.append(
                    f"- {h.get('ticker')} | prob_up={(h.get('prob_up') or 0):.2f} | conf={h.get('confidence')} | as_of={h.get('as_of_date')} | source={h.get('source')}"
                )
            lines.append("")
            lines.append("Tip: Too many emails? Increase cooldown_minutes in your subscription.")

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
