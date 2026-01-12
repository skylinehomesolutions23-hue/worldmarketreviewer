# walk_forward.py
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

def walk_forward_predict_proba(df, feature_cols, target_col):
    """
    Simple walk-forward prediction returning probability of "up".
    """
    if len(df) < 10:
        return pd.Series([0.5] * len(df))  # fallback if not enough data

    model = RandomForestClassifier(n_estimators=50, random_state=42)
    train = df.iloc[:-1]
    test = df.iloc[-1:]

    model.fit(train[feature_cols], train[target_col])
    proba = model.predict_proba(test[feature_cols])[:, 1]
    return pd.Series(proba, index=test.index)
