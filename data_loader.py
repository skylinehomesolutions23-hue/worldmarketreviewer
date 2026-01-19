# data_loader.py
from __future__ import annotations

import os
import pandas as pd

from market_data import get_daily_prices, get_monthly_prices

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MONTHLY_PRICES_FILE = os.path.join(DATA_DIR, "monthly_prices.csv")

# Cache freshness settings (tune as you want)
CACHE_TTL_HOURS_DAILY = 24          # only refetch daily once per day
CACHE_TTL_HOURS_MONTHLY = 24 * 7    # monthly cache ~weekly


def _detect_columns(df: pd.DataFrame):
    cols = {c.lower().strip(): c for c in df.columns}

    ticker_col = None
    for k in ["ticker", "symbol"]:
        if k in cols:
            ticker_col = cols[k]
            break

    date_col = None
    for k in ["date", "month", "timestamp"]:
        if k in cols:
            date_col = cols[k]
            break

    price_col = None
    for k in ["price", "close", "adj close", "adj_close", "value"]:
        if k in cols:
            price_col = cols[k]
            break

    return ticker_col, date_col, price_col


def _load_from_monthly_prices_csv(ticker: str) -> pd.DataFrame | None:
    if not os.path.exists(MONTHLY_PRICES_FILE):
        return None

    try:
        df = pd.read_csv(MONTHLY_PRICES_FILE)
        if df is None or df.empty:
            return None

        if len(df.columns) == 3 and all(str(c).startswith("Unnamed") for c in df.columns):
            df.columns = ["ticker", "date", "price"]

        ticker_col, date_col, price_col = _detect_columns(df)

        if ticker_col is None or date_col is None or price_col is None:
            df = df.copy()
            df.columns = [str(c).strip() for c in df.columns]
            if len(df.columns) >= 3:
                ticker_col, date_col, price_col = df.columns[0], df.columns[1], df.columns[2]
            else:
                return None

        sub = df[df[ticker_col].astype(str).str.upper().str.strip() == ticker].copy()
        if sub.empty:
            return None

        sub[date_col] = pd.to_datetime(sub[date_col], errors="coerce", utc=True)
        sub[price_col] = pd.to_numeric(sub[price_col], errors="coerce")
        sub = sub.dropna(subset=[date_col, price_col])
        if sub.empty:
            return None

        sub = sub.sort_values(date_col).set_index(date_col)
        out = pd.DataFrame({"Price": sub[price_col].astype(float)})
        out.attrs["source"] = "monthly_prices.csv"
        return out

    except Exception:
        return None


def _cache_path(ticker: str, freq: str) -> str:
    safe = ticker.upper().strip().replace("/", "_").replace("^", "")
    return os.path.join(DATA_DIR, f"cache_prices_{safe}_{freq}.csv")


def _is_cache_fresh(df: pd.DataFrame, ttl_hours: int) -> bool:
    if df is None or df.empty:
        return False
    if "fetched_at_utc" not in df.columns:
        return False

    try:
        fetched = pd.to_datetime(df["fetched_at_utc"], errors="coerce", utc=True).dropna()
        if fetched.empty:
            return False
        age = pd.Timestamp.utcnow().tz_localize("UTC") - fetched.max()
        return age <= pd.Timedelta(hours=int(ttl_hours))
    except Exception:
        return False


def _load_cached_prices(ticker: str, freq: str) -> pd.DataFrame | None:
    path = _cache_path(ticker, freq)
    if not os.path.exists(path):
        return None

    try:
        df = pd.read_csv(path)
        if df is None or df.empty:
            return None
        if "date" not in df.columns or "price" not in df.columns:
            return None

        df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df = df.dropna(subset=["date", "price"]).sort_values("date")
        return df if not df.empty else None
    except Exception:
        return None


def _save_cached_prices(ticker: str, freq: str, df: pd.DataFrame) -> None:
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        out = df.copy()
        out["fetched_at_utc"] = pd.Timestamp.utcnow().tz_localize("UTC").isoformat()
        path = _cache_path(ticker, freq)
        out.to_csv(path, index=False)
    except Exception:
        pass


