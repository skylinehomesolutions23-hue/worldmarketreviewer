import pandas as pd
import os

DAILY_DIR = "data"
MONTHLY_DIR = "data/monthly"

os.makedirs(MONTHLY_DIR, exist_ok=True)

def main():
    for file in os.listdir(DAILY_DIR):
        if not file.endswith(".csv"):
            continue

        ticker = file.replace(".csv", "")
        path = os.path.join(DAILY_DIR, file)

        df = pd.read_csv(path)

        if df.empty:
            print(f"⚠️ Empty file: {file}")
            continue

        # -----------------------------
        # FORCE DATE COLUMN DETECTION
        # -----------------------------
        date_col = None

        # 1️⃣ Look for obvious names
        for c in df.columns:
            if c.lower() in ["date", "datetime", "timestamp", "time"]:
                date_col = c
                break

        # 2️⃣ Fallback: first column
        if date_col is None:
            date_col = df.columns[0]

        # Try parsing dates
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

        if df[date_col].isna().all():
            print(f"⚠️ Could not parse dates in {file}")
            continue

        # -----------------------------
        # PRICE COLUMN DETECTION
        # -----------------------------
        price_col = None
        for c in df.columns:
            if c.lower() in ["adj close", "adj_close", "close"]:
                price_col = c
                break

        if price_col is None:
            print(f"⚠️ No price column in {file}")
            continue

        df = df.sort_values(date_col)

        # -----------------------------
        # MONTHLY AGGREGATION
        # -----------------------------
        df["month"] = df[date_col].dt.to_period("M").dt.to_timestamp()
        monthly = (
            df.groupby("month")[price_col]
            .last()
            .reset_index()
        )

        monthly.columns = ["month", "close"]

        out = os.path.join(MONTHLY_DIR, file)
        monthly.to_csv(out, index=False)

        print(f"✅ Built monthly prices: {ticker}")

if __name__ == "__main__":
    main()
