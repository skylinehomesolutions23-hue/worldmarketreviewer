# walk_forward.py
from __future__ import annotations

from typing import List, Optional
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from model_cache import get_cached_model, set_cached_model


def _train_model(
    train_df: pd.DataFrame,
    feature_cols: List[str],
    target_col: str,
) -> RandomForestClassifier:
    model = RandomForestClassifier(
        n_estimators=200,
        random_state=42,
        n_jobs=-1,
        max_depth=None,
        min_samples_split=2,
        min_samples_leaf=1,
    )
    model.fit(train_df[feature_cols], train_df[target_col])
    return model


def _predict_prob_up(
    model: RandomForestClassifier,
    test_df: pd.DataFrame,
    feature_cols: List[str],
) -> float:
    proba = model.predict_proba(test_df[feature_cols])

    # If model saw only one class
    if proba.shape[1] == 1:
        cls = int(model.classes_[0])
        return 1.0 if cls == 1 else 0.0

    class_to_index = {int(c): i for i, c in enumerate(model.classes_)}
    idx = class_to_index.get(1, 1)
    return float(proba[0, idx])


def walk_forward_predict_proba(
    df: pd.DataFrame,
    feature_cols: List[str],
    target_col: str,
    *,
    ticker: Optional[str] = None,
    horizon_days: int = 5,          # <-- NEW (accepted for compatibility + cache key)
    retrain: bool = True,
    lookback: int = 252,
    min_train: int = 60,
) -> pd.Series:
    """
    Predict probability of "up" for the last row.

    Notes:
    - horizon_days is used only to keep cache distinct per horizon
      (because target definition changes with horizon).
    """
    horizon_days = max(1, int(horizon_days))

    if df is None or len(df) < 2:
        idx = df.index[-1:] if df is not None and len(df) else None
        return pd.Series([0.5], index=idx)

    if len(df) < max(10, min_train + 1):
        return pd.Series([0.5], index=df.iloc[-1:].index)

    end_idx = len(df) - 1
    start_idx = max(0, end_idx - int(lookback))
    train = df.iloc[start_idx:end_idx].copy()
    test = df.iloc[end_idx:end_idx + 1].copy()

    missing = [c for c in feature_cols if c not in train.columns]
    if missing or target_col not in train.columns:
        return pd.Series([0.5], index=test.index)

    unique_targets = pd.Series(train[target_col]).dropna().unique()
    if len(unique_targets) == 0:
        return pd.Series([0.5], index=test.index)
    if len(unique_targets) == 1:
        only = int(unique_targets[0])
        return pd.Series([1.0 if only == 1 else 0.0], index=test.index)

    model = None

    # Cache key must include horizon because the target changes
    cache_key = None
    if ticker:
        cache_key = f"{ticker.upper().strip()}__H{horizon_days}"

    if not retrain and cache_key:
        model = get_cached_model(cache_key)

    if model is None:
        model = _train_model(train, feature_cols, target_col)
        if cache_key:
            set_cached_model(cache_key, model)

    prob_up = _predict_prob_up(model, test, feature_cols)
    prob_up = max(0.0, min(1.0, float(prob_up)))

    return pd.Series([prob_up], index=test.index)
