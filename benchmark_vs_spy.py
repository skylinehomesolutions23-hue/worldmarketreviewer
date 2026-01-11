import pandas as pd
from pathlib import Path

RESULTS_DIR = Path("results")
DATA_DIR = Path("data")


def main():
    equity_file = RESULTS_DIR / "walkforward_equity.csv"
    spy_file = DATA_DIR / "SPY.csv"

    if not equity_file.exists():
        raise FileNotFoundError("walkforward_equity.csv not found")

    if not spy_file.exists():
        raise FileNotFoundError("SPY.csv not found")

    # ======================
    # Load strategy equity
    # ======================
    equity = pd.read_csv(equity_file)

    if not {"month", "equity"}.issubset(equity.columns):
        raise ValueError("walkforward_equity.csv must contain month and equity")

    equity["month"] = (
        pd.to_datetime(equity["month"], errors="coerce")
        .dt.to_period("M")
        .dt.to_timestamp("M")
    )

    equity = equity.dropna(subset=["month"])

    # ======================
    # Load SPY
    # ======================
    spy = pd.read_csv(spy_file)

    # --- Date column detection ---
    date_col = None
    for c in spy.columns:
        if c.lower() in {"date", "datetime", "timestamp"}:
            date_col = c
            break

    if date_col is None:
        date_col = spy.columns[0]  # fallback

    spy[date_col] = pd.to_datetime(spy[date_col], errors="coerce")
    spy = spy.dropna(subset=[date_col])

    if spy.empty:
        raise ValueError("SPY dataframe empty after date parsing")

    # --- Price column detection ---
    price_col = None
    for col in ["Adj Close", "adj_close", "Close", "close"]:
        if col in spy.columns:
            price_col = col
            break

    if price_col is None:
        raise ValueError(f"No price column found in SPY.csv → {list(spy.columns)}")

    # 🔥 FORCE NUMERIC
    spy[price_col] = (
        spy[price_col]
        .astype(str)
        .str.replace(",", "", regex=False)
    )
    spy[price_col] = pd.to_numeric(spy[price_col], errors="coerce")

    if spy[price_col].isna().mean() > 0.2:
        raise ValueError("Too many NaNs in SPY price column after numeric coercion")

    spy = spy.dropna(subset=[price_col])

    # ======================
    # Monthly SPY equity
    # ======================
    spy["month"] = (
        spy[date_col]
        .dt.to_period("M")
        .dt.to_timestamp("M")
    )

    spy_monthly = (
        spy.groupby("month")[price_col]
        .last()
        .pct_change()
        .fillna(0)
        .add(1)
        .cumprod()
        .rename("spy_equity")
        .reset_index()
    )

    # ======================
    # Merge
    # ======================
    df = equity.merge(spy_monthly, on="month", how="inner")

    if df.empty:
        raise ValueError(
            "❌ equity_vs_spy merge is empty\n"
            f"Equity months: {equity['month'].min()} → {equity['month'].max()}\n"
            f"SPY months: {spy_monthly['month'].min()} → {spy_monthly['month'].max()}"
        )

    out = RESULTS_DIR / "equity_vs_spy.csv"
    df.to_csv(out, index=False)

    print(f"📈 Equity vs SPY saved → {out}")
    print(df.head())


if __name__ == "__main__":
    main()
