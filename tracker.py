# tracker.py

import datetime
from database import insert_row, fetch_recent
from logger import log

_last_update = None


def record(summary: dict):
    global _last_update

    ts = datetime.datetime.utcnow().isoformat()
    _last_update = ts

    insert_row(
        timestamp=ts,
        status=summary["status"],
        exposure=summary["recommended_exposure"],
        vol=summary["vol_3m"],
        drawdown=summary["max_drawdown_3m"],
    )

    log(f"Recorded snapshot: {summary['status']} exposure={summary['recommended_exposure']}")


def get_recent(limit=200):
    return fetch_recent(limit)


def get_health():
    """Returns system health info"""
    if not _last_update:
        return {
            "status": "STALE",
            "last_update": None
        }

    last = datetime.datetime.fromisoformat(_last_update)
    now = datetime.datetime.utcnow()
    delta = (now - last).total_seconds()

    healthy = delta < 120  # 2 minutes threshold

    return {
        "status": "OK" if healthy else "STALE",
        "last_update": _last_update,
        "seconds_since_update": round(delta, 1)
    }
