# backtest_portfolio_monthly.py
import pandas as pd

SIGNALS_FILE = "data/signals.csv"
RETURNS_FILE = "data/forward_returns.csv"
OUT_FILE = "results/portfolio_monthly_equity.csv"

def run_backtest():
    signals = pd.read_csv(SIGNALS_FILE, parse_dates=["date"])
    returns = pd.read_csv(RETURNS_FILE, parse_dates=["date"])

    # Merge signals with forward returns
    df = signals.merge(
        returns,
        on=["date", "ticker", "rank"],
        how="inner"
    )

    # Rank-weighted portfolio
    df["weight"] = df["rank"] / df.groupby("date")["rank"].transform("sum")

    df["weighted_return"] = df["weight"] * df["forward_return"]

    monthly = (
        df.groupby("date")["weighted_return"]
        .sum()
        .add(1)
        .cumprod()
        .reset_index(name="equity")
    )

    monthly.to_csv(OUT_FILE, index=False)
    print(f"📈 Monthly portfolio equity saved → {OUT_FILE}")
    print(monthly.head())

if __name__ == "__main__":
    run_backtest()
