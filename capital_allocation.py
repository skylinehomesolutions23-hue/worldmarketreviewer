import pandas as pd
import numpy as np
from pathlib import Path

RESULTS_DIR = Path("results")
OUT_DIR = RESULTS_DIR
OUT_DIR.mkdir(parents=True, exist_ok=True)

TOP_N = 10
MAX_WEIGHT = 0.15   # safety cap per name


def main():
    signals = pd.read_csv(
        RESULTS_DIR / "signals_rank_filtered.csv",
        parse_dates=["date"]
    )

    # Sort by rank (lower rank = stronger)
    signals = signals.sort_values(["date", "rank"])

    # Select top N per date
    top = signals.groupby("date").head(TOP_N).copy()

    # Inverse-rank weighting
    top["raw_weight"] = 1 / top["rank"]

    # Normalize weights per date
    top["weight"] = top.groupby("date")["raw_weight"].transform(
        lambda x: x / x.sum()
    )

    # Apply max weight cap
    top["weight"] = top["weight"].clip(upper=MAX_WEIGHT)

    # Re-normalize after caps
    top["weight"] = top.groupby("date")["weight"].transform(
        lambda x: x / x.sum()
    )

    weights = top[["date", "ticker", "weight"]]

    weights.to_csv(OUT_DIR / "portfolio_weights.csv", index=False)

    print("✅ Capital allocation complete")
    print(weights.tail())


if __name__ == "__main__":
    main()
