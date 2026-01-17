# market_data.py
from __future__ import annotations

import pandas as pd

try:
    import yfinance as yf
except Exception:
    yf = None


def _require_yfinance():
    if yf is None:
        raise RuntimeError("yfinance is not installed. Add it to requirements.txt")


def get_daily_prices(ticker: str, period: str = "5y") -> pd.DataFrame:
    """
    Fetch daily prices using yfinance.
    Returns DataFrame with columns: ['date', 'price'] where price = Adj Close if available else Close.
    """
    _require_yfinance()
    t = (ticker or "").upper().strip()
    if not t:
        return pd.DataFrame(columns=["date", "price"])

    df = yf.download(t, period=period, interval="1d", auto_adjust=False, progress=False)
    if df is None or df.empty:
        return pd.DataFrame(columns=["date", "price"])

    df = df.reset_index()

    # yfinance can name columns differently depending on version
    date_col = "Date" if "Date" in df.columns else df.columns[0]
    if "Adj Close" in df.columns:
        price_series = df["Adj Close"]
    elif "Close" in df.columns:
        price_series = df["Close"]
    else:
        # fallback: try last column
        price_series = df.iloc[:, -1]

    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df[date_col], errors="coerce"),
            "price": pd.to_numeric(price_series, errors="coerce"),
        }
    ).dropna()

    return out


def get_monthly_prices(ticker: str, period: str = "max") -> pd.DataFrame:
    """
    Fetch monthly prices using yfinance.
    Returns DataFrame with columns: ['date', 'price'] where price = Adj Close if available else Close.
    """
    _require_yfinance()
    t = (ticker or "").upper().strip()
    if not t:
        return pd.DataFrame(columns=["date", "price"])

    df = yf.download(t, period=period, interval="1mo", auto_adjust=False, progress=False)
    if df is None or df.empty:
        return pd.DataFrame(columns=["date", "price"])

    df = df.reset_index()
    date_col = "Date" if "Date" in df.columns else df.columns[0]
    if "Adj Close" in df.columns:
        price_series = df["Adj Close"]
    elif "Close" in df.columns:
        price_series = df["Close"]
    else:
        price_series = df.iloc[:, -1]

    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df[date_col], errors="coerce"),
            "price": pd.to_numeric(price_series, errors="coerce"),
        }
    ).dropna()

    return out
