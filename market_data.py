# market_data.py
import io
import os
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import requests

# Simple disk cache (works on Render too)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def _stooq_symbol(ticker: str) -> str:
    """
    Stooq symbols:
      US stocks often: aapl.us, amzn.us, meta.us
      ETFs: spy.us, qqq.us, dia.us
    """
    return f"{ticker.lower()}.us"


def fetch_daily_prices_stooq(ticker: str, timeout: int = 20) -> Optional[pd.DataFrame]:
    """
    Returns DataFrame with columns: ['date','close'] sorted ascending.
    """
    ticker = ticker.upper().strip()
    sym = _stooq_symbol(ticker)
    url = f"https://stooq.com/q/d/l/?s={sym}&i=d"

    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code != 200 or not r.text or "404" in r.text.lower():
            return None

        df = pd.read_csv(io.StringIO(r.text))
        if df is None or df.empty:
            return None

        # Expected columns: Date, Open, High, Low, Close, Volume
        cols = {c.lower(): c for c in df.columns}
        if "date" not in cols or "close" not in cols:
            return None

        df = df.rename(columns={cols["date"]: "date", cols["close"]: "close"})
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = df.dropna(subset=["date", "close"]).sort_values("date")

        if len(df) < 30:
            return None

        return df[["date", "close"]].copy()

    except Exception:
        return None


def daily_to_monthly_price(daily: pd.DataFrame) -> pd.DataFrame:
    """
    Convert daily close to month-end close series: index=datetime, column ['Price']
    """
    x = daily.copy()
    x = x.set_index("date")
    # month-end close = last daily close in the month
    m = x["close"].resample("M").last().dropna()
    out = pd.DataFrame({"Price": m.astype(float)})
    return out


def get_monthly_prices(ticker: str, use_cache: bool = True, cache_days: int = 1) -> Optional[pd.DataFrame]:
    """
    Get monthly prices either from cache or by downloading from Stooq.
    Cache is per-ticker, refreshed daily by default.
    """
    ticker = ticker.upper().strip()
    cache_path = os.path.join(CACHE_DIR, f"stooq_{ticker}.csv")

    if use_cache and os.path.exists(cache_path):
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(cache_path))
            if datetime.now() - mtime < timedelta(days=cache_days):
                df = pd.read_csv(cache_path)
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
                df["Price"] = pd.to_numeric(df["Price"], errors="coerce")
                df = df.dropna(subset=["date", "Price"]).sort_values("date").set_index("date")
                if len(df) >= 10:
                    return df[["Price"]].copy()
        except Exception:
            pass

    daily = fetch_daily_prices_stooq(ticker)
    if daily is None:
        return None

    monthly = daily_to_monthly_price(daily)
    monthly = monthly.reset_index().rename(columns={"date": "date"})

    # write cache
    try:
        monthly.to_csv(cache_path, index=False)
    except Exception:
        pass

    monthly = monthly.set_index("date")
    if len(monthly) < 10:
        return None

    return monthly[["Price"]].copy()
