import pandas as pd
from pathlib import Path

RESULTS_DIR = Path("results")
OUT_DIR = RESULTS_DIR / "portfolio_diagnostics"
OUT_DIR.mkdir(parents=True, exist_ok=True)

ROLLING_WINDOW = 12


def main():
    df = pd.read_csv(
        RESULTS_DIR / "signals_rank_filtered.csv",
        parse_dates=["date"]
    )

    df = df.sort_values(["ticker", "date"])

    df["rank_change"] = df.groupby("ticker")["rank"].diff().abs()

    stability = (
        df.groupby("date")["rank_change"]
        .mean()
        .rolling(ROLLING_WINDOW)
        .mean()
        .dropna()
        .reset_index()
        .rename(columns={"rank_change": "avg_rank_change"})
    )

    stability.to_csv(
        OUT_DIR / "rank_stability.csv",
        index=False
    )

    print("✅ Rank stability analysis complete")
    print(stability.tail())


if __name__ == "__main__":
    main()
