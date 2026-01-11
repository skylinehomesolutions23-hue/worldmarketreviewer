# api.py

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pathlib import Path

from build_mobile_summary import main
from tracker import get_recent
from profile_manager import set_active_profile, load_config
from scheduler import start as start_scheduler
from database import init_db

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
DASHBOARD_FILE = BASE_DIR / "dashboard.html"


@app.on_event("startup")
def startup_event():
    init_db()
    start_scheduler()


# -------------------------
# Serve dashboard UI
# -------------------------
@app.get("/", response_class=HTMLResponse)
def dashboard():
    if DASHBOARD_FILE.exists():
        return DASHBOARD_FILE.read_text(encoding="utf-8")
    return "<h1>dashboard.html not found</h1>"


# -------------------------
# API endpoints
# -------------------------
@app.get("/api/summary")
def get_summary():
    return main()


@app.get("/api/history")
def history():
    return get_recent()


@app.post("/api/profile/{profile_name}")
def set_profile(profile_name: str):
    return set_active_profile(profile_name)


@app.get("/api/config")
def config():
    return load_config()
