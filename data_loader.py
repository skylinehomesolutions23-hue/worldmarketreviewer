# data_loader.py
import os
import pandas as pd
from typing import Optional

from market_data import get_monthly_prices

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MONTHLY_PRICES_FILE = os.path.join(DATA_DIR, "monthly_prices.csv")


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


def _load_from_monthly_prices_csv(ticker: str) -> Optional[pd.DataFrame]:
    ticker = ticker.upper().strip()

    if not os.path.exists(MONTHLY_PRICES_FILE):
        return None

    try:
        df = pd.read_csv(MONTHLY_PRICES_FILE)
        if df is None or df.empty:
            return None

        # Handle "no header / unnamed columns" case
        if len(df.columns) == 3 and all(str(c).startswith("Unnamed") for c in df.columns):
            df.columns = ["ticker", "date", "price"]

        ticker_col, date_col, price_col = _detect_columns(df)

        # fallback: assume first 3 columns
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

        sub[date_col] = pd.to_datetime(sub[date_col], errors="coerce")
        sub[price_col] = pd.to_numeric(sub[price_col], errors="coerce")
        sub = sub.dropna(subset=[date_col, price_col])
        if sub.empty:
            return None

        sub = sub.sort_values(date_col).set_index(date_col)
        out = pd.DataFrame({"Price": sub[price_col].astype(float)})

        if len(out) < 10:
            return None

        return out

    except Exception:
        return None


def load_stock_data(ticker: str) -> Optional[pd.DataFrame]:
    """
    Returns monthly price data:
      index: datetime
      columns: ['Price']

    Priority:
      1) local data/monthly_prices.csv (if present)
      2) download from Stooq (Render-friendly)
    """
    ticker = ticker.upper().strip()

    # Try local first
    local = _load_from_monthly_prices_csv(ticker)
    if local is not None:
        return local

    # Fallback to online fetch (works on Render + phone)
    remote = get_monthly_prices(ticker)
    return remote
