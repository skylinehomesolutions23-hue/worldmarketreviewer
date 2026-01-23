import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

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
    out = []
    seen = set()
    for t in raw:
        tk = (t or "").upper().strip()
        if not tk or tk in seen:
            continue
        seen.add(tk)
        out.append(tk)
    return out[:10]


class SubscribeRequest(BaseModel):
    email: str
    enabled: bool = True
    tickers: Any
    min_prob_up: float = 0.65
    min_confidence: str = "MEDIUM"  # LOW/MEDIUM/HIGH
    horizon_days: int = 5
    source_pref: str = "auto"  # auto/cache/live
    cooldown_minutes: int = 360  # 6 hours


@router.get("/health")
def alerts_health():
    return {
        "ok": True,
        "smtp_configured": smtp_configured(),
        "time_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


@router.post("/subscribe")
def subscribe(req: SubscribeRequest):
    tickers = _parse_tickers(req.tickers)
    if not tickers:
        return {"ok": False, "error": "tickers is required (up to 10)"}

    sub = upsert_subscription(
        {
            "email": req.email,
            "enabled": bool(req.enabled),
            "tickers": ",".join(tickers),
            "min_prob_up": float(req.min_prob_up),
            "min_confidence": (req.min_confidence or "MEDIUM").upper().strip(),
            "horizon_days": int(req.horizon_days),
            "source_pref": (req.source_pref or "auto").lower().strip(),
            "cooldown_minutes": int(req.cooldown_minutes),
        }
    )
    return {"ok": True, "subscription": sub}


@router.get("/subscription")
def subscription(email: str):
    sub = get_subscription(email)
    if not sub:
        return {"ok": False, "error": "Not found"}
    # normalize tickers to list for client convenience
    sub["tickers_list"] = _parse_tickers(sub.get("tickers"))
    return {"ok": True, "subscription": sub}


@router.get("/events")
def events(email: str, limit: int = 100):
    rows = get_alert_events(email, limit=limit)
    return {"ok": True, "email": (email or "").strip().lower(), "returned": len(rows), "events": rows}


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
    """
    cron_key = os.getenv("ALERTS_CRON_KEY", "").strip()
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
        tickers = (sub.get("tickers") or "").strip()
        tickers_list = [t for t in tickers.replace(" ", ",").split(",") if t.strip()]
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
            lines = []
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
            if email_result.get("ok"):
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
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from alerts_db import (
    get_alert_events,
    get_subscription,
    insert_alert_events,
    list_enabled_subscriptions,
    set_last_sent_at,
    upsert_subscription,
)
from alerts_engine import build_alert_items, fetch_predictions, smtp_configured

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class SubscribeRequest(BaseModel):
    email: EmailStr
    tickers: List[str]
    horizon_days: int = 5
    min_confidence: str = "MEDIUM"


def _normalize_tickers(tickers: List[str]) -> List[str]:
    seen = set()
    out = []
    for t in tickers or []:
        t = (t or "").upper().strip()
        if not t:
            continue
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out[:10]  # enforce max 10


def _cron_key() -> str:
    return (os.getenv("ALERTS_CRON_KEY") or "").strip()


@router.get("/health")
def health():
    return {
        "ok": True,
        "smtp_configured": smtp_configured(),
        "cron_key_set": bool(_cron_key()),
        "time_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


@router.post("/subscribe")
def subscribe(req: SubscribeRequest):
    tickers = _normalize_tickers(req.tickers)
    if not tickers:
        raise HTTPException(status_code=400, detail="Provide at least one ticker.")
    tickers_csv = ",".join(tickers)

    row = add_subscription(
        email=req.email,
        tickers_csv=tickers_csv,
        horizon_days=int(req.horizon_days),
        min_confidence=(req.min_confidence or "MEDIUM").upper().strip(),
    )
    return {"ok": True, "subscription": row}


@router.get("/subscriptions")
def subscriptions(limit: int = 200):
    limit = max(1, min(2000, int(limit)))
    rows = list_subscriptions(limit=limit)
    return {"ok": True, "count": len(rows), "rows": rows}


@router.delete("/subscriptions/{sub_id}")
def unsubscribe(sub_id: int):
    ok = delete_subscription(sub_id)
    return {"ok": ok}


@router.post("/run")
def run_alerts(
    key: str,
    source_pref: str = "auto",
):
    """
    This is what a Render Cron Job will call.
    It requires ?key=ALERTS_CRON_KEY so random users can't run it.
    """
    if not _cron_key():
        raise HTTPException(status_code=500, detail="ALERTS_CRON_KEY not configured on server.")
    if key != _cron_key():
        raise HTTPException(status_code=401, detail="Unauthorized")

    rows = list_subscriptions(limit=500)

    sent = 0
    checked = 0
    preview: List[Dict[str, Any]] = []

    for sub in rows:
        checked += 1
        tickers_csv = (sub.get("tickers") or "").strip()
        tickers = [t.strip().upper() for t in tickers_csv.split(",") if t.strip()]
        horizon_days = int(sub.get("horizon_days") or 5)
        min_conf = (sub.get("min_confidence") or "MEDIUM").upper().strip()

        try:
            summary_json = fetch_predictions(tickers=tickers, horizon_days=horizon_days, source_pref=source_pref)
            items = build_alert_items(summary_json, min_confidence=min_conf)
        except Exception as e:
            preview.append({"email": sub.get("email"), "error": str(e)})
            continue

        # For now we don't send emails; we just mark as "sent" if any items matched
        if items:
            mark_sent(int(sub["id"]))
            sent += 1
            preview.append({"email": sub.get("email"), "count": len(items), "top": items[:3]})
        else:
            preview.append({"email": sub.get("email"), "count": 0})

    return {
        "ok": True,
        "checked": checked,
        "sent": sent,
        "source_pref": source_pref,
        "preview": preview[:25],
        "time_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "note": "Email delivery not enabled yet; this is a safe dry-run that marks last_sent_at.",
    }
