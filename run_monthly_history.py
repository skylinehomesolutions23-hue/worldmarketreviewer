import pandas as pd
from pathlib import Path
import subprocess
import sys

DATA_DIR = Path("data")
PYTHON = sys.executable


def list_available_months():
    """
    Scan all CSVs in /data.
    Assume FIRST column is date (robust to any column naming).
    Return sorted YYYY-MM strings.
    """
    months = set()

    for file in DATA_DIR.glob("*.csv"):
        try:
            df = pd.read_csv(file)
        except Exception:
            continue

        if df.shape[1] < 2:
            continue

        # FIRST column = date
        date_col = df.columns[0]
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=[date_col])

        if df.empty:
            continue

        df["month"] = df[date_col].dt.to_period("M")
        months.update(df["month"].astype(str).tolist())

    if not months:
        raise ValueError("No valid date data found in CSV files")

    return sorted(months)


def main():
    months = list_available_months()

    print(f"📆 Running {len(months)} months")

    for month in months:
        print(f"\n▶ Running {month}")
        subprocess.run(
            [PYTHON, "run_monthly.py", "--month", month],
            check=True
        )


if __name__ == "__main__":
    main()
