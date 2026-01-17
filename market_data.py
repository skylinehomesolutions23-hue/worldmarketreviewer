# market_data.py
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


# Optional Alpha Vantage (only used if key is present)
ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY", "").strip()


def _as_date_price_df_from_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize OHLC-ish dataframe to columns ['date','price'] using Adj Close if available else Close.
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=["date", "price"])

    df = df.copy()
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


def _require_yfinance():
    if yf is None:
        raise RuntimeError("yfinance is not installed. Add it to requirements.txt")


# -------------------- Source 1: yfinance --------------------

def _yf_download(ticker: str, period: str, interval: str) -> pd.DataFrame:
    _require_yfinance()
    return yf.download(
        ticker,
        period=period,
        interval=interval,
        auto_adjust=False,
        progress=False,
        threads=False,  # helps on servers
        group_by="column",
    )


def _yf_history(ticker: str, period: str, interval: str) -> pd.DataFrame:
    _require_yfinance()
    return yf.Ticker(ticker).history(
        period=period,
        interval=interval,
        auto_adjust=False,
        actions=False,
    )


def _fetch_yfinance(ticker: str, period: str, interval: str, attempts: int = 2) -> pd.DataFrame:
    last_err: Optional[str] = None
    for i in range(1, attempts + 1):
        try:
            df = _yf_download(ticker, period=period, interval=interval)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            last_err = f"yfinance download() failed: {type(e).__name__}: {e}"
        time.sleep(0.5 * i)

        try:
            df = _yf_history(ticker, period=period, interval=interval)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            last_err = f"yfinance history() failed: {type(e).__name__}: {e}"
        time.sleep(0.5 * i)

    raise RuntimeError(last_err or "yfinance returned empty data")


# -------------------- Source 2: Stooq (free, no key) --------------------

def _stooq_symbol(ticker: str) -> str:
    """
    Stooq uses lowercase symbols and for many US equities/ETFs supports '<ticker>.us'
    Examples:
      SPY -> spy.us
      QQQ -> qqq.us
      NVDA -> nvda.us
    """
    t = (ticker or "").strip().lower()
    t = t.replace("^", "")  # indices like ^GSPC won't work on stooq anyway
    if not t:
        return ""

    # If user already passed ".us" etc, keep it
    if "." in t:
        return t

    return f"{t}.us"


def _fetch_stooq_daily(ticker: str) -> pd.DataFrame:
    sym = _stooq_symbol(ticker)
    if not sym:
        raise RuntimeError("stooq: empty symbol")

    url = "https://stooq.com/q/d/l/"
    params = {"s": sym, "i": "d"}  # daily
    r = requests.get(url, params=params, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"stooq HTTP {r.status_code}")

    # Stooq returns CSV: Date,Open,High,Low,Close,Volume
    from io import StringIO
    df = pd.read_csv(StringIO(r.text))
    if df is None or df.empty or "Date" not in df.columns:
        raise RuntimeError("stooq returned empty/invalid CSV")

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    # Prefer Close
    if "Close" not in df.columns:
        raise RuntimeError("stooq CSV missing Close")
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")

    df = df.dropna(subset=["Date", "Close"]).sort_values("Date")
    if df.empty:
        raise RuntimeError("stooq data empty after cleaning")

    out = pd.DataFrame({"date": df["Date"], "price": df["Close"]})
    return out


def _daily_to_monthly_last(daily: pd.DataFrame) -> pd.DataFrame:
    """
    Convert daily ['date','price'] to monthly using last close of each month.
    """
    d = daily.copy()
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    d["price"] = pd.to_numeric(d["price"], errors="coerce")
    d = d.dropna(subset=["date", "price"]).sort_values("date")
    if d.empty:
        return pd.DataFrame(columns=["date", "price"])

    d = d.set_index("date")
    m = d["price"].resample("M").last().dropna()
    return pd.DataFrame({"date": m.index, "price": m.values})


# -------------------- Source 3 (optional): Alpha Vantage --------------------

