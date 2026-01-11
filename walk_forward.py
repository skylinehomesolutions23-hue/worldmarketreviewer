# walk_forward.py

import os
import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

# -----------------------------
# CPU SAFETY
# -----------------------------
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"


def walk_forward_predict_proba(
    df: pd.DataFrame,
    feature_cols: list,
    target_col: str = "target",
    start_train_size: int = 200,
    step: int = 5,
    window: int = 750,
):
    """
    Walk-forward training & probability prediction.
    Returns pd.Series aligned with df.index
    """

    if target_col not in df.columns:
        raise ValueError("Target column missing")

    X = df[feature_cols].copy()
    y = df[target_col].copy()

    probs = pd.Series(index=df.index, dtype=float)
    scaler = StandardScaler()

    for i in range(start_train_size, len(df), step):
        train_start = max(0, i - window)

        X_train = X.iloc[train_start:i]
        y_train = y.iloc[train_start:i]

        if X_train.isnull().any().any():
            X_train = X_train.dropna()
            y_train = y_train.loc[X_train.index]

        if len(X_train) < start_train_size:
            continue

        X_test = X.iloc[[i]]

        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        model = RandomForestClassifier(
            n_estimators=150,
            max_depth=6,
            min_samples_leaf=10,
            random_state=42,
            n_jobs=1,  # CRITICAL
        )

        model.fit(X_train_scaled, y_train)
        probs.iloc[i] = model.predict_proba(X_test_scaled)[0][1]

    return probs.ffill()
