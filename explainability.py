def explain_decision(vol, dd, kill, profile):
    reasons = []

    if kill:
        reasons.append("Kill-switch triggered.")
    if vol > profile["risk_rules"]["volatility_threshold"]:
        reasons.append(f"Volatility {vol:.2f} exceeds threshold.")
    if dd < profile["risk_rules"]["drawdown_threshold"]:
        reasons.append(f"Drawdown {dd:.2f} exceeds limit.")

    if not reasons:
        reasons.append("All risk metrics within healthy range.")

    return " ".join(reasons)
