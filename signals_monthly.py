# signals_monthly.py
def generate_signals(df, lookback=10):
    df = df.copy()

    df["ret"] = df["close"].pct_change()
    df["mom"] = df["ret"].rolling(lookback).mean()

    # signal decided at END of month
    df["signal"] = (df["mom"] > 0).astype(int)

    # position applied NEXT month (no look-ahead)
    df["position"] = df["signal"].shift(1).fillna(0)

    return df
