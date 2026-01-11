import pandas as pd
import json
from pathlib import Path
from tracker import record

# -----------------------------
# Paths
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CONFIG_FILE = BASE_DIR / "config.json"

RETURNS_FILE = DATA_DIR / "monthly_returns.csv"
RISK_FILE = DATA_DIR / "integrated_risk_report.csv"
KILL_FILE = DATA_DIR / "signal_lifecycle_decision_v3.csv"
OUTPUT_FILE = DATA_DIR / "mobile_summary.csv"


def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def find_date_column(df):
    for col in df.columns:
        if col.lower() in ["date", "month", "period", "timestamp"]:
            return col
    return None


def main():
    # -----------------------------
    # Load config
    # -----------------------------
    config = load_config()

    active_profile = config["active_profile"]
    profile = config["profiles"][active_profile]

    vol_threshold = profile["risk_rules"]["volatility_threshold"]
    dd_threshold = profile["risk_rules"]["drawdown_threshold"]

    exposure_risk_on = profile["exposure_levels"]["risk_on"]
    exposure_risk_off = profile["exposure_levels"]["risk_off"]
    exposure_kill = profile["exposure_levels"]["kill"]

    labels = config["labels"]

    # -----------------------------
    # Validate files
    # -----------------------------
    for f in [RETURNS_FILE, RISK_FILE, KILL_FILE]:
        if not f.exists():
            raise FileNotFoundError(f"Missing required file: {f.name}")

    # -----------------------------
    # Load returns
    # -----------------------------
    returns = pd.read_csv(RETURNS_FILE)
    date_col = find_date_column(returns)

    if date_col:
        returns[date_col] = pd.to_datetime(returns[date_col], errors="coerce")
        returns = returns.sort_values(date_col)
        latest_returns = returns.iloc[-1]
        latest_date = latest_returns[date_col]
    else:
        latest_returns = returns.iloc[-1]
        latest_date = "UNKNOWN"

    # -----------------------------
    # Load risk
    # -----------------------------
    risk = pd.read_csv(RISK_FILE)
    latest_risk = risk.iloc[-1]

    # -----------------------------
    # Load kill switch
    # -----------------------------
    kill = pd.read_csv(KILL_FILE)
    latest_kill = kill.iloc[-1]
    kill_signal = bool(latest_kill.get("kill_signal", False))

    # -----------------------------
    # Decision logic (CONFIG DRIVEN)
    # -----------------------------
    if kill_signal:
        status = labels["kill"]
        exposure = exposure_kill

    elif latest_risk.get("vol_3m", 0) > vol_threshold or latest_risk.get("max_dd_3m", 0) < dd_threshold:
        status = labels["risk_off"]
        exposure = exposure_risk_off

    else:
        status = labels["risk_on"]
        exposure = exposure_risk_on

    # -----------------------------
    # Build summary
    # -----------------------------
    summary = pd.DataFrame([{
        "date": str(latest_date),
        "status": status,
        "recommended_exposure": float(exposure),
        "rolling_net_return": round(float(latest_returns.get("rolling_net_return", 0) or 0), 4),
        "vol_3m": round(float(latest_risk.get("vol_3m", 0) or 0), 3),
        "max_drawdown_3m": round(float(latest_risk.get("max_dd_3m", 0) or 0), 3),
        "tail_correlation": round(float(latest_risk.get("tail_corr", 0) or 0), 3),
        "kill_signal": kill_signal,
        "reason": str(latest_kill.get("reason", "OK")),
        "profile": active_profile
    }])

    summary = summary.replace([float("inf"), float("-inf")], 0).fillna(0)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUTPUT_FILE, index=False)

    result = summary.to_dict(orient="records")[0]

    record(result)

    print("✅ Mobile summary created successfully")
    print(result)

    return result


if __name__ == "__main__":
    main()
