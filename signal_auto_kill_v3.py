import pandas as pd
from pathlib import Path

RESULTS = Path("results")
DECAY = RESULTS / "decay"

def detect_date_column(df):
    for col in df.columns:
        if "date" in col.lower() or "month" in col.lower():
            return col
    raise ValueError("No date-like column found in returns file")

def main():
    # --- Load decay metrics ---
    ic = pd.read_csv(
        DECAY / "signal_ic_decay.csv",
        parse_dates=["date"]
    )

    hit = pd.read_csv(
        DECAY / "signal_hit_rate.csv",
        parse_dates=["date"]
    )

    # --- Load monthly returns (flexible schema) ---
    returns = pd.read_csv(RESULTS / "monthly_returns.csv")

    date_col = detect_date_column(returns)
    returns[date_col] = pd.to_datetime(returns[date_col])
    returns = returns.rename(columns={date_col: "date"})

    # normalize return column
    if "net_return" not in returns.columns:
        if "return" in returns.columns:
            returns = returns.rename(columns={"return": "net_return"})
        else:
            raise ValueError("No return column found in monthly_returns.csv")

    # --- Load risk snapshot (cross-sectional, no date) ---
    risk = pd.read_csv(
        RESULTS / "integrated_risk_report.csv"
    ).iloc[0]

    # --- Align by month (robust) ---
    for d in [ic, hit, returns]:
        d["year_month"] = d["date"].dt.to_period("M")

    df = (
        ic.merge(hit, on="year_month", how="inner", suffixes=("", "_hit"))
        .merge(
            returns[["year_month", "net_return"]],
            on="year_month",
            how="inner"
        )
        .sort_values("year_month")
    )

    if df.empty:
        raise ValueError("Merged dataframe is empty — check date alignment")

    latest = df.iloc[-1]

    # --- Auto-kill logic ---
    kill = False
    reasons = []

    if latest["ic_mean"] < 0:
        kill = True
        reasons.append("NEGATIVE_IC")

    if latest["rolling_hit_rate"] < 0.52:
        kill = True
        reasons.append("LOW_HIT_RATE")

    if risk["max_dd_6m"] < -0.35:
        kill = True
        reasons.append("EXCESS_DRAWDOWN")

    if latest["net_return"] < 0:
        kill = True
        reasons.append("NEGATIVE_RETURN")

    decision = pd.DataFrame([{
        "date": latest["date"],
        "ic_mean": latest["ic_mean"],
        "ic_slope": latest["ic_slope"],
        "hit_rate": latest["rolling_hit_rate"],
        "latest_return": latest["net_return"],
        "kill_signal": kill,
        "reason": "|".join(reasons) if reasons else "EDGE_HEALTHY"
    }])

    out = DECAY / "signal_auto_kill_v3.csv"
    decision.to_csv(out, index=False)

    print("✅ Auto-kill v3 decision complete")
    print(decision)

if __name__ == "__main__":
    main()