def _live_fetch_daily(ticker: str, period: str = "10y") -> pd.DataFrame:
    raw, src = get_daily_prices(ticker, period=period)
    if raw is None or raw.empty:
        raise RuntimeError("all providers returned empty daily data")

    raw = raw.copy()
    raw["date"] = pd.to_datetime(raw["date"], errors="coerce", utc=True)
    raw["price"] = pd.to_numeric(raw["price"], errors="coerce")
    raw = raw.dropna(subset=["date", "price"]).sort_values("date")
    if raw.empty:
        raise RuntimeError("daily data became empty after cleaning")

    _save_cached_prices(ticker, "daily", raw)

    out = raw.set_index("date")[["price"]].rename(columns={"price": "Price"})
    out.attrs["source"] = src
    return out


def _live_fetch_monthly(ticker: str, period: str = "max") -> pd.DataFrame:
    raw, src = get_monthly_prices(ticker, period=period)
    if raw is None or raw.empty:
        raise RuntimeError("all providers returned empty monthly data")

    raw = raw.copy()
    raw["date"] = pd.to_datetime(raw["date"], errors="coerce", utc=True)
    raw["price"] = pd.to_numeric(raw["price"], errors="coerce")
    raw = raw.dropna(subset=["date", "price"]).sort_values("date")
    if raw.empty:
        raise RuntimeError("monthly data became empty after cleaning")

    _save_cached_prices(ticker, "monthly", raw)

    out = raw.set_index("date")[["price"]].rename(columns={"price": "Price"})
    out.attrs["source"] = src
    return out


def load_stock_data(
    ticker: str,
    lookback_days: int | None = None,
    freq: str = "daily",
    source: str = "auto",   # <-- NEW: allow api.py to pass source preference
) -> pd.DataFrame | None:
    """
    Returns DataFrame indexed by UTC datetime with column ['Price'].

    source:
      - "auto": cache-first, then live, fallback to stale cache
      - "cache": cache-only (fresh or stale); if no cache, returns None
      - "yfinance": live-first (still uses your internal provider selection), fallback to cache

    df.attrs['source'] will be:
      'cache' | 'cache_stale' | provider string from market_data | 'monthly_prices.csv'
    """
    t = ticker.upper().strip()
    os.makedirs(DATA_DIR, exist_ok=True)

    freq = (freq or "daily").lower().strip()
    source = (source or "auto").lower().strip()

    ttl = CACHE_TTL_HOURS_DAILY if freq == "daily" else CACHE_TTL_HOURS_MONTHLY

    # Load cache (if exists)
    cached = _load_cached_prices(t, freq)
    out_cached = None
    fresh = False
    if cached is not None and not cached.empty:
        fresh = _is_cache_fresh(cached, ttl_hours=ttl)
        out_cached = cached.set_index("date")[["price"]].rename(columns={"price": "Price"})
        out_cached.attrs["source"] = "cache" if fresh else "cache_stale"

    # Source=cache: return cache-only (fresh OR stale). If none, return None.
    if source == "cache":
        out = out_cached
        if out is None or out.empty:
            return None
    else:
        out = None

        # auto: if fresh cache exists, use it immediately
        if source == "auto" and out_cached is not None and fresh:
            out = out_cached

        # monthly CSV fallback (dev)
        if out is None and freq == "monthly":
            out = _load_from_monthly_prices_csv(t)

        # live fetch order:
        # - yfinance (live-first): try live first
        # - auto: try live if no fresh cache returned
        if out is None:
            try:
                if freq == "monthly":
                    out = _live_fetch_monthly(t)
                else:
                    out = _live_fetch_daily(t)
            except Exception as e:
                print(f"⚠ {t}: live fetch failed ({freq}): {type(e).__name__}: {e}")

                # fallback to stale cache if we have it
                if out_cached is not None and not out_cached.empty:
                    out = out_cached
                else:
                    return None

    if out is None or out.empty:
        print(f"⚠ {t}: Not enough data (empty)")
        return None

    # lookback trimming
    if lookback_days is not None:
        try:
            cutoff = out.index.max() - pd.Timedelta(days=int(lookback_days))
            out = out[out.index >= cutoff]
        except Exception as e:
            print(f"⚠ {t}: lookback trim failed: {type(e).__name__}: {e}")

    # minimum rows
    if len(out) < 30:
        src = out.attrs.get("source", "?")
        print(f"⚠ {t}: not enough rows after load ({len(out)}) source={src}")
        return None

    return out
