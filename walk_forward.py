# walk_forward.py
from __future__ import annotations

from typing import List, Optional, Tuple
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from model_cache import get_cached_model, set_cached_model


def _train_model(
    train_df: pd.DataFrame,
    feature_cols: List[str],
    target_col: str,
) -> RandomForestClassifier:
    # Keep random_state fixed for reproducibility
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
    """
    Returns P(class==1). If the model was trained on a single class, handle gracefully.
    """
    # If only one class was seen during training, predict_proba may return shape (n,1)
    proba = model.predict_proba(test_df[feature_cols])
    if proba.shape[1] == 1:
        # Only one class available
        cls = int(model.classes_[0])
        return 1.0 if cls == 1 else 0.0

    # Find column corresponding to class 1
    class_to_index = {int(c): i for i, c in enumerate(model.classes_)}
    idx = class_to_index.get(1, 1)  # fallback to second column
    return float(proba[0, idx])


def walk_forward_predict_proba(
    df: pd.DataFrame,
    feature_cols: List[str],
    target_col: str,
    *,
    ticker: Optional[str] = None,
    retrain: bool = True,
    lookback: int = 252,
    min_train: int = 60,
) -> pd.Series:
    """
    Walk-forward-ish prediction returning probability of "up" for the *last* row.

    Key improvements:
    - Deterministic window via `lookback`
    - Optional model caching keyed by ticker
    - Stable behavior via fixed random_state and bigger forest

    Returns:
      pd.Series indexed like df.iloc[-1:], with one value = prob_up.
    """
    if df is None or len(df) < 2:
        return pd.Series([0.5], index=df.index[-1:] if df is not None and len(df) else None)

    # Need enough history
    if len(df) < max(10, min_train + 1):
        return pd.Series([0.5], index=df.iloc[-1:].index)

    # Slice deterministic training window (excluding final row)
    end_idx = len(df) - 1
    start_idx = max(0, end_idx - int(lookback))
    train = df.iloc[start_idx:end_idx].copy()
    test = df.iloc[end_idx:end_idx + 1].copy()

    # Basic sanity: feature columns present
    missing = [c for c in feature_cols if c not in train.columns]
    if missing:
        return pd.Series([0.5], index=test.index)

    # Target sanity: if constant (all 0 or all 1), outcome is known
    if target_col not in train.columns:
        return pd.Series([0.5], index=test.index)

    unique_targets = pd.Series(train[target_col]).dropna().unique()
    if len(unique_targets) == 0:
        return pd.Series([0.5], index=test.index)
    if len(unique_targets) == 1:
        only = int(unique_targets[0])
        return pd.Series([1.0 if only == 1 else 0.0], index=test.index)

    # Try to reuse cached model
    model = None
    cache_key = (ticker or "").upper().strip() if ticker else None
    if not retrain and cache_key:
        model = get_cached_model(cache_key)

    # Train if needed
    if model is None:
        model = _train_model(train, feature_cols, target_col)
        if cache_key:
            set_cached_model(cache_key, model)

    prob_up = _predict_prob_up(model, test, feature_cols)
    # clamp
    prob_up = max(0.0, min(1.0, float(prob_up)))
    return pd.Series([prob_up], index=test.index)
