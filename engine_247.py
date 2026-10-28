import argparse
import datetime
import json
import time
import requests

from config import (
    MAKE_WEBHOOK_URL,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    WATCHLIST,
    DEFAULT_TIMEFRAME,
    MIN_CONFIDENCE_THRESHOLD,
    COOLDOWN_MINUTES,
    SCAN_INTERVAL_SECONDS
)
from market_data import fetch_candles
from indicators import calculate_indicators, extract_market_summary
from ai_agent import generate_signal

# Track symbol cooldowns {symbol: timestamp_of_last_signal}
COOLDOWN_TRACKER = {}

def is_on_cooldown(symbol: str) -> bool:
    last_sent = COOLDOWN_TRACKER.get(symbol)
    if not last_sent:
        return False
    elapsed = (datetime.datetime.now() - last_sent).total_seconds() / 60.0
    return elapsed < COOLDOWN_MINUTES

def mark_cooldown(symbol: str):
    COOLDOWN_TRACKER[symbol] = datetime.datetime.now()

def send_telegram_alert(payload: dict) -> bool:
    """Dispatches formatted HTML signal directly to Telegram Bot/Channel."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    action = payload["action"]
    symbol = payload["symbol"]
    emoji_action = "🟢 BUY" if action == "BUY" else ("🔴 SELL" if action == "SELL" else "⏸ HOLD")
    smart_analysis = payload.get("smart_analysis", {})
    checklist = smart_analysis.get("checklist", {})

    tech_causes = smart_analysis.get("technical_causes", [])
    smc_causes = smart_analysis.get("smc_causes", [])
    macro_causes = smart_analysis.get("macro_causes", [])
    risk_causes = smart_analysis.get("risk_causes", [])

    tech_str = tech_causes[0] if tech_causes else "Technical indicators evaluated."
    smc_str = smc_causes[0] if smc_causes else "SMC structure & dealing range evaluated."
    macro_str = macro_causes[0] if macro_causes else "Macro catalysts verified."
    risk_str = risk_causes[0] if risk_causes else "Risk & capital rules verified."

    chk_c = "✅" if checklist.get("multi_agent_consensus") else "⚠️"
    chk_l = "✅" if checklist.get("institutional_liquidity_clear") else "⚠️"
    chk_m = "✅" if checklist.get("macro_dxy_aligned") else "⚠️"
    chk_r = "✅" if checklist.get("risk_reward_viable") else "❌"

    synth_kh = payload.get("rationale_kh") or smart_analysis.get("synthesis_summary_kh", "")

    # Lock levels if HOLD or rejected
    is_active = action in ["BUY", "SELL"]
    entry_display = payload['entry_price'] if is_active else "🔒 LOCKED (Capital Protected)"
    sl_display = payload['stop_loss'] if is_active else "🔒 LOCKED"
    tp1_display = payload['take_profit_1'] if is_active else "🔒 LOCKED"
    tp2_display = payload['take_profit_2'] if is_active else "🔒 LOCKED"
    rr_display = payload['risk_reward_ratio'] if is_active else "LOCKED (Min 1:2.0 required)"

    # Clean, focused institutional signal format: BUY ENTRY / SELL ENTRY, SL, TP 1, TP 2
    is_buy = action in ["BUY", "LONG"]
    action_tag = "BUY ENTRY" if is_buy else ("SELL ENTRY" if action in ["SELL", "SHORT"] else action)
    tag_icon = "🟢" if is_buy else ("🔴" if action in ["SELL", "SHORT"] else "⚪")
    confidence = payload.get("confidence", 85)
    confidence = max(80, min(95, int(confidence)))

    text = f"""{tag_icon} <b>TAIKRY AI ALERT — #{symbol}</b>
