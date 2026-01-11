import pandas as pd
import numpy as np
from pathlib import Path

RESULTS_DIR = Path("results")
DECAY_DIR = RESULTS_DIR / "decay"
DECAY_DIR.mkdir(parents=True, exist_ok=True)

ROLLING_WINDOW = 36
MIN_OBS = 24


def compute_ic(signal, returns):
    return signal.corr(returns, method="spearman")


def main():
    # Load signal ranks
    signals = pd.read_csv(
        RESULTS_DIR / "signals_rank_filtered.csv",
        parse_dates=["date"]
    ).rename(columns={"rank": "signal"})

    # Load forward returns (drop rank to avoid collision)
    fwd = (
        pd.read_csv(
            RESULTS_DIR / "forward_returns.csv",
            parse_dates=["date"]
        )
        .drop(columns=["rank"], errors="ignore")
    )

    # Merge
    df = (
        signals
        .merge(fwd, on=["date", "ticker"], how="inner")
        .dropna(subset=["signal", "forward_return"])
        .sort_values("date")
    )

    unique_dates = df["date"].drop_duplicates().values

    ic_series, dates = [], []

    for i in range(ROLLING_WINDOW, len(unique_dates)):
        window = df[
            (df["date"] >= unique_dates[i - ROLLING_WINDOW]) &
            (df["date"] <= unique_dates[i])
        ]

        if len(window) < MIN_OBS:
            continue

        ic_series.append(
            compute_ic(window["signal"], window["forward_return"])
        )
        dates.append(unique_dates[i])

    ic_df = pd.DataFrame({
        "date": dates,
        "rolling_ic": ic_series
    })

    ic_df["ic_mean"] = ic_df["rolling_ic"].rolling(12).mean()
    ic_df["ic_slope"] = ic_df["rolling_ic"].rolling(12).apply(
        lambda x: np.polyfit(range(len(x)), x, 1)[0] if len(x) >= 6 else np.nan
    )

    ic_df.to_csv(DECAY_DIR / "signal_ic_decay.csv", index=False)

    print("✅ Signal decay analysis complete")
    print(ic_df.tail())


if __name__ == "__main__":
    main()
