import pandas as pd
from pathlib import Path

DECAY_DIR = Path("results/decay")
OUT_DIR = Path("results/decisions")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    ic = pd.read_csv(DECAY_DIR / "signal_ic_decay.csv", parse_dates=["date"])
    hit = pd.read_csv(DECAY_DIR / "signal_hit_rate.csv", parse_dates=["date"])

    df = ic.merge(hit, on="date", how="inner")

    latest = df.iloc[-1]

    kill = (
        (latest["ic_mean"] < 0) and
        (latest["ic_slope"] < 0) and
        (latest["rolling_hit_rate"] < 0.45)
    )

    decision = pd.DataFrame([{
        "date": latest["date"],
        "ic_mean": latest["ic_mean"],
        "ic_slope": latest["ic_slope"],
        "hit_rate": latest["rolling_hit_rate"],
        "kill_signal": kill,
        "reason": "EDGE_DECAY_DETECTED" if kill else "EDGE_HEALTHY"
    }])

    decision.to_csv(
        OUT_DIR / "signal_lifecycle_decision.csv",
        index=False
    )

    print("✅ Signal lifecycle decision complete")
    print(decision)


if __name__ == "__main__":
    main()
