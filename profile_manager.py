import json
from pathlib import Path

CONFIG_FILE = Path(__file__).resolve().parent / "config.json"

def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

def set_profile(profile_name):
    cfg = load_config()
    if profile_name not in cfg["profiles"]:
        raise ValueError("Invalid profile")
    cfg["active_profile"] = profile_name
    cfg["auto_mode"] = False
    save_config(cfg)
    return cfg

def auto_select_profile(vol, drawdown):
    cfg = load_config()

    if vol < 0.2 and drawdown > -0.15:
        selected = "aggressive"
    elif vol < 0.35:
        selected = "balanced"
    else:
        selected = "conservative"

    cfg["active_profile"] = selected
    save_config(cfg)
    return selected
