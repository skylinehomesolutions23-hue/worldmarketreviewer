import pandas as pd
from pathlib import Path
from tracker import record

# -----------------------------
# Config (cross-platform paths)
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

RETURNS_FILE = DATA_DIR / "monthly_returns.csv"
RISK_FILE = DATA_DIR / "integrated_risk_report.csv"
KILL_FILE = DATA_DIR / "signal_lifecycle_decision_v3.csv"

OUTPUT_FILE = DATA_DIR / "mobile_summary.csv"


def find_date_column(df):
    """Find a usable date column or fall back to index"""
    for col in df.columns:
        if col.lower() in ["date", "month", "period", "timestamp"]:
            return col
    return None


def main():
    # -----------------------------
    # Validate inputs
    # -----------------------------
    for f in [RETURNS_FILE, RISK_FILE, KILL_FILE]:
        if not f.exists():
            raise FileNotFoundError(f"Missing required file: {f.name}")

    # -----------------------------
    # Load monthly returns
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
    # Load risk snapshot
    # -----------------------------
    risk = pd.read_csv(RISK_FILE)
    latest_risk = risk.iloc[-1]

    # -----------------------------
    # Load kill switch
    # -----------------------------
    kill = pd.read_csv(KILL_FILE)
    kill_date_col = find_date_column(kill)

    if kill_date_col:
        kill[kill_date_col] = pd.to_datetime(kill[kill_date_col], errors="coerce")
        kill = kill.sort_values(kill_date_col)
        latest_kill = kill.iloc[-1]
    else:
        latest_kill = kill.iloc[-1]

    # -----------------------------
    # Decision logic
    # -----------------------------
    kill_signal = bool(latest_kill.get("kill_signal", False))

    if kill_signal:
        status = "KILL"
        exposure = 0.0
    elif latest_risk.get("vol_3m", 0) > 0.30 or latest_risk.get("max_dd_3m", 0) < -0.35:
        status = "RISK_OFF"
        exposure = 0.25
    else:
        status = "RISK_ON"
        exposure = 1.0

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
        "reason": str(latest_kill.get("reason", "OK"))
    }])

    # -----------------------------
    # Make JSON-safe
    # -----------------------------
    summary = summary.replace([float("inf"), float("-inf")], 0)
    summary = summary.fillna(0)

    # -----------------------------
    # Save CSV
    # -----------------------------
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUTPUT_FILE, index=False)

    # -----------------------------
    # Convert to dict
    # -----------------------------
    result = summary.to_dict(orient="records")[0]

    # -----------------------------
    # Record to database/logger
    # -----------------------------
    try:
        record(result)
    except Exception as e:
        # Do NOT crash the pipeline if database isn't ready
        print(f"⚠️ Warning: record() failed: {e}")

    print("✅ Mobile summary created successfully")
    print(result)

    return result


if __name__ == "__main__":
    main()
