# api.py
import os
import json
import uuid
import math
import subprocess
from datetime import datetime
from typing import List, Optional, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="WorldMarketReviewer API")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Summary artifacts your phone hits
SUMMARY_JSON = os.path.join(BASE_DIR, "data", "latest_summary.json")
SUMMARY_CSV_FALLBACK = os.path.join(BASE_DIR, "data", "mobile_summary.csv")

# Phase 2 artifacts
RESULTS_FILE = os.path.join(BASE_DIR, "results", "predictions.csv")
STATE_FILE = os.path.join(BASE_DIR, "phase2_state.json")

RUNS_DIR = os.path.join(BASE_DIR, "runs")
os.makedirs(RUNS_DIR, exist_ok=True)


def sanitize_json(obj: Any) -> Any:
    """
    Recursively make obj JSON-compliant by converting:
    - NaN, +Inf, -Inf => None
    """
    if obj is None:
        return None

    # floats: NaN/Inf handling
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj

    # ints/bools/strings are fine
    if isinstance(obj, (int, bool, str)):
        return obj

    # lists/tuples
    if isinstance(obj, (list, tuple)):
        return [sanitize_json(x) for x in obj]

    # dicts
    if isinstance(obj, dict):
        return {str(k): sanitize_json(v) for k, v in obj.items()}

    # other types: convert to string (safe fallback)
    return str(obj)


# -------------------------
# Summary endpoint (mobile)
# -------------------------
@app.get("/api/summary")
def api_summary():
    """
    Mobile app reads this.
    Primary: data/latest_summary.json
    Fallback: data/mobile_summary.csv (returned as text)
    Always returns JSON-safe content.
    """
    if os.path.exists(SUMMARY_JSON):
        with open(SUMMARY_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        return sanitize_json(data)

    if os.path.exists(SUMMARY_CSV_FALLBACK):
        with open(SUMMARY_CSV_FALLBACK, "r", encoding="utf-8", errors="replace") as f:
            return {"format": "csv", "content": f.read()}

    return {
        "error": "No summary found",
        "expected_json": SUMMARY_JSON,
        "expected_csv": SUMMARY_CSV_FALLBACK,
    }


# -------------------------
# Phase 2 endpoints
# -------------------------
class Phase2RunRequest(BaseModel):
    mode: str = "all"  # "all" or "tickers"
    tickers: Optional[List[str]] = None
    max_parallel: int = 4
    force: bool = True
    sleep: float = 0.0


def _run_paths(run_id: str):
    meta = os.path.join(RUNS_DIR, f"{run_id}.json")
    log = os.path.join(RUNS_DIR, f"{run_id}.log")
    return meta, log


def _write_meta(run_id: str, data: dict):
    meta_path, _ = _run_paths(run_id)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _read_meta(run_id: str) -> dict:
    meta_path, _ = _run_paths(run_id)
    if not os.path.exists(meta_path):
        raise HTTPException(status_code=404, detail="run_id not found")
    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.post("/phase2/run")
def phase2_run(req: Phase2RunRequest):
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
    _, log_path = _run_paths(run_id)

    runner = os.path.join(BASE_DIR, "phase2_parallel_runner.py")

    cmd = [
        os.sys.executable,
        runner,
        "--max-parallel", str(max(1, req.max_parallel)),
        "--sleep", str(req.sleep),
    ]
    if req.force:
        cmd.append("--force")

    if req.mode == "all":
        cmd.append("--all")
    elif req.mode == "tickers":
        if not req.tickers:
            raise HTTPException(status_code=400, detail="tickers required when mode='tickers'")
        tickers_str = ",".join([t.upper().strip() for t in req.tickers if t.strip()])
        cmd += ["--tickers", tickers_str]
    else:
        raise HTTPException(status_code=400, detail="mode must be 'all' or 'tickers'")

    _write_meta(run_id, {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "status": "running",
        "cmd": cmd,
        "log_path": log_path,
        "results_file": RESULTS_FILE,
        "state_file": STATE_FILE,
    })

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    with open(log_path, "w", encoding="utf-8") as logf:
        subprocess.Popen(
            cmd,
            cwd=BASE_DIR,
            env=env,
            stdout=logf,
            stderr=subprocess.STDOUT,
            text=True
        )

    return {"run_id": run_id, "status": "running"}


@app.get("/phase2/status/{run_id}")
def phase2_status(run_id: str):
    meta = _read_meta(run_id)
    _, log_path = _run_paths(run_id)

    if meta.get("status") in ("success", "failed"):
        return meta

    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            txt = f.read()

        if "=== DONE ===" in txt:
            status = "success"
            import re
            m = re.search(r"Failed:\s+(\d+)", txt)
            if m and int(m.group(1)) > 0:
                status = "failed"
            meta["status"] = status
            meta["finished_at"] = datetime.now().isoformat(timespec="seconds")
            _write_meta(run_id, meta)

    return meta


@app.get("/phase2/log/{run_id}")
def phase2_log(run_id: str, tail_kb: int = 64):
    _ = _read_meta(run_id)
    _, log_path = _run_paths(run_id)

    if not os.path.exists(log_path):
        return {"run_id": run_id, "log": ""}

    max_bytes = max(1, int(tail_kb)) * 1024
    with open(log_path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - max_bytes), os.SEEK_SET)
        data = f.read()

    return {"run_id": run_id, "log": data.decode("utf-8", errors="replace")}


@app.get("/phase2/last")
def phase2_last():
    return sanitize_json({
        "results_file": RESULTS_FILE,
        "state_file": STATE_FILE,
        "results_exists": os.path.exists(RESULTS_FILE),
        "state_exists": os.path.exists(STATE_FILE),
        "server_time": datetime.now().isoformat(timespec="seconds"),
    })


@app.get("/")
def root():
    return {"message": "WorldMarketReviewer API is running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=False)
