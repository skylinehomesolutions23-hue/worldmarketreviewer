import os
import pandas as pd
import numpy as np
import warnings

# --- Silence pandas date inference spam (polish, not required)
warnings.filterwarnings(
    "ignore",
    message="Could not infer format"
)

DATA_DIR = "data"
SIGNALS_FILE = "results/all_monthly_signals.csv"
OUTPUT_FILE = "results/walkforward_equity.csv"


def load_price_data(ticker):
    """
    Loads daily price data for a ticker and standardizes columns.
    Expected columns: date, close
    """
    path = os.path.join(DATA_DIR, f"{ticker}.csv")
    if not os.path.exists(path):
        return None

    df = pd.read_csv(path)

    # --- Normalize column names
    df.columns = [c.lower() for c in df.columns]

    # --- Identify date column
    date_col = "date" if "date" in df.columns else df.columns[0]

    # --- Robust date parsing (NO WARNINGS)
    df[date_col] = pd.to_datetime(
        df[date_col].astype(str).str.slice(0, 10),
        errors="coerce"
    )

    # --- Force numeric prices
    df["close"] = pd.to_numeric(df["close"], errors="coerce")

    df = df.dropna(subset=[date_col, "close"])
    df = df.sort_values(date_col)

    return df[[date_col, "close"]].rename(columns={date_col: "date"})


def monthly_return(prices, month):
    """
    Computes return from first to last trading day of a given month.
    """
    m = prices[prices["date"].dt.to_period("M") == month]

    if len(m) < 2:
        return np.nan

    return (m["close"].iloc[-1] / m["close"].iloc[0]) - 1


def main():
    # --- Load signals
    signals = pd.read_csv(SIGNALS_FILE)
    signals["month"] = pd.to_datetime(signals["month"]).dt.to_period("M")

    months = sorted(signals["month"].
