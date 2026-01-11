import pandas as pd
from pathlib import Path

PORTFOLIO_PATH = Path("results/portfolio_equity_FINAL.csv")
ALLOC_PATH = Path("results/capital_allocation_decision.csv")
KILL_PATH = Path("results/kill_switch_status.csv")

OUT_PATH = Path("results/final_exposure_curve.csv")


def main():
    equity = pd.read_csv(PORTFOLIO_PATH, index_col=0, parse_dates=True)
    allocation = pd.read_csv(ALLOC_PATH).iloc[0]["final_allocation"]
    kill = pd.read_csv(KILL_PATH).iloc[0]["kill_switch"]

    exposure = 0.0 if kill else allocation

    equity["effective_equity"] = equity.iloc[:, 0] * exposure
    equity["exposure"] = exposure

    equity.to_csv(OUT_PATH)

    print("Final exposure curve created.")
    print(f"Exposure applied: {exposure}")


if __name__ == "__main__":
    main()
