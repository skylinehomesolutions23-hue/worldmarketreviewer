# tracker.py

from datetime import datetime
from database import save_history, get_history
from logger import log


def record(summary: dict):
    """
    Records a snapshot into historical database.
    """
    timestamp = datetime.utcnow().isoformat()

    save_history(
        timestamp=timestamp,
        exposure=summary["recommended_exposure"],
        status=summary["status"]
    )

    log(f"Recorded snapshot: {summary['status']} exposure={summary['recommended_exposure']}")


def get_recent(limit=200):
    """
    Returns recent history for API/dashboard.
    """
    return get_history(limit)
