# final_portfolio_engine.py

import pandas as pd
import numpy as np

FILES = {
    "base": "results/portfolio_equity_rank_weighted.csv",
    "vol": "results/portfolio_equity_rank_weighted_vol.csv",
    "beta": "results/portfolio_equity_beta_targeted.csv",
}

OUT_FILE = "results/portfolio_equity_FINAL.csv"


def load_equity(file):
    df = pd.read_csv(file)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # auto-detect equity column
    for c in ["final_equity", "adj_equity", "equity"]:
        if c in df.columns:
            return df[["date", c]].rename(columns={c: "equity"})

    raise ValueError(f"No equity column found in {file}: {df.columns.tolist()}")


def main():
    base = load_equity(FILES["base"])
    vol = load_equity(FILES["vol"]).rename(columns={"equity": "equity_vol"})
    beta = load_equity(FILES["beta"]).rename(columns={"equity": "equity_beta"})

    df = base.merge(vol, on="date", how="left")
    df = df.merge(beta, on="date", how="left")
    df = df.sort_values("date").dropna()

    # Normalize overlays
    for c in ["equity", "equity_vol", "equity_beta"]:
        df[c] = df[c] / df[c].iloc[0]

    # Geometric blend (capital-efficient, robust)
    df["final_equity"] = (
        df["equity"] * df["equity_vol"] * df["equity_beta"]
    ) ** (1 / 3)

    out = df[["date", "final_equity"]]
    out.to_csv(OUT_FILE, index=False)

    print(f"🏁 FINAL portfolio saved → {OUT_FILE}")
    print(out.tail())


if __name__ == "__main__":
    main()
