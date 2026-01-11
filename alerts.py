import requests

def send_alert(message: str):
    print(f"[ALERT] {message}")

    # Optional Discord webhook
    # requests.post("https://discord.com/api/webhooks/...", json={"content": message})

    return True
