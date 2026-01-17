# model_cache.py
from __future__ import annotations

from typing import Dict, Optional
from sklearn.base import BaseEstimator

# Simple process-memory cache (best-effort on Render)
_MODEL_CACHE: Dict[str, BaseEstimator] = {}


def get_cached_model(ticker: str) -> Optional[BaseEstimator]:
    key = (ticker or "").upper().strip()
    if not key:
        return None
    return _MODEL_CACHE.get(key)


def set_cached_model(ticker: str, model: BaseEstimator) -> None:
    key = (ticker or "").upper().strip()
    if not key:
        return
    _MODEL_CACHE[key] = model


def clear_cache() -> None:
    _MODEL_CACHE.clear()
