# regime_filter.py
import pandas as pd

SPY_FILE = "data/SPY.csv"
EQUITY_FILE = "results/portfolio_monthly_equity.csv"
OUT_FILE = "data/regime.csv"

def main():
    spy = pd.read_csv(SPY_FILE)
    eq = pd.read_csv(EQUITY_FILE, parse_dates=["date"])

    # --- SELECT PRICE COLUMN ---
    if "close" in spy.columns:
        price = spy["close"]
    elif "Price" in spy.columns:
        price = spy["Price"]
    else:
        raise ValueError("SPY.csv must contain 'close' or 'Price'")

    # --- FORCE NUMERIC & CLEAN ---
    price = pd.to_numeric(price, errors="coerce")
    price = price.dropna().reset_index(drop=True)

    # --- ALIGN WITH PORTFOLIO ---
    n = min(len(price), len(eq))
    price = price.iloc[:n]
    dates = eq["date"].iloc[:n].reset_index(drop=True)

    df = pd.DataFrame({
        "date": dates,
        "price": price.values
    })

    # --- REGIME SIGNAL ---
    df["ma10"] = df["price"].rolling(10).mean()
    df["pct_from_ma"] = (df["price"] - df["ma10"]) / df["ma10"]

    def classify(x):
        if x > 0.02:
            return 1.0   # risk-on
        elif x < -0.02:
            return 0.0   # risk-off
        else:
            return 0.5   # neutral

    df["exposure"] = df["pct_from_ma"].apply(classify)
    df = df.dropna()

    df[["date", "exposure"]].to_csv(OUT_FILE, index=False)

    print(f"✅ Regime file saved → {OUT_FILE}")
    print(df.tail())

if __name__ == "__main__":
    main()
