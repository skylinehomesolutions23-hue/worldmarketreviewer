# market_data.py
from __future__ import annotations

import time
from typing import Optional, Tuple

import pandas as pd
import requests

try:
    import yfinance as yf
except Exception:
    yf = None


def _require_yfinance():
    if yf is None:
        raise RuntimeError("yfinance is not installed. Add it to requirements.txt")


def _as_date_price_df_from_yf(raw: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize yfinance output into DataFrame columns: ['date','price'].
    """
    if raw is None or raw.empty:
        return pd.DataFrame(columns=["date", "price"])

    df = raw.copy().reset_index()

    # yfinance sometimes names the index/col differently
    date_col = "Date" if "Date" in df.columns else df.columns[0]

    if "Adj Close" in df.columns:
        price_series = df["Adj Close"]
    elif "Close" in df.columns:
        price_series = df["Close"]
    else:
        price_series = df.iloc[:, -1]

    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df[date_col], errors="coerce", utc=True),
            "price": pd.to_numeric(price_series, errors="coerce"),
        }
    ).dropna()

    return out


def _yf_download(ticker: str, period: str, interval: str) -> pd.DataFrame:
    _require_yfinance()
    return yf.download(
        ticker,
        period=period,
        interval=interval,
        auto_adjust=False,
        progress=False,
        threads=False,  # important on servers
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


def _fetch_yfinance(ticker: str, period: str, interval: str, attempts: int = 3) -> Tuple[pd.DataFrame, str]:
    last_err: Optional[str] = None

    for i in range(1, attempts + 1):
        # Try download()
        try:
            raw = _yf_download(ticker, period=period, interval=interval)
            df = _as_date_price_df_from_yf(raw)
            if not df.empty:
                return df.sort_values("date"), "yfinance"
        except Exception as e:
            last_err = f"yfinance download() failed: {type(e).__name__}: {e}"

        time.sleep(0.6 * i)

        # Try history()
        try:
            raw = _yf_history(ticker, period=period, interval=interval)
            df = _as_date_price_df_from_yf(raw)
            if not df.empty:
                return df.sort_values("date"), "yfinance"
        except Exception as e:
            last_err = f"yfinance history() failed: {type(e).__name__}: {e}"

        time.sleep(0.6 * i)

    raise RuntimeError(last_err or "yfinance returned empty data")


def _stooq_symbol(ticker: str) -> str:
    """
    Stooq commonly supports US tickers as '<ticker>.us' in lowercase.
    """
    t = (ticker or "").strip().lower().replace("^", "")
    if not t:
        return ""
    if "." in t:
        return t
    return f"{t}.us"


def _fetch_stooq_daily(ticker: str) -> Tuple[pd.DataFrame, str]:
    sym = _stooq_symbol(ticker)
    if not sym:
        raise RuntimeError("stooq: empty symbol")

    url = "https://stooq.com/q/d/l/"
    params = {"s": sym, "i": "d"}  # daily CSV

    r = requests.get(url, params=params, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"stooq HTTP {r.status_code}")

    from io import StringIO
    df = pd.read_csv(StringIO(r.text))
    if df is None or df.empty or "Date" not in df.columns:
        raise RuntimeError("stooq returned empty/invalid CSV")

    if "Close" not in df.columns:
        raise RuntimeError("stooq CSV missing Close")

    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df["Date"], errors="coerce", utc=True),
            "price": pd.to_numeric(df["Close"], errors="coerce"),
        }
    ).dropna()

    out = out.sort_values("date")
    if out.empty:
        raise RuntimeError("stooq data empty after cleaning")

    return out, "stooq"


def _daily_to_monthly_last(daily: pd.DataFrame) -> pd.DataFrame:
    """
    Convert daily ['date','price'] to monthly by taking the last price in each month.
    """
    d = daily.copy()
    d["date"] = pd.to_datetime(d["date"], errors="coerce", utc=True)
    d["price"] = pd.to_numeric(d["price"], errors="coerce")
    d = d.dropna(subset=["date", "price"]).sort_values("date")
    if d.empty:
        return pd.DataFrame(columns=["date", "price"])

    d = d.set_index("date")
    m = d["price"].resample("M").last().dropna()
    return pd.DataFrame({"date": m.index, "price": m.values})


def get_daily_prices(ticker: str, period: str = "10y") -> Tuple[pd.DataFrame, str]:
    """
    Returns (df, source) where df has columns ['date','price'] (UTC).
    Source order: yfinance -> stooq
    """
    t = (ticker or "").upper().strip()
    if not t:
        return pd.DataFrame(columns=["date", "price"]), "none"

    # 1) yfinance
    try:
        return _fetch_yfinance(t, period=period, interval="1d", attempts=3)
    except Exception as e_yf:
        last = f"{e_yf}"

    # 2) stooq
    try:
        return _fetch_stooq_daily(t)
    except Exception as e_st:
        last = f"stooq failed: {e_st}"

    raise RuntimeError(f"All sources failed for {t}. Last error: {last}")


def get_monthly_prices(ticker: str, period: str = "max") -> Tuple[pd.DataFrame, str]:
    """
    Returns (df, source) monthly (UTC).
    Source order: yfinance monthly -> stooq daily resampled to monthly
    """
    t = (ticker or "").upper().strip()
    if not t:
        return pd.DataFrame(columns=["date", "price"]), "none"

    # 1) yfinance monthly
    try:
        df, src = _fetch_yfinance(t, period=period, interval="1mo", attempts=3)
        return df, src
    except Exception as e_yf:
        last = f"{e_yf}"

    # 2) stooq daily -> monthly
    try:
        daily, _ = _fetch_stooq_daily(t)
        monthly = _daily_to_monthly_last(daily)
        if monthly.empty:
            raise RuntimeError("stooq monthly resample produced empty")
        return monthly, "stooq"
    except Exception as e_st:
        last = f"stooq->monthly failed: {e_st}"

    raise RuntimeError(f"All monthly sources failed for {t}. Last error: {last}")
