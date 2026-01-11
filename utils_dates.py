# utils_dates.py
import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")

def latest_available_month():
    spy = pd.read_csv(DATA_DIR / "SPY.csv", usecols=[0])
    dates = pd.to_datetime(spy.iloc[:, 0], format="mixed", errors="coerce").dropna()

    # LAST FULL MONTH ONLY
    latest = dates.max().to_period("M") - 1
    return latest.to_timestamp("M")

def parse_month(month_str):
    return pd.Period(month_str, freq="M").to_timestamp("M")
