# backtest_monthly.py
import sys
import pandas as pd
from pathlib import Path
from data_loader import load_csv, list_data_files
from save_signals import save_month_signals


def main(end_date_str):
    end_date = pd.to_datetime(end_date_str)

    rows = []

    for file in list_data_files():
        ticker = file.stem.upper()
        df = load_csv(file)

        if "close" not in df.columns or df["close"].isna().all():
            continue

        df = df.dropna(subset=["close"])

        if len(df) < 2:
            continue

        prev = df.iloc[-2]
        last = df.iloc[-1]

        monthly_return = (last["close"] - prev["close"]) / prev["close"]

        rows.append({
            "ticker": ticker,
            "score": monthly_return
        })

    if not rows:
        raise ValueError("No data produced for this month")

    result = pd.DataFrame(rows).sort_values("score", ascending=False)

    save_month_signals(result, end_date_str.replace("-", "_"))


if __name__ == "__main__":
    main(sys.argv[1])