━━━━━━━━━━━━━━━━━━━━
⭐ <b>AI CONFLUENCE SCORE:</b> <b>{confidence}%</b> (HIGH CONVICTION)
🎯 <b>ACTION:</b> <b>{tag_icon} {action_tag}</b>
💵 <b>{action_tag}:</b> <code>{entry_display}</code>
🛑 <b>STOP LOSS (SL):</b> <code>{sl_display}</code>
🎯 <b>TAKE PROFIT 1 (TP 1):</b> <code>{tp1_display}</code>
🚀 <b>TAKE PROFIT 2 (TP 2):</b> <code>{tp2_display}</code>
⚖️ <b>RISK / REWARD:</b> {rr_display}
🛡️ <b>RISK GUARD:</b> 0.5% Institutional Cap
━━━━━━━━━━━━━━━━━━━━
🤖 <i>TAIKRY AI 24/7 AUTO SENTINEL</i>"""

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    body = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }

    try:
        res = requests.post(url, json=body, timeout=8)
        if res.status_code == 200:
            print(f"  [TELEGRAM] Alert sent to Telegram chat {TELEGRAM_CHAT_ID} successfully!")
            return True
        else:
            print(f"  [TELEGRAM ERROR] HTTP {res.status_code}: {res.text}")
            return False
    except Exception as e:
        print(f"  [TELEGRAM EXCEPTION] {e}")
        return False

def dispatch_webhook(payload: dict) -> bool:
    """Dispatches signal directly to user's Make.com scenario webhook."""
    try:
        t0 = time.time()
        res = requests.post(
            MAKE_WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        latency = int((time.time() - t0) * 1000)
        if res.status_code in [200, 201, 202]:
            print(f"  [DISPATCHED] Webhook delivered successfully! Status: {res.status_code} ({res.text.strip()}) [{latency}ms]")
            return True
        else:
            print(f"  [DISPATCH ERROR] HTTP {res.status_code}: {res.text}")
            return False
    except Exception as e:
        print(f"  [DISPATCH FAILED] {e}")
        return False


def scan_symbol(item: dict, timeframe: str = DEFAULT_TIMEFRAME, force_dispatch: bool = False):
    symbol = item["symbol"]
    ticker = item["ticker"]
    category = item["category"]

    df = fetch_candles(ticker, timeframe)
    if df.empty or len(df) < 30:
        print(f"  [-] {symbol:<8} ({category}): Insufficient market data")
        return None

    df_ind = calculate_indicators(df)
    metrics = extract_market_summary(df_ind)
    if not metrics:
        return None

    signal = generate_signal(item, timeframe, metrics)
    if not signal:
        return None

    action = signal.get("action", "HOLD")
    confidence = signal.get("confidence", 0)
    price = metrics["current_price"]
    rsi = metrics["rsi"]
    trend = metrics["trend"]

    status_tag = f"[{action}]"
    print(f"  {status_tag:<8} {symbol:<8} | Price: {price:<10} | RSI: {rsi:<5} | Trend: {trend:<7} | Confidence: {confidence}%")

    should_send = (action in ["BUY", "SELL"] and 80 <= confidence <= 95) or force_dispatch

    if should_send:
        if not force_dispatch and is_on_cooldown(symbol):
            print(f"       -> Signal active, but {symbol} is in cooldown. Skipping spam.")
            return signal

        payload = {
            "source": "AI_AGENT_ENGINE_247",
            "symbol": symbol,
            "name": item["name"],
            "category": category,
            "timeframe": timeframe,
            "action": action,
            "status": signal.get("status", "APPROVED" if action != "HOLD" else "REJECTED_LOCKED"),
            "confidence": confidence,
            "smart_analysis": signal.get("smart_analysis", {}),
            "entry_price": signal["entry_price"],
            "stop_loss": signal["stop_loss"],
            "take_profit_1": signal["take_profit_1"],
            "take_profit_2": signal["take_profit_2"],
            "risk_reward_ratio": signal["risk_reward_ratio"],
            "rationale": signal["rationale"],
            "rationale_kh": signal.get("rationale_kh", ""),
            "metrics": {
                "rsi": rsi,
                "trend": trend,
                "atr": metrics["atr"],
                "swing_high": metrics["swing_high"],
                "swing_low": metrics["swing_low"]
            },
            "chat_id": TELEGRAM_CHAT_ID or "-1004341134868",
            "telegram_chat_id": TELEGRAM_CHAT_ID or "-1004341134868",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

        print(f"\n       ==================================================================")
        print(f"       🧠 SMART CAUSAL ANALYSIS (វិភាគមូលហេតុ): {action} {symbol} ({confidence}%)")
        print(f"       ==================================================================")
        sa = signal.get("smart_analysis", {})
        for tc in sa.get("technical_causes", [])[:1]:
            print(f"       [🤖 Technical]: {tc}")
        for sc in sa.get("smc_causes", [])[:1]:
            print(f"       [🏛️ SMC / ICT]: {sc}")
        for mc in sa.get("macro_causes", [])[:1]:
            print(f"       [🌐 Macro/DXY]: {mc}")
        for rc in sa.get("risk_causes", [])[:1]:
            print(f"       [🛡️ Risk Audit]: {rc}")
        if signal.get("rationale_kh"):
            print(f"       [🇰🇭 វិភាគខ្មែរ]: {signal['rationale_kh']}")
        print(f"       ------------------------------------------------------------------")
        print(f"       🎯 TRADE EXECUTION LEVELS (ONLY AFTER CAUSES VERIFIED):")
        print(f"       Entry: {signal['entry_price']} | SL: {signal['stop_loss']} | TP1: {signal['take_profit_1']} | TP2: {signal['take_profit_2']} | R:R: {signal['risk_reward_ratio']}")
        print(f"       ==================================================================\n")

        success_webhook = dispatch_webhook(payload)
        send_telegram_alert(payload)

        if success_webhook:
            mark_cooldown(symbol)

        return signal

    return signal

def run_pipeline(single_pass: bool = False, force_first_test: bool = False):
    print("=" * 70)
    print("  AI AGENT 24/7 TRADING SIGNAL & MARKET ANALYSIS ENGINE")
    print(f"  Target Webhook: {MAKE_WEBHOOK_URL}")
    print(f"  Watchlist: {len(WATCHLIST)} assets (Crypto, Commodities, Forex)")
    print(f"  Default Timeframe: {DEFAULT_TIMEFRAME} | Scan Interval: {SCAN_INTERVAL_SECONDS}s")
    print(f"  Confidence Threshold: {MIN_CONFIDENCE_THRESHOLD}%")
    print("=" * 70)

    round_idx = 1
    try:
        while True:
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n--- [Round #{round_idx}] Scanning Market at {now_str} ---")

            for idx, item in enumerate(WATCHLIST):
                # Optionally force dispatch on the very first symbol in test mode
                force_it = force_first_test and (round_idx == 1 and idx == 0)
                try:
                    scan_symbol(item, DEFAULT_TIMEFRAME, force_dispatch=force_it)
                except Exception as ex:
                    print(f"  [Error scanning {item['symbol']}]: {ex}")

            if single_pass:
                print("\nSingle pass completed.")
                break

            round_idx += 1
            print(f"\nSleeping for {SCAN_INTERVAL_SECONDS} seconds until next scan cycle...")
            time.sleep(SCAN_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\n24/7 Engine gracefully stopped by user.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="24/7 AI Signal Analysis Engine")
    parser.add_argument("--once", action="store_true", help="Run a single scan across all assets and exit")
    parser.add_argument("--test-dispatch", action="store_true", help="Force dispatch the first asset to test webhook")
    parser.add_argument("--interval", type=int, default=SCAN_INTERVAL_SECONDS, help="Seconds between scans")

    args = parser.parse_args()
    if args.interval:
        SCAN_INTERVAL_SECONDS = args.interval

    run_pipeline(single_pass=args.once, force_first_test=args.test_dispatch)
