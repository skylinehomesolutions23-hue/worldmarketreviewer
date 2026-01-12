# data_loader.py
from __future__ import annotations

import os
import pandas as pd

from market_data import get_monthly_prices

# Paths resolved relative to this file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MONTHLY_PRICES_FILE = os.path.join(DATA_DIR, "monthly_prices.csv")


def _detect_columns(df: pd.DataFrame):
    """
    Detects column names for ticker/date/price in monthly_prices.csv.
    Supports common variants:
      - ticker / symbol
      - date / month / timestamp
      - price / close / adj_close / value
    """
    cols = {c.lower().strip(): c for c in df.columns}

    # ticker
    ticker_col = None
    for k in ["ticker", "symbol"]:
        if k in cols:
            ticker_col = cols[k]
            break

    # date
    date_col = None
    for k in ["date", "month", "timestamp"]:
        if k in cols:
            date_col = cols[k]
            break

    # price
    price_col = None
    for k in ["price", "close", "adj close", "adj_close", "value"]:
        if k in cols:
            price_col = cols[k]
            break

    return ticker_col, date_col, price_col


def _load_from_monthly_prices_csv(ticker: str) -> pd.DataFrame | None:
    """
    Load from data/monthly_prices.csv if present.
    Returns a DataFrame indexed by datetime with column ['Price'].
    """
    if not os.path.exists(MONTHLY_PRICES_FILE):
        return None

    try:
        df = pd.read_csv(MONTHLY_PRICES_FILE)

        if df is None or df.empty:
            return None

        # If file has no headers and is just 3 columns, set them.
        if len(df.columns) == 3 and all(str(c).startswith("Unnamed") for c in df.columns):
            df.columns = ["ticker", "date", "price"]

        ticker_col, date_col, price_col = _detect_columns(df)

        # If still not detected, assume first three columns are ticker/date/price
        if ticker_col is None or date_col is None or price_col is None:
            df = df.copy()
            df.columns = [str(c).strip() for c in df.columns]
            if len(df.columns) >= 3:
                ticker_col, date_col, price_col = df.columns[0], df.columns[1], df.columns[2]
            else:
                return None

        # Filter ticker
        sub = df[df[ticker_col].astype(str).str.upper().str.strip() == ticker].copy()
        if sub.empty:
            return None

        sub[date_col] = pd.to_datetime(sub[date_col], errors="coerce")
        sub[price_col] = pd.to_numeric(sub[price_col], errors="coerce")
        sub = sub.dropna(subset=[date_col, price_col])
        if sub.empty:
            return None

        sub = sub.sort_values(date_col).set_index(date_col)
        out = pd.DataFrame({"Price": sub[price_col].astype(float)})

        return out

    except Exception:
        return None


def _load_live_monthly(ticker: str) -> pd.DataFrame | None:
    """
    Live monthly fallback for Render: fetch from yfinance.
    Returns a DataFrame indexed by datetime with column ['Price'].
    """
    try:
        raw = get_monthly_prices(ticker)
        if raw is None or raw.empty:
            return None

        raw = raw.copy()
        raw["date"] = pd.to_datetime(raw["date"], errors="coerce")
        raw["price"] = pd.to_numeric(raw["price"], errors="coerce")
        raw = raw.dropna(subset=["date", "price"]).sort_values("date")

        if raw.empty:
            return None

        out = raw.set_index("date")[["price"]].rename(columns={"price": "Price"})
        return out

    except Exception:
        return None


def load_stock_data(ticker: str, lookback_days: int | None = None) -> pd.DataFrame | None:
    """
    Loads monthly price data for a single ticker.

    Priority:
      1) data/monthly_prices.csv (local dev)
      2) live fetch via yfinance (Render/prod)

    Returns DataFrame:
      index: datetime
      columns: ['Price']
    """
    t = ticker.upper().strip()
    os.makedirs(DATA_DIR, exist_ok=True)

    out = _load_from_monthly_prices_csv(t)
    if out is None:
        out = _load_live_monthly(t)

    if out is None or out.empty:
        print(f"⚠ {t}: Not enough data")
        return None

    # enforce minimum size
    if len(out) < 10:
        print(f"⚠ {t}: not enough rows ({len(out)})")
        return None

    # optional lookback: for monthly data, interpret days as roughly days,
    # but if provided we can keep only last N rows as a proxy.
    if lookback_days is not None:
        # approx: 21 trading days per month -> N months ~ lookback_days / 21
        n_months = max(10, int(lookback_days / 21))
        out = out.tail(n_months)

    return out
