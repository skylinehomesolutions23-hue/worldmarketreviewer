from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import json
from pathlib import Path

from build_mobile_summary import main
from tracker import get_recent, get_health
from scheduler import start

app = FastAPI()

# Start scheduler safely (won't duplicate)
start()

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"
DASHBOARD = BASE_DIR / "dashboard.html"


# -----------------------------
# Helpers
# -----------------------------

def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)


# -----------------------------
# Routes
# -----------------------------

@app.get("/")
def home():
    return FileResponse(DASHBOARD)


@app.get("/api/summary")
def get_summary():
    return main()


@app.get("/api/config")
def get_config():
    config = load_config()
    return {"active_profile": config.get("active_profile", "unknown")}


@app.post("/api/profile/{profile}")
def set_profile(profile: str):
    config = load_config()

    if profile not in config["profiles"]:
        return {"error": "Invalid profile"}

    config["active_profile"] = profile
    save_config(config)

    return {"status": "ok", "active_profile": profile}


@app.get("/api/history")
def get_history():
    return get_recent(200)


@app.get("/api/health")
def health():
    return get_health()
