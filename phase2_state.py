# phase2_state.py
import json
import os
from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_state(state_path: str) -> dict:
    if not os.path.exists(state_path):
        return {"version": 1, "updated_at": _now_iso(), "tickers": {}}
    with open(state_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state_path: str, state: dict) -> None:
    state["updated_at"] = _now_iso()
    tmp_path = state_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
    os.replace(tmp_path, state_path)


def ensure_ticker(state: dict, ticker: str) -> None:
    state.setdefault("tickers", {})
    if ticker not in state["tickers"]:
        state["tickers"][ticker] = {
            "status": "never",
            "last_run_id": None,
            "last_error": None,
            "started_at": None,
            "finished_at": None
        }


def mark_started(state: dict, ticker: str, run_id: str) -> None:
    ensure_ticker(state, ticker)
    state["tickers"][ticker]["status"] = "running"
    state["tickers"][ticker]["last_run_id"] = run_id
    state["tickers"][ticker]["last_error"] = None
    state["tickers"][ticker]["started_at"] = _now_iso()
    state["tickers"][ticker]["finished_at"] = None


def mark_success(state: dict, ticker: str, run_id: str) -> None:
    ensure_ticker(state, ticker)
    state["tickers"][ticker]["status"] = "success"
    state["tickers"][ticker]["last_run_id"] = run_id
    state["tickers"][ticker]["last_error"] = None
    state["tickers"][ticker]["finished_at"] = _now_iso()


def mark_failed(state: dict, ticker: str, run_id: str, error: str) -> None:
    ensure_ticker(state, ticker)
    state["tickers"][ticker]["status"] = "failed"
    state["tickers"][ticker]["last_run_id"] = run_id
    state["tickers"][ticker]["last_error"] = str(error)
    state["tickers"][ticker]["finished_at"] = _now_iso()


def should_run(state: dict, ticker: str, force: bool = False) -> bool:
    ensure_ticker(state, ticker)
    return True if force else state["tickers"][ticker]["status"] != "success"


def reset_ticker(state: dict, ticker: str) -> None:
    ensure_ticker(state, ticker)
    state["tickers"][ticker] = {
        "status": "never",
        "last_run_id": None,
        "last_error": None,
        "started_at": None,
        "finished_at": None
    }
