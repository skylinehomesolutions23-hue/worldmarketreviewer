from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pathlib import Path
import json

from build_mobile_summary import main as run_summary
from tracker import get_history

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"
DASHBOARD_FILE = BASE_DIR / "dashboard.html"


# -----------------------
# Helpers
# -----------------------
def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


# -----------------------
# Routes
# -----------------------

@app.get("/", response_class=HTMLResponse)
def dashboard():
    return DASHBOARD_FILE.read_text()


@app.get("/api/summary")
def summary():
    return run_summary()


@app.get("/api/history")
def history():
    return get_history()


@app.get("/api/config")
def config():
    return load_config()


@app.post("/api/profile/{name}")
def set_profile(name: str):
    cfg = load_config()

    if name not in cfg["profiles"]:
        return {"error": "Invalid profile"}

    cfg["active_profile"] = name
    save_config(cfg)

    return {"status": "ok", "active_profile": name}


@app.post("/api/toggle-auto")
def toggle_auto():
    cfg = load_config()
    cfg["auto_mode"] = not cfg.get("auto_mode", True)
    save_config(cfg)

    return {"status": "ok", "auto_mode": cfg["auto_mode"]}
