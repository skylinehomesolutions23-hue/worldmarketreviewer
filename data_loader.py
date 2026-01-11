# data_loader.py
from pathlib import Path
import pandas as pd

DATA_DIR = Path("data")


def list_data_files():
    return sorted(DATA_DIR.glob("*.csv"))


def load_csv(file_path):
    df = pd.read_csv(file_path)

    # normalize column names
    df.columns = [c.lower() for c in df.columns]

    if "close" in df.columns:
        # remove commas, force numeric
        df["close"] = (
            df["close"]
            .astype(str)
            .str.replace(",", "", regex=False)
        )
        df["close"] = pd.to_numeric(df["close"], errors="coerce")

    return df
