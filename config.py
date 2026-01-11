from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = BASE_DIR / "results"

RESULTS_DIR.mkdir(exist_ok=True)

# Portfolio
TOP_N = 10
INITIAL_CAPITAL = 100_000

# Momentum
MOMENTUM_LOOKBACK = 12

# Risk filter
RISK_OFF_IF_AVG_MOMENTUM_BELOW = 0.0
