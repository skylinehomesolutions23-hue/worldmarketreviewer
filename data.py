import yfinance as yf
import pandas as pd


def load_data(ticker, start="2000-01-01"):
    """
    Download daily OHLCV data and flatten columns
    """

    df = yf.download(
        ticker,
        start=start,
        auto_adjust=False,
        progress=False
    )

    if df.empty:
        raise ValueError("No data downloaded")

    # 🔑 CRITICAL FIX: flatten yfinance multi-index columns
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.dropna()

    return df
