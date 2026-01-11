from pathlib import Path

PRICE_FILES = {
    "SPY.csv", "QQQ.csv", "IWM.csv", "DIA.csv", "VTI.csv",
    "AAPL.csv", "MSFT.csv", "NVDA.csv", "GOOGL.csv", "AMZN.csv",
    "META.csv", "TSLA.csv", "AVGO.csv", "ASML.csv",
    "GLD.csv", "SLV.csv", "TLT.csv", "UUP.csv",
    "XOM.csv", "CVX.csv",
}

DERIVED_FILES = {
    "monthly_prices.csv",
    "forward_returns.csv",
}

SIGNAL_FILES = {
    "signals.csv",
    "signals_rank_filtered.csv",
    "good_ranks.csv",
    "regime.csv",
}

def classify_file(path: Path):
    name = path.name
    if name in PRICE_FILES:
        return "PRICE"
    if name in DERIVED_FILES:
        return "DERIVED"
    if name in SIGNAL_FILES:
        return "SIGNAL"
    return "RESULT"
