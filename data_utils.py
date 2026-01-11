import pandas as pd
import numpy as np
from typing import Tuple


# -----------------------------
# Core inference utilities
# -----------------------------

def infer_date_column(df: pd.DataFrame) -> Tuple[pd.DataFrame, str]:
    """
    Infer the date axis.
    Priority:
    1) Datetime-like index
    2) Column with 'date' in name
    3) Column convertible to datetime with high success rate
    """
    # 1) Index already datetime
    if isinstance(df.index, pd.DatetimeIndex):
        return df.copy(), "__index__"

    df = df.copy()

    # 2) Explicit date-like column name
    for col in df.columns:
        if "date" in col.lower():
            parsed = pd.to_datetime(df[col], errors="coerce")
            if parsed.notna().sum() > 0.9 * len(parsed):
                df[col] = parsed
                return df, col

    # 3) Try all columns for datetime coercion
    best_col = None
    best_score = 0

    for col in df.columns:
        parsed = pd.to_datetime(df[col], errors="coerce")
        score = parsed.notna().sum()
        if score > best_score:
            best_score = score
            best_col = col

    if best_col is None or best_score < 0.5 * len(df):
        raise ValueError("Could not infer date column or index")

    df[best_col] = pd.to_datetime(df[best_col], errors="coerce")
    return df, best_col


def infer_price_column(df: pd.DataFrame) -> str:
    """
    Infer the price column.
    Priority:
    1) Common price names
    2) Highest-variance numeric column
    """
    price_candidates = [
        "adj close", "adj_close", "adjusted close",
        "close", "price", "last", "px_last"
    ]

    lower_map = {col.lower(): col for col in df.columns}

    # 1) Named price columns
    for name in price_candidates:
        if name in lower_map:
            return lower_map[name]

    # 2) Fallback: numeric column with highest variance
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if not numeric_cols:
        raise ValueError("No numeric columns available to infer price")

    variances = df[numeric_cols].var()
    return variances.idxmax()


# -----------------------------
# Public loader
# -----------------------------

def load_price_series(
    path: str,
    rename_price: str = "price"
) -> pd.Series:
    """
    Load ANY CSV containing a price series and return:
    - DatetimeIndex
    - Single standardized price Series
    """
    df = pd.read_csv(path)

    df, date_col = infer_date_column(df)

    if date_col == "__index__":
        df.index = pd.to_datetime(df.index)
    else:
        df = df.set_index(date_col)

    df = df.sort_index()
    df = df[~df.index.isna()]

    price_col = infer_price_column(df)
    price = df[price_col].astype(float)

    price.name = rename_price
    return price


def load_price_dataframe(
    path: str,
    rename_price: str = "price"
) -> pd.DataFrame:
    """
    Same as load_price_series, but returns a DataFrame
    """
    series = load_price_series(path, rename_price)
    return series.to_frame()
