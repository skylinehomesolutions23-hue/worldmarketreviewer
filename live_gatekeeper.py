import pandas as pd

def main():
    kill = pd.read_csv(
        "results/decay/signal_auto_kill_v3.csv",
        parse_dates=["date"]
    )

    risk = pd.read_csv("results/integrated_risk_report.csv")

    # Use latest observations
    latest_kill = kill.iloc[-1]
    latest_risk = risk.iloc[-1]

    status = "FULL"
    reason = "NORMAL"

    if latest_kill["kill_signal"]:
        status = "HALT"
        reason = latest_kill["reason"]

    elif (
        latest_risk["beta_3m"] > 1.2 or
        latest_risk["max_dd_3m"] < -0.15
    ):
        status = "REDUCE"
        reason = "ELEVATED_RISK"

    output = pd.DataFrame([{
        "date": latest_kill["date"],
        "status": status,
        "reason": reason,
        "beta_3m": latest_risk["beta_3m"],
        "max_dd_3m": latest_risk["max_dd_3m"]
    }])

    output.to_csv("results/live_gatekeeper_status.csv", index=False)

    print("🚦 Live gatekeeper decision")
    print(output)

if __name__ == "__main__":
    main()
