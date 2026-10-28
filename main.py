"""
TAIKRY AI MARKET INTELLIGENCE PRO — Universal Main Launcher
Allows running server, 24/7 monitoring, single scans, and backtests from ANY directory.
"""
import sys
import os
import argparse

# Ensure project root is always in sys.path regardless of where the command is executed
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

def main():
    parser = argparse.ArgumentParser(
        description="TAIKRY AI MARKET INTELLIGENCE PRO — Institutional Trading System"
    )
    parser.add_argument("--scan", action="store_true", help="Run a single multi-agent scan across all assets")
    parser.add_argument("--symbol", type=str, default="XAUUSD", help="Symbol to scan (default: XAUUSD)")
    parser.add_argument("--monitor", action="store_true", help="Start continuous 24/7 autonomous monitoring loop")
    parser.add_argument("--server", action="store_true", help="Launch FastAPI REST backend and Trading Dashboard")
    parser.add_argument("--backtest", action="store_true", help="Run a walk-forward backtest on the specified symbol")
    parser.add_argument("--send-report", action="store_true", help="Generate full bilingual AI report and dispatch to Telegram (-1004341134868) and Make webhook")
    parser.add_argument("--daily-report", action="store_true", help="Generate and dispatch XAUUSD daily performance report to Telegram")
    parser.add_argument("--stats", action="store_true", help="Display verified XAUUSD win rates and performance analytics")
    parser.add_argument("--port", type=int, default=8000, help="Port for FastAPI server (default: 8000)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host for FastAPI server (default: 0.0.0.0)")

    args = parser.parse_args()

    # Default to showing help if no argument provided
    if not (args.scan or args.monitor or args.server or args.backtest or args.send_report or args.daily_report or args.stats):
        print("=" * 70)
        print("  TAIKRY AI MARKET INTELLIGENCE PRO")
        print("=" * 70)
        print("Usage:")
        print("  python main.py --scan               # Single scan across all watchlist assets")
        print("  python main.py --scan --symbol BTCUSDT # Scan specific symbol")
        print("  python main.py --send-report        # Send bilingual report to Telegram (-1004341134868)")
        print("  python main.py --daily-report       # Dispatch verified XAUUSD daily performance report")
        print("  python main.py --stats              # Display verified XAUUSD win-rate metrics")
        print("  python main.py --server             # Start FastAPI & Dashboard at http://localhost:8000/dashboard")
        print("  python main.py --monitor            # Start continuous 24/7 autonomous monitoring")
        print("  python main.py --backtest           # Run walk-forward backtest on XAUUSD")
        print("=" * 70)
        return

    if args.scan:
        from taikry.monitoring.engine import market_monitor_247
        print(f"[*] Initiating market scan for {args.symbol}...")
        results = market_monitor_247.scan_once(symbols=[args.symbol] if args.symbol else None)
        print("\n" + "=" * 70)
        print("SCAN COMPLETED")
        print("=" * 70)
        for r in results:
            print(f"\nSymbol: {r.get('symbol')} | Price: {r.get('verified_price')} | Bias: {r.get('market_bias')} | Status: {r.get('setup_status')}")
            print("-" * 50)
            print(r.get("report_english", ""))
            print("-" * 50)

    elif args.monitor:
        from taikry.monitoring.engine import market_monitor_247
        print("[*] Starting continuous 24/7 market monitoring...")
        market_monitor_247.start_background()
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            market_monitor_247.stop()
            print("\n[*] Monitoring stopped.")

    elif args.backtest:
        from taikry.trading.backtester import backtest_engine
        from taikry.data.providers import market_data_engine
        print(f"[*] Fetching historical candles for {args.symbol}...")
        df = market_data_engine.get_candles(args.symbol, "M15", limit=150)
        scorecard = backtest_engine.run_backtest(args.symbol, "M15", df)
        print("\n" + "=" * 70)
        print(f"BACKTEST SCORECARD — {scorecard.get('symbol')} ({scorecard.get('timeframe')})")
        print("=" * 70)
        print(f"Win Rate:        {scorecard.get('win_rate_percent')}%")
        print(f"Net Profit:      ${scorecard.get('net_profit')}")
        print(f"Profit Factor:   {scorecard.get('profit_factor')}")
        print(f"Max Drawdown:    {scorecard.get('max_drawdown_percent')}%")
        print(f"Avg R-Multiple:  {scorecard.get('average_r_multiple')}R")
        print(f"Total Trades:    {scorecard.get('total_trades')}")
        print("=" * 70)

    elif args.send_report:
        from taikry.agents.consensus_engine import ai_consensus_engine
        from taikry.notifications.telegram_service import telegram_service
        from taikry.notifications.make_webhook_dispatcher import dispatch_to_make
        from taikry.config import TELEGRAM_CHAT_ID

        target_sym = args.symbol.upper() if args.symbol else "XAUUSD"
        print(f"[*] Analyzing market & generating report for {target_sym}...")
        res = ai_consensus_engine.analyze_symbol(target_sym)
        print(f"[*] Bias: {res.get('market_bias')} | Setup Status: {res.get('setup_status')}")
        print(f"[*] Target Telegram Bot Chat ID: {TELEGRAM_CHAT_ID}")

        # 1. Dispatch directly via Telegram Bot Service
        tg_ok = telegram_service.send_bilingual_report(res, force=True)
        print(f"[*] Telegram Direct API: {'SENT (HTTP 200)' if tg_ok else 'PENDING / AWAITING BOT TOKEN'}")

        # 2. Dispatch to Make Webhook with chat_id
        payload = {
            "event": "AI_REPORT_SIGNAL",
            "symbol": target_sym,
            "direction": res.get("proposed_direction", "NONE"),
            "entry_price": res.get("entry_price"),
            "stop_loss": res.get("stop_loss"),
            "take_profit_1": res.get("take_profit_1"),
            "take_profit_2": res.get("take_profit_2"),
            "risk_reward": res.get("risk_reward_ratio"),
            "report_english": res.get("report_english"),
            "report_khmer": res.get("report_khmer"),
            "chat_id": TELEGRAM_CHAT_ID,
            "telegram_chat_id": TELEGRAM_CHAT_ID,
            "timestamp": res.get("timestamp_utc")
        }
        dispatch_to_make(payload, event_type="critical_market_alert")
        print(f"[*] Make.com Webhook delivered with chat_id: {TELEGRAM_CHAT_ID}")
        print("\n" + "=" * 70)
        print("BILINGUAL REPORT PREVIEW (EN & KH)")
        print("=" * 70)
        print(res.get("report_english", ""))
        print("\n" + "=" * 30 + "\n")
        print(res.get("report_khmer", ""))
        print("=" * 70)

    elif args.daily_report:
        from taikry.trading.xauusd_tracker import xauusd_performance_tracker
        from taikry.trading.xauusd_signal_engine import get_cambodia_date_str
        from taikry.notifications.telegram_service import telegram_service

        metrics = xauusd_performance_tracker.calculate_win_rate_metrics()
        today_stats = metrics["today"]
        today_date = get_cambodia_date_str()

        payload = {
            "report_date": today_date,
            "signals_sent_count": today_stats["total_sent_count"],
            "wins_count": today_stats["wins_count"],
            "losses_count": today_stats["losses_count"],
            "unresolved_count": today_stats["open_unresolved_count"],
            "expired_count": today_stats["expired_no_entry_count"],
            "ambiguous_count": today_stats["ambiguous_count"],
            "win_rate_percent": today_stats["win_rate_percent"],
            "win_rate_str": today_stats["win_rate_display"],
            "sample_size": today_stats["resolved_sample_size"],
            "tp2_attainment_rate": today_stats["tp2_attainment_rate"],
            "tp3_attainment_rate": today_stats["tp3_attainment_rate"]
        }
        print(f"[*] Dispatching XAUUSD Daily Report for {today_date}...")
        ok, msg_id, err = telegram_service.send_xauusd_daily_report(payload, force=True)
        if ok:
            print(f"[*] Telegram Daily Report dispatched successfully! (Message ID: {msg_id})")
        else:
            print(f"[!] Telegram Daily Report failed: {err}")

    elif args.stats:
        from taikry.trading.xauusd_tracker import xauusd_performance_tracker
        from taikry.trading.xauusd_signal_engine import xauusd_signal_engine

        metrics = xauusd_performance_tracker.calculate_win_rate_metrics()
        quota = xauusd_signal_engine.get_daily_quota_status()
        print("\n" + "=" * 70)
        print(f"TAIKRY SIGNAL AI — VERIFIED XAUUSD PERFORMANCE METRICS ({metrics['cambodia_date']})")
        print("=" * 70)
        print(f"Daily Quota:           {quota['signals_sent_today']}/{quota['daily_hard_limit']} signals sent today ({quota['target_status']})")
        print(f"All-Time Win Rate:     {metrics['all_time']['win_rate_display']}")
        print(f"Resolved Sample Size:  {metrics['all_time']['resolved_sample_size']} trades ({metrics['all_time']['wins_count']} Wins / {metrics['all_time']['losses_count']} Losses)")
        print(f"Today Win Rate:        {metrics['today']['win_rate_display']}")
        print(f"7-Day Win Rate:        {metrics['last_7_days']['win_rate_display']}")
        print(f"30-Day Win Rate:       {metrics['last_30_days']['win_rate_display']}")
        print(f"BUY Signals Win Rate:  {metrics['buy_signals']['win_rate_display']}")
        print(f"SELL Signals Win Rate: {metrics['sell_signals']['win_rate_display']}")
        print(f"TP2 Attainment Rate:   {metrics['all_time']['tp2_attainment_rate'] or 'N/A'}%")
        print(f"TP3 Attainment Rate:   {metrics['all_time']['tp3_attainment_rate'] or 'N/A'}%")
        print(f"Net R-Multiple:        {metrics['all_time']['net_r_multiple']:+.2f}R")
        print(f"Current Streak:        {metrics['streaks']['current_streak']}")
        print(f"Evaluation Policy:     {metrics['methodology']['policy']} ({metrics['methodology']['formula']})")
        print("=" * 70 + "\n")

    elif args.server:
        import uvicorn
        from taikry.database.session import init_db
        init_db()
        print(f"[*] Starting TAIKRY PRO Server at http://localhost:{args.port}/dashboard ...")
        uvicorn.run("taikry.api.app:app", host=args.host, port=args.port, reload=False)

if __name__ == "__main__":
    main()
