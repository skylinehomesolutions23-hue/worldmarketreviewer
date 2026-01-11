# tracker.py

import datetime
from database import insert_row, fetch_recent
from logger import log


def record(summary: dict):
    ts = datetime.datetime.utcnow().isoformat()

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
