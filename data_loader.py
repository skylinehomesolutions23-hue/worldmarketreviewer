# data_loader.py
from __future__ import annotations

import os
import pandas as pd

from market_data import get_daily_prices, get_monthly_prices

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


def _cache_path(ticker: str, freq: str) -> str:
    safe = ticker.upper().strip().replace("/", "_").replace("^", "")
    return os.path.join(DATA_DIR, f"cache_prices_{safe}_{freq}.csv")


def _load_cached_prices(ticker: str, freq: str) -> pd.DataFrame | None:
    path = _cache_path(ticker, freq)
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path)
        if df is None or df.empty:
            return None
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df = df.dropna(subset=["date", "price"]).sort_values("date")
        if df.empty:
            return None
        return df
    except Exception:
        return None


def _save_cached_prices(ticker: str, freq: str, df: pd.DataFrame) -> None:
    try:
        path = _cache_path(ticker, freq)
        df.to_csv(path, index=False)
    except Exception:
        pass


def _load_live_daily(ticker: str, period: str = "5y") -> pd.DataFrame | None:
    """
    Live DAILY fallback for Render: fetch via yfinance.
    Returns DataFrame indexed by datetime with column ['Price'].
    """
    try:
        raw = get_daily_prices(ticker, period=period)
        if raw is None or raw.empty:
            return None

        raw = raw.copy()
        raw["date"] = pd.to_datetime(raw["date"], errors="coerce")
        raw["price"] = pd.to_numeric(raw["price"], errors="coerce")
        raw = raw.dropna(subset=["date", "price"]).sort_values("date")
        if raw.empty:
            return None

        # cache for stability + fewer calls
        _save_cached_prices(ticker, "daily", raw)

        out = raw.set_index("date")[["price"]].rename(columns={"price": "Price"})
        return out
    except Exception:
        return None


def _load_live_monthly(ticker: str, period: str = "max") -> pd.DataFrame | None:
    """
    Live monthly fallback for Render: fetch from yfinance.
    Returns a DataFrame indexed by datetime with column ['Price'].
    """
    try:
        raw = get_monthly_prices(ticker, period=period)
        if raw is None or raw.empty:
            return None

        raw = raw.copy()
        raw["date"] = pd.to_datetime(raw["date"], errors="coerce")
        raw["price"] = pd.to_numeric(raw["price"], errors="coerce")
        raw = raw.dropna(subset=["date", "price"]).sort_values("date")
        if raw.empty:
            return None

        _save_cached_prices(ticker, "monthly", raw)

        out = raw.set_index("date")[["price"]].rename(columns={"price": "Price"})
        return out
    except Exception:
        return None


def load_stock_data(
    ticker: str,
    lookback_days: int | None = None,
    freq: str = "daily",
) -> pd.DataFrame | None:
    """
    Loads price data for a single ticker.

    freq:
      - "daily"  (recommended; fixes NVDA and makes 252 lookback meaningful)
      - "monthly" (legacy)

    Priority:
      1) cached live data (data/cache_prices_<ticker>_<freq>.csv)
      2) data/monthly_prices.csv (ONLY if freq == "monthly")
      3) live fetch via yfinance

    Returns DataFrame:
      index: datetime
      columns: ['Price']
    """
    t = ticker.upper().strip()
    os.makedirs(DATA_DIR, exist_ok=True)

    freq = (freq or "daily").lower().strip()

    # 1) cache
    cached = _load_cached_prices(t, freq)
    if cached is not None and not cached.empty:
        out = cached.set_index("date")[["price"]].rename(columns={"price": "Price"})
    else:
        out = None

    # 2) optional monthly csv for dev
    if out is None and freq == "monthly":
        out = _load_from_monthly_prices_csv(t)

    # 3) live fetch
    if out is None:
        if freq == "monthly":
            out = _load_live_monthly(t)
        else:
            out = _load_live_daily(t)

    if out is None or out.empty:
        print(f"⚠ {t}: Not enough data")
        return None

    # optional lookback trimming
    if lookback_days is not None:
        # For daily data this is accurate; for monthly it still works.
        cutoff = out.index.max() - pd.Timedelta(days=int(lookback_days))
        out = out[out.index >= cutoff]

    # enforce minimum size
    if len(out) < 30:
        print(f"⚠ {t}: not enough rows ({len(out)})")
        return None

    return out
