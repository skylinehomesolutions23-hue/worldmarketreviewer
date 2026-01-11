# backtest_rank_filtered.py
import pandas as pd

SIGNALS_FILE = "data/signals_rank_filtered.csv"
RETURNS_FILE = "data/forward_returns.csv"
OUT_FILE = "results/portfolio_equity_rank_filtered.csv"

def main():
    sig = pd.read_csv(SIGNALS_FILE)
    ret = pd.read_csv(RETURNS_FILE)

    df = sig.merge(ret, on=["date", "ticker", "rank"])
    monthly = df.groupby("date")["forward_return"].mean().reset_index()

    monthly["equity"] = (1 + monthly["forward_return"]).cumprod()
    monthly[["date", "equity"]].to_csv(OUT_FILE, index=False)

    print("📈 Rank-filtered equity saved →", OUT_FILE)
    print(monthly.head())

if __name__ == "__main__":
    main()
