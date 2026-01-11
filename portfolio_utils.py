# portfolio_utils.py

import numpy as np

def compute_turnover(prev_weights, new_weights):
    """
    Turnover = sum(|new - old|)
    """
    all_tickers = set(prev_weights) | set(new_weights)

    turnover = 0.0
    for t in all_tickers:
        w_old = prev_weights.get(t, 0.0)
        w_new = new_weights.get(t, 0.0)
        turnover += abs(w_new - w_old)

    return turnover
