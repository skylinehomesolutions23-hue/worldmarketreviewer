def explain_status(status, prefs):
    level = prefs.get("experience_level", "beginner")

    explanations = {
        "GREEN": {
            "beginner": (
                "Market conditions are healthy. "
                "Risk levels are normal and the system is operating as expected."
            ),
            "pro": (
                "Signals are stable with acceptable volatility, drawdowns, "
                "and no tail-risk breach detected."
            ),
        },
        "YELLOW": {
            "beginner": (
                "Some warning signs are appearing. "
                "The system is being cautious and watching risk closely."
            ),
            "pro": (
                "Early risk degradation detected. "
                "Metrics approaching soft risk thresholds."
            ),
        },
        "RED": {
            "beginner": (
                "Risk is elevated. "
                "The system has reduced or stopped exposure to protect capital."
            ),
            "pro": (
                "Risk limits breached. "
                "Kill-switch or defensive controls activated."
            ),
        },
    }

    return explanations.get(status, {}).get(
        level, "No explanation available."
    )
