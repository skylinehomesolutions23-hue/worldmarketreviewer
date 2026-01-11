import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")
OUTPUT_FILE = DATA_DIR / "monthly_prices.csv"


def main():
    rows = []

    for file in DATA_DIR.glob("*.csv"):
        ticker = file.stem.upper()

        try:
            df = pd.read_csv(file)
        except Exception as e:
            print(f"⚠️ Could not read {file.name}: {e}")
            continue

        if df.empty:
            print(f"⚠️ Empty file: {file.name}")
            continue

        if "Price" not in df.columns or "close" not in df.columns:
            print(f"⚠️ Skipping {file.name} (unexpected columns)")
            continue

        # HARD MAP (your schema)
        df["Price"] = pd.to_datetime(df["Price"], errors="coerce")
        df = df.dropna(subset=["Price", "close"])

        if df.empty:
            print(f"⚠️ No valid rows after cleaning: {file.name}")
            continue

        # Month end timestamp
        df["month"] = df["Price"].dt.to_period("M").dt.to_timestamp("M")

        monthly = (
            df.sort_values("Price")
              .groupby("month")["close"]
              .last()
              .reset_index()
        )

        for _, r in monthly.iterrows():
            rows.append({
                "ticker": ticker,
                "month": r["month"],
                "close": float(r["close"])
            })

        print(f"✅ Processed {ticker}")

    if not rows:
        raise RuntimeError("❌ No monthly prices were created")

    out = (
        pd.DataFrame(rows)
        .sort_values(["month", "ticker"])
        .reset_index(drop=True)
    )

    out.to_csv(OUTPUT_FILE, index=False)

    print(f"\n✅ Monthly prices saved → {OUTPUT_FILE}")
    print(out.head())


if __name__ == "__main__":
    main()
