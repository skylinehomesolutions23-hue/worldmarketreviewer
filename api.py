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

DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

SUMMARY_JSON = os.path.join(DATA_DIR, "latest_summary.json")
SUMMARY_CSV = os.path.join(DATA_DIR, "mobile_summary.csv")

BUILD_SUMMARY_SCRIPT = os.path.join(BASE_DIR, "build_mobile_summary.py")

RESULTS_FILE = os.path.join(BASE_DIR, "results", "predictions.csv")
STATE_FILE = os.path.join(BASE_DIR, "phase2_state.json")

RUNS_DIR = os.path.join(BASE_DIR, "runs")
os.makedirs(RUNS_DIR, exist_ok=True)


def sanitize_json(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, (int, bool, str)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [sanitize_json(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): sanitize_json(v) for k, v in obj.items()}
    return str(obj)


def try_build_summary() -> dict:
    """
    Attempt to build summary by running build_mobile_summary.py.
    Returns a dict with debug info (never raises).
    """
    debug = {
        "script_exists": os.path.exists(BUILD_SUMMARY_SCRIPT),
        "summary_json_exists_before": os.path.exists(SUMMARY_JSON),
        "summary_csv_exists_before": os.path.exists(SUMMARY_CSV),
        "cwd": BASE_DIR,
    }

    if not os.path.exists(BUILD_SUMMARY_SCRIPT):
        debug["error"] = "build_mobile_summary.py not found in repo"
        return debug

    try:
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        # capture output so we can diagnose Render failures
        p = subprocess.run(
            [os.sys.executable, BUILD_SUMMARY_SCRIPT],
            cwd=BASE_DIR,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=60,
            check=False,
        )
        debug["returncode"] = p.returncode
        debug["output_tail"] = (p.stdout or "")[-1500:]  # last 1500 chars
    except Exception as e:
        debug["exception"] = str(e)

    debug["summary_json_exists_after"] = os.path.exists(SUMMARY_JSON)
    debug["summary_csv_exists_after"] = os.path.exists(SUMMARY_CSV)
    return debug


@app.get("/api/summary")
def api_summary():
    # If JSON not present, try generating it
    if not os.path.exists(SUMMARY_JSON):
        debug = try_build_summary()
    else:
        debug = {"note": "latest_summary.json already exists"}

    # Return JSON if present
    if os.path.exists(SUMMARY_JSON):
        with open(SUMMARY_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        return sanitize_json(data)

    # Else return CSV if present
    if os.path.exists(SUMMARY_CSV):
        with open(SUMMARY_CSV, "r", encoding="utf-8", errors="replace") as f:
            return {"format": "csv", "content": f.read()}

    # Else return debug so we can see why Render can't build it
    return {
        "error": "No summary found",
        "debug": debug,
        "expected_json": SUMMARY_JSON,
        "expected_csv": SUMMARY_CSV,
    }


class Phase2RunRequest(BaseModel):
    mode: str = "all"
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


@app.get("/")
def root():
    return {"message": "WorldMarketReviewer API is running"}
