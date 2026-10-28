import json
import urllib.request
import urllib.error
import sys
import os

URL = os.getenv("MAKE_WEBHOOK_URL", "")

def send_webhook(symbol="XAUUSD", timeframe="M5", action="analyze", test="true"):
    url = os.getenv("MAKE_WEBHOOK_URL", URL)
    if not url:
        print("[ERROR] MAKE_WEBHOOK_URL is not configured in environment. Please set MAKE_WEBHOOK_URL.")
        return 1, "MAKE_WEBHOOK_URL not configured"

    payload = {
        "symbol": symbol,
        "timeframe": timeframe,
        "action": action,
        "test": test,
        "chat_id": "-1004341134868"
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        URL,
        data=data,
        headers={"Content-Type": "application/json"}
    )

    print(f"Sending POST to {URL}...")
    print(f"Payload: {json.dumps(payload, indent=2)}")

    try:
        with urllib.request.urlopen(req) as response:
            status_code = response.getcode()
            response_text = response.read().decode("utf-8")
            print(f"Status: {status_code}")
            print(f"Response: {response_text}")
            return status_code, response_text
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.read().decode('utf-8')}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    send_webhook()
