import pandas as pd
import numpy as np
from pathlib import Path

# =========================
# FILES
# =========================
RANK_WEIGHTED_FILE = "results/portfolio_equity_rank_weighted.csv"
REGIME_FILE = "data/regime.csv"
OUTPUT_FILE = "results/portfolio_equity_final_master.csv"

# =========================
# SETTINGS
# =========================
TARGET_VOL = 0.12
VOL_WINDOW = 12
MONTHS_PER_YEAR = 12
MAX_LEVERAGE = 1.5


def main():
    # -------------------------
    # Load rank-weighted equity
    # -------------------------
    eq = pd.read_csv(RANK_WEIGHTED_FILE, parse_dates=["date"]).sort_values("date")
    eq["ret"] = eq["equity"].pct_change()

    # -------------------------
    # Load regime exposure
    # -------------------------
    reg = pd.read_csv(REGIME_FILE, parse_dates=["date"])
    reg = reg[["date", "exposure"]]

    # -------------------------
    # Merge
    # -------------------------
    df = eq.merge(reg, on="date", how="left")
    df["exposure"] = df["exposure"].fillna(1.0)

    # -------------------------
    # Apply regime filter
    # -------------------------
    df["regime_ret"] = df["ret"] * df["exposure"]

    # -------------------------
    # Vol targeting
    # -------------------------
    df["vol"] = (
        df["regime_ret"]
        .rolling(VOL_WINDOW)
        .std()
        * np.sqrt(MONTHS_PER_YEAR)
    )

    df["scale"] = TARGET_VOL / df["vol"]
    df["scale"] = df["scale"].clip(lower=0.0, upper=MAX_LEVERAGE)

    # -------------------------
    # Final adjusted returns
    # -------------------------
    df["adj_ret"] = df["regime_ret"] * df["scale"]

    # -------------------------
    # Final equity curve
    # -------------------------
    df["equity"] = (1 + df["adj_ret"]).cumprod()

    # -------------------------
    # Save
    # -------------------------
    out = df[[
        "date",
        "equity",
        "adj_ret",
        "exposure",
        "scale",
        "vol"
    ]].dropna()

    Path(OUTPUT_FILE).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUTPUT_FILE, index=False)

    print(f"🚀 FINAL MASTER EQUITY saved → {OUTPUT_FILE}")
    print(out.tail())


if __name__ == "__main__":
    main()
