import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")
MIN_VALID_RATIO = 0.95  # at least 95% of rows must be numeric

def normalize_file(path: Path):
    df = pd.read_csv(path)

    price_cols = [
        c for c in df.columns
        if any(k in c.lower() for k in ["adj close", "close", "price"])
    ]

    if not price_cols:
        return

    for col in price_cols:
        cleaned = (
            df[col]
            .astype(str)
            .str.replace(",", "", regex=False)
        )

        numeric = pd.to_numeric(cleaned, errors="coerce")
        valid_ratio = numeric.notna().mean()

        if valid_ratio >= MIN_VALID_RATIO:
            df[col] = numeric
            df.to_csv(path, index=False)
            print(f"✔ Normalized {path.name} [{col}]")
            return

    print(f"⚠ Skipped {path.name} — no clean price column")

def main():
    for file in DATA_DIR.glob("*.csv"):
        normalize_file(file)

if __name__ == "__main__":
    main()
