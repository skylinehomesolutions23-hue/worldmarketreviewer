def classify(vol, drawdown):
    if vol > 0.35 and drawdown < -0.4:
        return "CRISIS"
    if vol > 0.25:
        return "RISKY"
    return "NORMAL"
