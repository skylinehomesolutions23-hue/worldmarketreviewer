# market_data.py
from __future__ import annotations

import pandas as pd
import yfinance as yf


def get_monthly_prices(ticker: str, lookback_years: int = 25) -> pd.DataFrame:
    """
    Fetch monthly close prices for a ticker using yfinance.

    Returns a DataFrame with columns:
      - date (datetime)
      - price (float)
    """
    t = ticker.upper().strip()

    # yfinance monthly history. Use a long lookback so you have enough samples.
    hist = yf.Ticker(t).history(period=f"{lookback_years}y", interval="1mo", auto_adjust=False)

    if hist is None or hist.empty:
        return pd.DataFrame(columns=["date", "price"])

    # Prefer Close; Adj Close may not exist in some feeds
    price_col = "Close" if "Close" in hist.columns else None
    if price_col is None:
        return pd.DataFrame(columns=["date", "price"])

    out = hist[[price_col]].copy()
    out = out.reset_index()

    # yfinance uses "Date" column after reset_index
    date_col = "Date" if "Date" in out.columns else out.columns[0]
    out.rename(columns={date_col: "date", price_col: "price"}, inplace=True)

    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["price"] = pd.to_numeric(out["price"], errors="coerce")
    out = out.dropna(subset=["date", "price"]).sort_values("date")

    return out[["date", "price"]]
