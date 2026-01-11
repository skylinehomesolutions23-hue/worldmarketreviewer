import pandas as pd
from pathlib import Path

RESULTS_DIR = Path("results")
OUT_FILE = RESULTS_DIR / "portfolio_returns_risk_aware.csv"

def main():
    df = pd.read_csv(
        RESULTS_DIR / "monthly_returns.csv",
        parse_dates=["date"]
    )

    # Safety
    df = df.sort_values("date").copy()

    # Rolling volatility (12-month)
    df["rolling_vol"] = df["net_return"].rolling(12).std()

    # Target volatility (annualized ~10%)
    target_vol = 0.10 / (12 ** 0.5)

    # Risk scaler
    df["risk_scalar"] = target_vol / df["rolling_vol"]
    df["risk_scalar"] = df["risk_scalar"].clip(0.25, 1.5)

    # Risk-adjusted return
    df["risk_adjusted_return"] = df["net_return"] * df["risk_scalar"]

    df.to_csv(OUT_FILE, index=False)

    print("✅ Risk-aware portfolio returns complete")
    print(df.tail())

if __name__ == "__main__":
    main()
