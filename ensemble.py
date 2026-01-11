def ensemble_score(ml_prob, trend_up, regime):
    score = ml_prob

    if trend_up:
        score += 0.05
    else:
        score -= 0.05

    if regime == 1:   # bull
        score += 0.05
    elif regime == -1:  # bear
        score -= 0.05

    return max(min(score, 0.99), 0.01)
