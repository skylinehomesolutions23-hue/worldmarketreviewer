from pathlib import Path
import pandas as pd
import re

OUTPUTS_DIR = Path("outputs")
RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(exist_ok=True)

def extract_month_from_filename(file: Path) -> str:
    """
    Extract YYYY-MM from signals_YYYY_MM_DD.csv
    """
    match = re.search(r"signals_(\d{4})_(\d{2})_", file.name)
    if not match:
        raise ValueError(f"Invalid filename format: {file.name}")
    return f"{match.group(1)}-{match.group(2)}"

def load_all_signal_files() -> pd.DataFrame:
    files = sorted(OUTPUTS_DIR.glob("signals_*.csv"))
    if not files:
        raise FileNotFoundError("No monthly signal files found in outputs/")

    all_rows = []

    for file in files:
        df = pd.read_csv(file)

        if not {"ticker", "score"}.issubset(df.columns):
            raise ValueError(f"{file.name} missing required columns")

        month = extract_month_from_filename(file)

        df = df[["ticker", "score"]].copy()
        df["month"] = month
        df["rank"] = df["score"].rank(ascending=False, method="first")

        all_rows.append(df)

    return pd.concat(all_rows, ignore_index=True)

def main():
    df = load_all_signal_files()
    out = RESULTS_DIR / "all_monthly_signals.csv"
    df.to_csv(out, index=False)
    print(f"✅ Aggregated signals saved → {out}")
    print(df.head(10))

if __name__ == "__main__":
    main()
