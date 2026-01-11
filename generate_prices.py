import pandas as pd
import yfinance as yf
from pathlib import Path

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

RANKING_FILE = "full_universe_rankings.csv"
START_DATE = "2005-01-01"

def get_tickers(df: pd.DataFrame):
    # Try common names first
    for col in ["ticker", "symbol", "Ticker", "Symbol"]:
        if col in df.columns:
            return df[col].dropna().unique().tolist()

    # Fallback: first column
    return df.iloc[:, 0].dropna().unique().tolist()

def main():
    df = pd.read_csv(RANKING_FILE)
    tickers = get_tickers(df)

    if not tickers:
        raise ValueError("❌ No tickers found in ranking file")

    print(f"Downloading {len(tickers)} tickers...")

    for t in tickers:
        try:
            data = yf.download(t, start=START_DATE, progress=False)
            if data.empty:
                print(f"⚠ No data for {t}")
                continue

            out = data[["Close"]].rename(columns={"Close": "close"})
            out.index.name = "date"
            out.to_csv(DATA_DIR / f"{t}.csv")

        except Exception as e:
            print(f"❌ {t}: {e}")

    print("✅ Price generation complete")

if __name__ == "__main__":
    main()
