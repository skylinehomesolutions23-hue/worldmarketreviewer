# portfolio_monthly.py
import pandas as pd
from pathlib import Path

SIGNALS_DIR = Path("outputs")
RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(exist_ok=True)


def load_monthly_signals():
    files = sorted(SIGNALS_DIR.glob("signals_*.csv"))
    if not files:
        raise FileNotFoundError("No monthly signal files found in outputs/")

    frames = []
    for f in files:
        month = f.stem.replace("signals_", "")[:7].replace("-", "_")
        df = pd.read_csv(f)

        if "ticker" not in df.columns or "score" not in df.columns:
            raise ValueError(f"{f.name} must contain ticker and score")

        df["month"] = month
        frames.append(df)

    return pd.concat(frames, ignore_index=True)


def build_portfolio(top_n=10):
    signals = load_monthly_signals()

    portfolio = (
        signals.sort_values(["month", "score"], ascending=[True, False])
        .groupby("month")
        .head(top_n)
        .copy()
    )

    portfolio["weight"] = 1.0 / top_n
    return portfolio


def save_portfolio(top_n=10):
    portfolio = build_portfolio(top_n)
    out = RESULTS_DIR / "monthly_portfolio.csv"
    portfolio.to_csv(out, index=False)
    print(f"✅ Saved portfolio → {out}")


if __name__ == "__main__":
    save_portfolio(top_n=10)
