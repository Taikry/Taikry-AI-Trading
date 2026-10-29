import argparse
import datetime
import json
import time
import urllib.error
import urllib.request
import os

def send_test_webhook(iteration=1, symbol="XAUUSD", timeframe="M5", action="analyze"):
    target_url = os.getenv("MAKE_WEBHOOK_URL", "").strip()
    if not target_url:
        print("[ERROR] MAKE_WEBHOOK_URL environment variable is required.")
        return False
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    payload = {
        "symbol": symbol,
        "timeframe": timeframe,
        "action": action,
        "test": True,
        "iteration": iteration,
        "timestamp": timestamp
    }
    configured_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if configured_chat_id:
        payload["chat_id"] = configured_chat_id
    
    data = json.dumps(payload).encode("utf-8")
    configured_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if configured_chat_id:
        payload["chat_id"] = configured_chat_id
    req = urllib.request.Request(
        target_url,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    
    try:
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=10) as response:
            latency_ms = int((time.time() - t0) * 1000)
            status_code = response.getcode()
            response_text = response.read().decode("utf-8").strip()
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Test #{iteration} -> HTTP {status_code} ({response_text}) [{latency_ms}ms]")
            return True
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Test #{iteration} -> HTTP Error {e.code}: {err_msg}")
        return False
    except Exception as e:
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Test #{iteration} -> Connection Error: {e}")
        return False

def main():
    if not os.getenv("MAKE_WEBHOOK_URL", "").strip():
        print("[ERROR] MAKE_WEBHOOK_URL environment variable is required.")
        return
    parser = argparse.ArgumentParser(description="Auto-run webhook tester")
    parser.add_argument("--count", type=int, default=5, help="Number of requests to send (0 for infinite loop, default 5)")
    parser.add_argument("--interval", type=int, default=3, help="Interval in seconds between requests (default 3)")
    parser.add_argument("--symbol", type=str, default="XAUUSD", help="Symbol to test")
    parser.add_argument("--timeframe", type=str, default="M5", help="Timeframe to test")
    parser.add_argument("--action", type=str, default="analyze", help="Action to test")

    args = parser.parse_args()
    if args.count < 0 or args.interval < 1:
        parser.error("--count must be >= 0 and --interval must be >= 1")

    print(f"==================================================")
    print(f" Starting Webhook Auto-Runner")
    print(" Target: configured Make webhook")
    print(f" Total Requests: {'Infinite' if args.count == 0 else args.count}")
    print(f" Interval: {args.interval}s")
    print(f" Symbol: {args.symbol} | Timeframe: {args.timeframe}")
    print(f"==================================================")

    i = 1
    successful = 0
    failed = 0

    try:
        while True:
            ok = send_test_webhook(iteration=i, symbol=args.symbol, timeframe=args.timeframe, action=args.action)
            if ok:
                successful += 1
            else:
                failed += 1

            if args.count > 0 and i >= args.count:
                break

            i += 1
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nAuto-run stopped by user.")

    print(f"==================================================")
    print(f" Summary: {successful} succeeded, {failed} failed out of {successful + failed} sent.")
    print(f"==================================================")

if __name__ == "__main__":
    main()
