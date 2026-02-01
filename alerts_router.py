# alerts_router.py
import os
from datetime import datetime, time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

from alerts_db import (
    init_alerts_db,
    get_alert_events,
    get_last_email_sent_by_ticker,
    get_subscription,
    insert_alert_events,
    insert_email_sent_events,
    insert_recap_sent_event,
    list_enabled_subscriptions,
    list_recap_enabled_subscriptions,
    set_last_recap_sent_at,
    set_last_sent_at,
    update_recap_settings,
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


def _parse_days(days: str) -> List[str]:
    raw = (days or "").lower().replace(" ", "")
    if not raw:
        return ["mon", "tue", "wed", "thu", "fri"]
    if raw in ("all", "daily", "*"):
        return ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    parts = [p for p in raw.split(",") if p]
    ok = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
    cleaned = [p for p in parts if p in ok]
    return cleaned or ["mon", "tue", "wed", "thu", "fri"]


def _parse_hhmm(hhmm: str) -> time:
    s = (hhmm or "").strip()
    try:
        h, m = s.split(":")
        hh = max(0, min(23, int(h)))
        mm = max(0, min(59, int(m)))
        return time(hour=hh, minute=mm)
    except Exception:
        return time(hour=21, minute=0)  # default 9pm


def _get_tz(tzname: str):
    # zoneinfo is built-in in Python 3.9+
    from zoneinfo import ZoneInfo

    try:
        return ZoneInfo((tzname or "").strip() or "America/New_York")
    except Exception:
        return ZoneInfo("America/New_York")


def _should_send_recap(now_utc: datetime, sub: Dict[str, Any]) -> Dict[str, Any]:
    """
    Decide if recap should be sent for this subscription right now.
    Returns {"ok": bool, "reason": "...", "local_now": "...", "local_today": "..."}.
    """
    tz = _get_tz(sub.get("recap_timezone") or "America/New_York")
    local_now = now_utc.astimezone(tz)

    recap_time = _parse_hhmm(sub.get("recap_time_local") or "21:00")
    allowed_days = _parse_days(sub.get("recap_days") or "mon,tue,wed,thu,fri")

    dow_map = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    local_dow = dow_map[local_now.weekday()]

    if local_dow not in allowed_days:
        return {
            "ok": False,
            "reason": f"day_not_allowed:{local_dow}",
            "local_now": local_now.isoformat(),
            "local_today": local_now.date().isoformat(),
        }

    # Only send after the chosen local time
    if (local_now.time().hour, local_now.time().minute) < (recap_time.hour, recap_time.minute):
        return {
            "ok": False,
            "reason": "too_early",
            "local_now": local_now.isoformat(),
            "local_today": local_now.date().isoformat(),
        }

    # Ensure once-per-local-day
    last = sub.get("last_recap_sent_at")
    if isinstance(last, str):
        try:
            last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
        except Exception:
            last_dt = None
    elif isinstance(last, datetime):
        last_dt = last
    else:
        last_dt = None

    if last_dt is not None:
        if last_dt.tzinfo is None:
            # assume UTC
            last_dt = last_dt.replace(tzinfo=tz)
        last_local = last_dt.astimezone(tz)
        if last_local.date() == local_now.date():
            return {
                "ok": False,
                "reason": "already_sent_today",
                "local_now": local_now.isoformat(),
                "local_today": local_now.date().isoformat(),
            }

    return {
        "ok": True,
        "reason": "send",
        "local_now": local_now.isoformat(),
        "local_today": local_now.date().isoformat(),
    }


def _fetch_daily_closes(tickers: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    For each ticker, fetch last 2 daily closes and compute change.
    Returns { "SPY": {"close":..., "prev_close":..., "chg":..., "chg_pct":..., "as_of": "..."} }
    """
    out: Dict[str, Dict[str, Any]] = {}
    tks = [t.upper().strip() for t in tickers if (t or "").strip()]
    tks = list(dict.fromkeys(tks))[:25]
    if not tks:
        return out

    try:
        import yfinance as yf

        df = yf.download(
            tickers=" ".join(tks),
            period="7d",
            interval="1d",
            group_by="ticker",
            auto_adjust=False,
            threads=True,
            progress=False,
        )
        # df can be:
        # - MultiIndex columns if multiple tickers
        # - Single columns if one ticker
        if df is None or len(df.index) == 0:
            return out

        # Ensure we have at least 2 rows to compute change
        if len(df.index) < 2:
            # still return last close
            idx_last = df.index[-1]
            as_of = idx_last.to_pydatetime().date().isoformat()
            if len(tks) == 1:
                close = float(df["Close"].iloc[-1])
                out[tks[0]] = {"close": close, "prev_close": None, "chg": None, "chg_pct": None, "as_of": as_of}
            return out

        idx_last = df.index[-1]
        idx_prev = df.index[-2]
        as_of = idx_last.to_pydatetime().date().isoformat()

        if len(tks) == 1 and "Close" in df.columns:
            tk = tks[0]
            close = float(df["Close"].iloc[-1])
            prev_close = float(df["Close"].iloc[-2])
            chg = close - prev_close
            chg_pct = (chg / prev_close) * 100 if prev_close else None
            out[tk] = {"close": close, "prev_close": prev_close, "chg": chg, "chg_pct": chg_pct, "as_of": as_of}
            return out

        # Multi-ticker: df columns are like (TICKER, "Close")
        for tk in tks:
            try:
                close = df[(tk, "Close")].iloc[-1]
                prev_close = df[(tk, "Close")].iloc[-2]
                if close is None or prev_close is None:
                    continue
                close_f = float(close)
                prev_f = float(prev_close)
                chg = close_f - prev_f
                chg_pct = (chg / prev_f) * 100 if prev_f else None
                out[tk] = {"close": close_f, "prev_close": prev_f, "chg": chg, "chg_pct": chg_pct, "as_of": as_of}
            except Exception:
                continue

        return out
    except Exception:
        return out


class SubscribeRequest(BaseModel):
    email: EmailStr
    enabled: bool = True
    tickers: Any
    min_prob_up: float = 0.65
    min_confidence: str = "MEDIUM"  # LOW/MEDIUM/HIGH
    horizon_days: int = 5
    source_pref: str = "auto"  # auto/cache/live
    cooldown_minutes: int = 360  # 6 hours


class RecapSettingsRequest(BaseModel):
    email: EmailStr
    recap_enabled: bool = True
    recap_time_local: str = "21:00"  # HH:MM (local)
    recap_timezone: str = "America/New_York"
    recap_days: str = "mon,tue,wed,thu,fri"  # or "all"


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


# --- Daily recap settings endpoints ---

@router.get("/recap_settings")
def recap_settings(email: str):
    init_alerts_db()
    sub = get_subscription(email)
    if not sub:
        return {"ok": False, "error": "Not found"}
    return {
        "ok": True,
        "email": (email or "").strip().lower(),
        "recap_enabled": bool(sub.get("recap_enabled", False)),
        "recap_time_local": sub.get("recap_time_local") or "21:00",
        "recap_timezone": sub.get("recap_timezone") or "America/New_York",
        "recap_days": sub.get("recap_days") or "mon,tue,wed,thu,fri",
        "last_recap_sent_at": sub.get("last_recap_sent_at"),
    }


@router.post("/recap_settings")
def set_recap(req: RecapSettingsRequest):
    init_alerts_db()
    # Ensure subscription exists
    sub = get_subscription(req.email)
    if not sub:
        return {"ok": False, "error": "Subscription not found. Create it with /subscribe first."}

    updated = update_recap_settings(
        email=str(req.email),
        recap_enabled=bool(req.recap_enabled),
        recap_time_local=str(req.recap_time_local or "21:00"),
        recap_timezone=str(req.recap_timezone or "America/New_York"),
        recap_days=str(req.recap_days or "mon,tue,wed,thu,fri"),
    )
    return updated


# --- Existing alerts runner (per-ticker cooldown) ---

@router.post("/run")
def run_all(
    key: Optional[str] = None,
    email: Optional[str] = None,
    max_parallel: int = 4,
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

        if override_min_prob_up is not None:
            min_prob_up = float(override_min_prob_up)
        if override_min_confidence is not None:
            min_confidence = (override_min_confidence or "LOW").upper().strip()

        horizon_days = int(sub.get("horizon_days") or 5)
        source_pref = (sub.get("source_pref") or "auto").lower().strip()
        cm = sub.get("cooldown_minutes")
        cooldown_minutes = int(360 if cm is None else cm)

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
                    "eligible_hits": 0,
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

        last_sent_map = get_last_email_sent_by_ticker(em, [h.get("ticker") for h in hits])
        eligible_hits: List[Dict[str, Any]] = []
        blocked_tickers: List[str] = []

        for h in hits:
            tk = (h.get("ticker") or "").upper().strip()
            last_dt = last_sent_map.get(tk)
            if cooldown_ok(last_dt, cooldown_minutes):
                eligible_hits.append(h)
            else:
                blocked_tickers.append(tk)

        did_send = False
        email_result = None

        if eligible_hits:
            subject = f"WorldMarketReviewer Alerts ({len(eligible_hits)})"
            lines: List[str] = [
                f"Alert trigger time (UTC): {now}",
                f"Rule: prob_up≥{min_prob_up:.2f} & conf≥{min_confidence}",
                f"Horizon: {horizon_days} trading days",
                f"Cooldown: {cooldown_minutes} minutes (per ticker)",
                "",
            ]
            for h in eligible_hits[:20]:
                lines.append(
                    f"- {h.get('ticker')} | prob_up={(h.get('prob_up') or 0):.2f} | conf={h.get('confidence')} | as_of={h.get('as_of_date')} | source={h.get('source')}"
                )

            if blocked_tickers:
                lines += ["", f"Blocked by per-ticker cooldown: {', '.join(sorted(set(blocked_tickers)))}"]

            lines += ["", "Tip: Too many emails? Increase cooldown_minutes in your subscription."]

            email_result = send_email_alert(em, subject, "\n".join(lines))
            if isinstance(email_result, dict) and email_result.get("ok"):
                did_send = True
                sent += 1

                meta = {
                    "now_utc": now,
                    "rule_min_prob_up": float(min_prob_up),
                    "rule_min_confidence": str(min_confidence),
                    "horizon_days": int(horizon_days),
                    "cooldown_minutes": int(cooldown_minutes),
                    "source_pref": str(source_pref),
                }
                insert_email_sent_events(em, eligible_hits, meta=meta)
                set_last_sent_at(em, now)

        results.append(
            {
                "email": em,
                "hits": len(hits),
                "eligible_hits": len(eligible_hits),
                "blocked_tickers": sorted(set(blocked_tickers)),
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


# --- Daily recap runner (new) ---

@router.post("/run_recap")
def run_recap(
    key: Optional[str] = None,
    email: Optional[str] = None,
):
    init_alerts_db()

    cron_key = (os.getenv("ALERTS_CRON_KEY") or "").strip()
    if cron_key and (key or "").strip() != cron_key:
        return {"ok": False, "error": "Unauthorized (bad key)"}

    now_utc_dt = datetime.utcnow().replace(microsecond=0)
    now_utc = now_utc_dt.isoformat() + "Z"

    checked = 0
    attempted = 0
    sent = 0
    results: List[Dict[str, Any]] = []

    if email:
        sub = get_subscription(email)
        if not sub:
            return {"ok": True, "time_utc": now_utc, "note": "subscription not found"}
        subs = [sub]
    else:
        subs = list_recap_enabled_subscriptions(limit=2000)

    for sub in subs:
        checked += 1
        em = (sub.get("email") or "").strip().lower()

        if not bool(sub.get("enabled", True)) or not bool(sub.get("recap_enabled", False)):
            continue

        decision = _should_send_recap(now_utc_dt.replace(tzinfo=_get_tz("UTC")), sub)
        if not decision.get("ok"):
            results.append({"email": em, "sent": False, "reason": decision.get("reason"), "local_now": decision.get("local_now")})
            continue

        tickers_list = _parse_tickers(sub.get("tickers") or "")
        if not tickers_list:
            results.append({"email": em, "sent": False, "reason": "no_tickers"})
            continue

        attempted += 1

        closes = _fetch_daily_closes(tickers_list)
        if not closes:
            results.append({"email": em, "sent": False, "reason": "no_price_data"})
            continue

        # Build email
        subject = "WorldMarketReviewer — Daily Recap"
        lines: List[str] = []
        lines.append(f"Daily recap generated (UTC): {now_utc}")
        lines.append(f"Your local time: {decision.get('local_now')}")
        lines.append("")
        lines.append("Close summary (last trading day):")
        lines.append("")

        # Sort by ticker
        for tk in sorted(closes.keys()):
            c = closes[tk]
            close = c.get("close")
            prev = c.get("prev_close")
            chg = c.get("chg")
            chg_pct = c.get("chg_pct")
            as_of = c.get("as_of")
            if close is None:
                continue
            if chg is None or chg_pct is None or prev is None:
                lines.append(f"- {tk}: close={close:.2f} (as_of {as_of})")
            else:
                sign = "+" if chg >= 0 else ""
                lines.append(f"- {tk}: close={close:.2f} | {sign}{chg:.2f} ({sign}{chg_pct:.2f}%) | as_of {as_of}")

        lines.append("")
        lines.append("Tip: You can change recap time/days in recap settings.")

        email_result = send_email_alert(em, subject, "\n".join(lines))
        if isinstance(email_result, dict) and email_result.get("ok"):
            sent += 1
            set_last_recap_sent_at(em, now_utc)

            insert_recap_sent_event(
                em,
                tickers_list,
                payload={
                    "now_utc": now_utc,
                    "local_now": decision.get("local_now"),
                    "recap_time_local": sub.get("recap_time_local"),
                    "recap_timezone": sub.get("recap_timezone"),
                    "recap_days": sub.get("recap_days"),
                    "count": len(closes),
                },
            )

            results.append({"email": em, "sent": True, "email_result": email_result, "count": len(closes)})
        else:
            results.append({"email": em, "sent": False, "email_result": email_result})

    return {
        "ok": True,
        "time_utc": now_utc,
        "checked": checked,
        "attempted": attempted,
        "recaps_sent": sent,
        "results_sample": results[:25],
        "note": "Call /api/alerts/run_recap?key=... on a schedule (e.g., every 15-30 minutes).",
    }
