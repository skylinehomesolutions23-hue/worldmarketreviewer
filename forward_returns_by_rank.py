import pandas as pd
import os

SIGNALS_FILE = "data/signals.csv"
PRICES_FILE = "data/monthly_prices.csv"
OUTPUT_FILE = "data/forward_returns.csv"

FORWARD_MONTHS = 1  # 1-month forward return


def main():
    signals = pd.read_csv(SIGNALS_FILE)
    prices = pd.read_csv(PRICES_FILE, parse_dates=["month"])

    # 🔧 Normalize column names
    signals.columns = signals.columns.str.strip().str.lower()

    if "date" not in signals.columns:
        raise ValueError(f"signals.csv columns found: {signals.columns.tolist()}")

    signals["date"] = pd.to_datetime(signals["date"])

    prices = prices.sort_values(["ticker", "month"])

    # Compute forward returns
    prices["forward_return"] = (
        prices.groupby("ticker")["close"]
        .pct_change(FORWARD_MONTHS)
        .shift(-FORWARD_MONTHS)
    )

    merged = signals.merge(
        prices,
        left_on=["ticker", "date"],
        right_on=["ticker", "month"],
        how="left"
    )

    merged = merged.dropna(subset=["forward_return"])

    out = merged[["date", "ticker", "rank", "forward_return"]]

    os.makedirs("data", exist_ok=True)
    out.to_csv(OUTPUT_FILE, index=False)

    print(f"✅ Forward returns saved → {OUTPUT_FILE}")
    print(out.head())


if __name__ == "__main__":
    main()
