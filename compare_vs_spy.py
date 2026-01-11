# compare_vs_spy.py

import pandas as pd

FACTOR_FILE = "results/factor_equity_vol_targeted.csv"
SPY_FILE = "data/monthly/SPY.csv"
OUTPUT_FILE = "results/benchmark_comparison.csv"


def infer_date_column(df):
    for col in df.columns:
        if col.lower() in ["date", "month"]:
            return col
    return None


def infer_price_column(df):
    for col in df.columns:
        if col.lower() in ["close", "adj close", "adj_close", "price"]:
            return col
    return None


def main():
    # --- Factor ---
    factor = pd.read_csv(FACTOR_FILE, parse_dates=["date"])
    factor["ym"] = factor["date"].dt.to_period("M")

    # --- SPY ---
    spy = pd.read_csv(SPY_FILE)

    date_col = infer_date_column(spy)
    price_col = infer_price_column(spy)

    if date_col is None or price_col is None:
        raise RuntimeError(f"SPY columns: {list(spy.columns)}")

    spy[date_col] = pd.to_datetime(spy[date_col])
    spy = spy.sort_values(date_col)

    spy["spy_return"] = spy[price_col].pct_change()
    spy = spy.dropna()

    spy["ym"] = spy[date_col].dt.to_period("M")

    # --- Merge on month ---
    merged = factor.merge(
        spy[["ym", "spy_return"]],
        on="ym",
        how="inner"
    )

    if merged.empty:
        raise RuntimeError("Still no overlapping months — check data ranges")

    merged["spy_equity"] = (1 + merged["spy_return"]).cumprod()

    merged[["date", "equity", "spy_equity"]].to_csv(OUTPUT_FILE, index=False)

    print("📊 Benchmark comparison saved → results/benchmark_comparison.csv")
    print(merged.head())


if __name__ == "__main__":
    main()
