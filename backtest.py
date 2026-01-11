import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path("data")
RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(exist_ok=True)

RANKINGS_FILE = RESULTS_DIR / "predictions_ranked.csv"
EQUITY_FILE = RESULTS_DIR / "equity_curve.csv"
PORTFOLIO_FILE = RESULTS_DIR / "portfolio.csv"

TOP_N = 10
INITIAL_CAPITAL = 100_000


def normalize_ticker(name: str) -> str:
    return name.upper().replace(".CSV", "").split("_")[0]


def load_prices():
    series = {}

    for f in DATA_DIR.glob("*.csv"):
        df = pd.read_csv(f)
        df.columns = [c.lower() for c in df.columns]

        if "date" not in df.columns or "close" not in df.columns:
            continue

        ticker = normalize_ticker(f.stem)
