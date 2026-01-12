# feature_engineering.py
import pandas as pd

def build_features(df):
    """
    Builds basic technical features for modeling.
    """
    df = df.copy()
    df['returns'] = df['Price'].pct_change()
    df['ma5'] = df['Price'].rolling(5).mean()
    df['ma10'] = df['Price'].rolling(10).mean()
    df['volatility'] = df['returns'].rolling(10).std()
    df['target'] = (df['Price'].shift(-1) > df['Price']).astype(int)
    df = df.dropna()
    return df
