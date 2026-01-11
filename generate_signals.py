import pandas as pd
import os

INPUT_FILE = "data/monthly_prices.csv"
OUTPUT_FILE = "data/signals.csv"

LOOKBACK = 12  # months


def main():
    df = pd.read_csv(INPUT_FILE, parse_dates=["month"])
    df = df.sort_values(["ticker", "month"])

    # Calculate trailing returns
    df["trail_return"] = (
        df.groupby("ticker")["close"]
        .pct_change(LOOKBACK)
    )

    # Drop rows without enough history
    df = df.dropna(subset=["trail_return"])

    # Rank each month (1 = best)
    df["rank"] = df.groupby("month")["trail_return"] \
                    .rank(ascending=False, method="first")

    signals = df[["month", "ticker", "rank"]].copy()
    signals = signals.rename(columns={"month": "date"})

    os.makedirs("data", exist_ok=True)
    signals.to_csv(OUTPUT_FILE, index=False)

    print(f"✅ Signals saved → {OUTPUT_FILE}")
    print(signals.head())


if __name__ == "__main__":
    main()
