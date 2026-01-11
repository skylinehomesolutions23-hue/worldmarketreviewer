import pandas as pd
from pathlib import Path

from profile_manager import load_config, auto_select_profile
from explainability import explain_decision
from tracker import track

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

RETURNS_FILE = DATA_DIR / "monthly_returns.csv"
RISK_FILE = DATA_DIR / "integrated_risk_report.csv"
KILL_FILE = DATA_DIR / "signal_lifecycle_decision_v3.csv"

OUTPUT_FILE = DATA_DIR / "mobile_summary.csv"

def main():
    config = load_config()

    returns = pd.read_csv(RETURNS_FILE)
    risk = pd.read_csv(RISK_FILE)
    kill = pd.read_csv(KILL_FILE)

    latest_returns = returns.iloc[-1]
    latest_risk = risk.iloc[-1]
    latest_kill = kill.iloc[-1]

    vol = float(latest_risk.get("vol_3m", 0))
    dd = float(latest_risk.get("max_dd_3m", 0))
    kill_signal = bool(latest_kill.get("kill_signal", False))

    # Auto profile
    if config.get("auto_mode", True):
        active_profile = auto_select_profile(vol, dd)
    else:
        active_profile = config["active_profile"]

    profile = config["profiles"][active_profile]
    rules = profile["risk_rules"]
    levels = profile["exposure_levels"]

    if kill_signal:
        status = "KILL"
        exposure = levels["kill"]
    elif vol > rules["volatility_threshold"] or dd < rules["drawdown_threshold"]:
        status = "RISK_OFF"
        exposure = levels["risk_off"]
    else:
        status = "RISK_ON"
        exposure = levels["risk_on"]

    explanation = explain_decision(vol, dd, kill_signal, profile)

    summary = {
        "profile": active_profile,
        "status": status,
        "exposure": exposure,
        "vol_3m": round(vol, 3),
        "drawdown_3m": round(dd, 3),
        "kill_signal": kill_signal,
        "explanation": explanation
    }

    pd.DataFrame([summary]).to_csv(OUTPUT_FILE, index=False)

    # Log to DB
    track(summary)

    return summary


if __name__ == "__main__":
    print(main())
