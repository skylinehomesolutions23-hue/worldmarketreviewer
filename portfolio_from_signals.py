import pandas as pd

SIGNALS_FILE = "results/all_monthly_signals.csv"
OUT_FILE = "results/monthly_portfolio.csv"

TOP_N = 5

def main():
    df = pd.read_csv(SIGNALS_FILE)

    df["month"] = pd.to_datetime(df["month"])
    df = df.sort_values(["month", "rank"])

    portfolio = (
        df.groupby("month")
        .head(TOP_N)
        .assign(weight=lambda x: 1 / TOP_N)
        [["month", "ticker", "weight"]]
    )

    portfolio.to_csv(OUT_FILE, index=False)
    print(f"✅ Monthly portfolio saved → {OUT_FILE}")
    print(portfolio.head())

if __name__ == "__main__":
    main()
