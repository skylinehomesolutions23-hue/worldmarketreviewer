# market_data.py (SOURCE-AWARE)
from __future__ import annotations

import os
import time
from typing import Optional, Tuple

import pandas as pd
import requests

try:
    import yfinance as yf
except Exception:
    yf = None

ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY", "").strip()


def _as_date_price_df_from_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["date", "price"])
    df = df.reset_index()
    date_col = "Date" if "Date" in df.columns else df.columns[0]
    price = df["Adj Close"] if "Adj Close" in df.columns else df["Close"]
    return pd.DataFrame({
        "date": pd.to_datetime(df[date_col], errors="coerce"),
        "price": pd.to_numeric(price, errors="coerce"),
    }).dropna()


# ---------- yfinance ----------
def _fetch_yfinance(ticker: str, period: str, interval: str) -> Tuple[pd.DataFrame, str]:
    if yf is None:
        raise RuntimeError("yfinance not installed")

    for fn in ("download", "history"):
        try:
            if fn == "download":
                raw = yf.download(ticker, period=period, interval=interval, progress=False)
            else:
                raw = yf.Ticker(ticker).history(period=period, interval=interval)
            df = _as_date_price_df_from_ohlc(raw)
            if not df.empty:
                return df, "yfinance"
        except Exception:
            pass
        time.sleep(0.5)

    raise RuntimeError("yfinance failed")


# ---------- stooq ----------
def _fetch_stooq_daily(ticker: str) -> Tuple[pd.DataFrame, str]:
    sym = f"{ticker.lower()}.us"
    url = "https://stooq.com/q/d/l/"
    r = requests.get(url, params={"s": sym, "i": "d"}, timeout=20)
    if r.status_code != 200:
        raise RuntimeError("stooq HTTP error")

    from io import StringIO
    df = pd.read_csv(StringIO(r.text))
    if df.empty or "Close" not in df.columns:
        raise RuntimeError("stooq empty")

    df["date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["price"] = pd.to_numeric(df["Close"], errors="coerce")
    df = df.dropna(subset=["date", "price"])
    if df.empty:
        raise RuntimeError("stooq cleaned empty")

    return df[["date", "price"]], "stooq"


# ---------- alpha vantage ----------
def _fetch_alpha_vantage_daily(ticker: str) -> Tuple[pd.DataFrame, str]:
    if not ALPHAVANTAGE_API_KEY:
        raise RuntimeError("alpha vantage key missing")

    url = "https://www.alphavantage.co/query"
    r = requests.get(url, params={
        "function": "TIME_SERIES_DAILY_ADJUSTED",
        "symbol": ticker,
        "outputsize": "full",
        "apikey": ALPHAVANTAGE_API_KEY,
    }, timeout=25)

    j = r.json()
    series = j.get("Time Series (Daily)")
    if not series:
        raise RuntimeError("alpha vantage empty")

    rows = [(k, v.get("5. adjusted close")) for k, v in series.items()]
    df = pd.DataFrame(rows, columns=["date", "price"])
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df = df.dropna()
    if df.empty:
        raise RuntimeError("alpha vantage cleaned empty")

    return df.sort_values("date"), "alphavantage"


# ---------- public ----------
def get_daily_prices(ticker: str, period: str = "10y") -> Tuple[pd.DataFrame, str]:
    last_err = None

    for fn in (_fetch_yfinance, _fetch_stooq_daily, _fetch_alpha_vantage_daily):
        try:
            df, src = fn(ticker) if fn != _fetch_yfinance else fn(ticker, period, "1d")
            if not df.empty:
                return df, src
        except Exception as e:
            last_err = f"{fn.__name__}: {e}"

    raise RuntimeError(f"All sources failed for {ticker}. Last error: {last_err}")