def _fetch_alpha_vantage_daily(ticker: str) -> pd.DataFrame:
    if not ALPHAVANTAGE_API_KEY:
        raise RuntimeError("alpha vantage key not set")

    t = (ticker or "").upper().strip()
    if not t:
        raise RuntimeError("alpha vantage: empty ticker")

    url = "https://www.alphavantage.co/query"
    params = {
        "function": "TIME_SERIES_DAILY_ADJUSTED",
        "symbol": t,
        "outputsize": "full",
        "apikey": ALPHAVANTAGE_API_KEY,
    }

    r = requests.get(url, params=params, timeout=25)
    if r.status_code != 200:
        raise RuntimeError(f"alpha vantage HTTP {r.status_code}")

    j = r.json()
    # Rate limiting or errors show up here:
    if "Error Message" in j:
        raise RuntimeError(f"alpha vantage error: {j.get('Error Message')}")
    if "Note" in j:
        raise RuntimeError(f"alpha vantage note: {j.get('Note')}")

    key = "Time Series (Daily)"
    if key not in j:
        raise RuntimeError("alpha vantage: missing daily series")

    rows = []
    for ds, vals in j[key].items():
        # prefer adjusted close
        px = vals.get("5. adjusted close") or vals.get("4. close")
        rows.append((ds, px))

    df = pd.DataFrame(rows, columns=["date", "price"])
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df = df.dropna(subset=["date", "price"]).sort_values("date")

    if df.empty:
        raise RuntimeError("alpha vantage returned empty after cleaning")

    return df


# -------------------- Public API --------------------

def get_daily_prices(ticker: str, period: str = "10y") -> pd.DataFrame:
    """
    Returns DataFrame ['date','price'] daily.
    Fallback order: yfinance -> stooq -> alpha vantage (if key)
    """
    t = (ticker or "").upper().strip()
    if not t:
        return pd.DataFrame(columns=["date", "price"])

    # 1) yfinance
    try:
        raw = _fetch_yfinance(t, period=period, interval="1d", attempts=2)
        out = _as_date_price_df_from_ohlc(raw)
        if out is not None and not out.empty:
            return out
    except Exception as e:
        last = f"{e}"

    # 2) stooq
    try:
        out = _fetch_stooq_daily(t)
        if out is not None and not out.empty:
            return out
    except Exception as e:
        last = f"stooq failed: {e}"

    # 3) alpha vantage (optional)
    try:
        out = _fetch_alpha_vantage_daily(t)
        if out is not None and not out.empty:
            return out
    except Exception as e:
        last = f"alpha vantage failed: {e}"

    raise RuntimeError(f"All data sources failed for {t}. Last error: {last}")


def get_monthly_prices(ticker: str, period: str = "max") -> pd.DataFrame:
    """
    Returns DataFrame ['date','price'] monthly.
    Fallback order: yfinance monthly -> stooq daily resampled -> alpha vantage daily resampled (if key)
    """
    t = (ticker or "").upper().strip()
    if not t:
        return pd.DataFrame(columns=["date", "price"])

    # 1) yfinance monthly
    try:
        raw = _fetch_yfinance(t, period=period, interval="1mo", attempts=2)
        out = _as_date_price_df_from_ohlc(raw)
        if out is not None and not out.empty:
            return out
    except Exception as e:
        last = f"{e}"

    # 2) stooq daily -> monthly
    try:
        daily = _fetch_stooq_daily(t)
        out = _daily_to_monthly_last(daily)
        if out is not None and not out.empty:
            return out
    except Exception as e:
        last = f"stooq->monthly failed: {e}"

    # 3) alpha vantage daily -> monthly (optional)
    try:
        daily = _fetch_alpha_vantage_daily(t)
        out = _daily_to_monthly_last(daily)
        if out is not None and not out.empty:
            return out
    except Exception as e:
        last = f"alpha->monthly failed: {e}"

    raise RuntimeError(f"All monthly data sources failed for {t}. Last error: {last}")
