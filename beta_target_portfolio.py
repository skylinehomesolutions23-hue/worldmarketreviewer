# beta_target_portfolio.py

import pandas as pd
import numpy as np

EQUITY_FILE = "results/portfolio_equity_final_master.csv"
SPY_FILE = "data/SPY.csv"
OUT_FILE = "results/portfolio_equity_beta_targeted.csv"

ROLLING_WINDOW = 24
TARGET_BETA = 1.0


def load_spy():
    df = pd.read_csv(SPY_FILE)

    # Normalize column names
    df.columns = [c.lower() for c in df.columns]

    # Identify price column
    if "close" in df.columns:
        price_col = "close"
    elif "price" in df.columns:
        price_col = "price"
    else:
        raise ValueError(f"No SPY price column found: {df.columns.tolist()}")

    # Assume first column is date-like
    date_col = df.columns[0]

    df = df[[date_col, price_col]].copy()
    df.columns = ["date", "spy_price"]

    # Parse dates safely
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # Drop non-date rows (metadata, tickers, headers)
    df = df.dropna(subset=["date"])

    # Ensure numeric prices
    df["spy_price"] = pd.to_numeric(df["spy_price"], errors="coerce")
    df = df.dropna(subset=["spy_price"])

    df = df.sort_values("date")
    df["spy_return"] = df["spy_price"].pct_change()

    return df.dropna()


def main():
    eq = pd.read_csv(EQUITY_FILE)
    eq["date"] = pd.to_datetime(eq["date"])
    eq = eq.sort_values("date")

    eq["return"] = eq["equity"].pct_change()

    spy = load_spy()

    df = eq.merge(spy[["date", "spy_return"]], on="date", how="inner")

    # Rolling beta
    cov = df["return"].rolling(ROLLING_WINDOW).cov(df["spy_return"])
    var = df["spy_return"].rolling(ROLLING_WINDOW).var()

    df["beta"] = cov / var
    df["beta"] = df["beta"].clip(0.2, 3.0)

    # Scale exposure
    df["scale"] = TARGET_BETA / df["beta"]
    df["scale"] = df["scale"].clip(0.25, 1.5)

    df["adj_return"] = df["return"] * df["scale"]
    df["equity"] = (1 + df["adj_return"]).cumprod()

    out = df[["date", "equity", "beta", "scale"]]
    out.to_csv(OUT_FILE, index=False)

    print(f"📉 Beta-targeted equity saved → {OUT_FILE}")
    print(out.tail())


if __name__ == "__main__":
    main()
