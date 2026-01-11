def confidence_signal(prob, threshold=0.55):
    strength = max(0, (prob - threshold) / (1 - threshold))
    return min(strength, 1.0)
