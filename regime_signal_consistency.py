import pandas as pd
from pathlib import Path

RESULTS_DIR = Path("results")
DECAY_DIR = RESULTS_DIR / "decay"
DECAY_DIR.mkdir(parents=True, exist_ok=True)


def main():
    df = pd.read_csv(
        RESULTS_DIR / "forward_returns.csv",
        parse_dates=["date"]
    )

    # Market regime proxy
    df["regime"] = df["forward_return"].apply(
        lambda x: "UP" if x > 0 else "DOWN"
    )

    regime_stats = (
        df.groupby("regime")["forward_return"]
        .agg(["mean", "std", "count"])
        .reset_index()
    )

    regime_stats.to_csv(
        DECAY_DIR / "regime_signal_consistency.csv",
        index=False
    )

    print("✅ Regime signal consistency analysis complete")
    print(regime_stats)


if __name__ == "__main__":
    main()
