"""
Continuous Market Monitoring Engine for TAIKRY AI MARKET INTELLIGENCE PRO
Orchestrates:
- 15-minute analysis cycles for primary assets
- Real-time paper trade position tracking & TP/SL execution
- Weekend closure awareness (Commodities & Forex vs 24/7 Crypto)
- Deduplication and cooldown management
- Error recovery with exponential backoff
"""
import time
import datetime
import threading
import math
from typing import Dict, Any, List

from taikry.config import (
    WATCHLIST,
    PRIMARY_SYMBOL,
    MONITORING_INTERVAL_MINUTES,
    COOLDOWN_MINUTES,
    get_symbol_config,
    TELEGRAM_CHAT_ID
)
from taikry.data.validator import is_market_open
from taikry.data.providers import market_data_engine
from taikry.agents.consensus_engine import ai_consensus_engine
from taikry.trading.paper_trading import paper_trading_engine
from taikry.trading.lifecycle import signal_lifecycle_manager, SignalState
from taikry.notifications.telegram_service import telegram_service
from taikry.notifications.make_webhook_dispatcher import dispatch_to_make
from taikry.trading.xauusd_signal_engine import xauusd_signal_engine, normalize_xauusd_symbol
from taikry.trading.xauusd_tracker import xauusd_performance_tracker

class MarketMonitor247:
    """Continuous market surveillance while the host process is running."""

    def __init__(self):
        self.is_running = False
        self._thread = None
        self.interval_seconds = 60 # Active 60-second real-time institutional scan cycle
        self.cooldown_tracker = {}
        self.last_scan_time = None
        self.last_vip_check_time = 0
        self.stats = {
            "cycles_completed": 0,
            "reports_generated": 0,
            "alerts_dispatched": 0,
            "errors_handled": 0
        }

    def start_background(self):
        """Starts monitoring in a dedicated daemon thread."""
        if self.is_running:
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Signals monitoring loop to gracefully terminate."""
        self.is_running = False

    def scan_once(self, symbols: List[str] = None) -> List[Dict[str, Any]]:
        """
        Executes a single end-to-end market scan across watchlist.
        Prioritizes XAUUSD (Gold) as #1 asset in the universe.
        Dispatches to Telegram ONLY the #1 single best setup with AI Confluence Score 80%-95%.
        Evaluates active and waiting signal lifecycle state transitions on every tick.
        """
        raw_symbols = symbols or [w["symbol"] for w in WATCHLIST]
        # Institutional Priority Queue: XAUUSD scanned first
        target_symbols = sorted(raw_symbols, key=lambda s: 0 if s == PRIMARY_SYMBOL else 1)

        results = []
        current_prices = {}
        qualifying_candidates = []

        for sym in target_symbols:
            open_ok, reason = is_market_open(sym)
            if not open_ok:
                # Weekend / Closed hours for Forex & Gold: Skip gracefully without raising errors
                continue

            try:
                res = ai_consensus_engine.analyze_symbol(sym)
                results.append(res)
                self.stats["reports_generated"] += 1

                verified_p = res.get("verified_price", 0.0)
                if verified_p > 0:
                    current_prices[sym] = verified_p

                setup_status = res.get("setup_status")
                prop_dir = res.get("proposed_direction")
                score = res.get("ai_score") or res.get("confidence_score", 0)

                # Strict Quality Gate: ONLY setups with active direction AND score strictly in 80% - 95%
                if setup_status == "APPROVE" and prop_dir in ["LONG", "SHORT", "BUY", "SELL"] and (80 <= score <= 95):
                    qualifying_candidates.append(res)

            except Exception as e:
                self.stats["errors_handled"] += 1

        # Institutional Selection: Dispatch ONLY the single #1 BEST SETUP from the universe
        if qualifying_candidates:
            # Sort by ai_score descending, with gold (XAUUSD) preference on score ties
            qualifying_candidates.sort(
                key=lambda x: (
                    x.get("ai_score") or x.get("confidence_score", 0),
                    1 if x.get("symbol") == "XAUUSD" else 0
                ),
                reverse=True
            )
            best_setup = qualifying_candidates[0]
            self._handle_approved_setup(best_setup)

        # 1. Evaluate persistent signal lifecycle states against latest prices
        if current_prices:
            signal_lifecycle_manager.evaluate_signals(current_prices)
            # Evaluate dedicated XAUUSD Telegram signal outcomes
            xau_price = current_prices.get("XAUUSD")
            if xau_price and xau_price > 0:
                xauusd_performance_tracker.evaluate_signals_against_market(xau_price)

        # 2. Check and update open paper trades against latest prices
        if current_prices:
            closed_events = paper_trading_engine.update_open_trades(current_prices)
            for ev in closed_events:
                self._notify_trade_closure(ev)

        # 3. Periodic VIP Subscription & SaaS Trial Expiration Sweep (Every 15 mins)
        now_ts = time.time()
        if now_ts - self.last_vip_check_time >= 900:
            self.last_vip_check_time = now_ts
            try:
                from taikry.subscriptions.vip_manager import vip_subscription_manager
                vip_subscription_manager.check_and_process_expirations()
            except Exception:
                pass
            # SaaS 14-Day Free Trial expiration sweep
            try:
                from taikry.database.session import SessionLocal
                from taikry.database.models import User
                db_saas = SessionLocal()
                try:
                    utc_now = datetime.datetime.now(datetime.timezone.utc)
                    expired_users = db_saas.query(User).filter(
                        User.trial_status == "trial_active",
                        User.trial_expires_at <= utc_now
                    ).all()
                    for exp_u in expired_users:
                        exp_u.trial_status = "trial_expired"
                    if expired_users:
                        db_saas.commit()
                finally:
                    db_saas.close()
            except Exception:
                pass

        self.last_scan_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.stats["cycles_completed"] += 1
        return results

    def _handle_approved_setup(self, consensus_res: Dict[str, Any]):
        """
        Dispatches high-conviction approved setup.
        STRICT POLICY: Trading signals to Telegram are sent for XAUUSD ONLY.
        Non-gold instruments are strictly blocked from Telegram delivery.
        """
        sym = consensus_res["symbol"]
        score = consensus_res.get("ai_score") or consensus_res.get("confidence_score", 0)

        if consensus_res.get("setup_status") != "APPROVE" or consensus_res.get("proposed_direction") not in ["LONG", "SHORT", "BUY", "SELL"]:
            return

        # Strict Guard: Score MUST be strictly within 80% - 95%
        if score < 80 or score > 95:
            return

        is_buy = consensus_res.get("proposed_direction") in ["LONG", "BUY"]
        direction = "BUY" if is_buy else "SELL"

        # Check cooldown (3 minutes) to prevent flooding while keeping alerts active and fresh
        cooldown_limit = 3.0
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        last_time = self.cooldown_tracker.get(sym)
        if last_time:
            if last_time.tzinfo is None:
                last_time = last_time.replace(tzinfo=datetime.timezone.utc)
            elapsed_min = (now_utc - last_time).total_seconds() / 60.0
            if elapsed_min < cooldown_limit:
                return

        try:
            entry = float(consensus_res.get("entry_price"))
            sl = float(consensus_res.get("stop_loss"))
            tp1 = float(consensus_res.get("take_profit_1"))
        except (TypeError, ValueError):
            logger.info("Approved setup for %s skipped: entry, stop-loss, or take-profit is missing.", sym)
            return
        if not all(math.isfinite(value) and value > 0 for value in (entry, sl, tp1)):
            logger.info("Approved setup for %s skipped: invalid price levels.", sym)
            return
        if (is_buy and not sl < entry < tp1) or (not is_buy and not sl > entry > tp1):
            logger.info("Approved setup for %s skipped: price levels conflict with direction.", sym)
            return
        tp2 = consensus_res.get("take_profit_2")

        # 1. Register persistent stateful signal in Signal Lifecycle Manager (General Dashboard)
        created_signal = signal_lifecycle_manager.create_signal(
            symbol=sym,
            direction=direction,
            entry_price=entry,
            stop_loss=sl,
            take_profit_1=tp1,
            take_profit_2=tp2,
            risk_reward=consensus_res.get("risk_reward_ratio", "N/A"),
            ai_score=score,
            timeframe=consensus_res.get("timeframe", "M15"),
            initial_state=SignalState.WAITING_CONFIRMATION,
            trigger_cause=f"AI Consensus score {score}% approved for {direction} {sym}"
        )

        # 2. Execute simulated paper trade (Internal dashboard simulation)
        paper_res = paper_trading_engine.open_trade(
            symbol=sym,
            direction=direction,
            entry_price=entry,
            stop_loss=sl,
            take_profit_1=tp1,
            take_profit_2=tp2
        )

        # 3. STRICT XAUUSD-ONLY TELEGRAM POLICY
        canonical_gold = normalize_xauusd_symbol(sym)
        if canonical_gold == "XAUUSD":
            # Generate and persist via XAUUSD Signal Engine (enforcing atomic daily quota max 4)
            xau_signal = xauusd_signal_engine.generate_xauusd_signal("XAUUSD")
            if xau_signal.get("success"):
                telegram_ok, msg_id, tg_err = telegram_service.send_xauusd_signal_alert(xau_signal)
                if telegram_ok:
                    self.stats["alerts_dispatched"] += 1
            else:
                logger.info(f"XAUUSD Signal Engine suppressed alert: {xau_signal.get('error') or xau_signal.get('rejection_reason')}")
        else:
            # NON-XAUUSD INSTRUMENTS: Strictly blocked from Telegram trading signals
            logger.info(f"Strict XAUUSD policy: Telegram signal delivery blocked for non-gold instrument '{sym}'.")

        # 4. Dispatch to Make Webhook (for automation / dashboard logging)
        payload = {
            "event": "VALIDATED_SIGNAL",
            "signal_id": created_signal.get("signal_id"),
            "symbol": sym,
            "direction": direction,
            "ai_score": score,
            "entry_price": consensus_res["entry_price"],
            "stop_loss": consensus_res["stop_loss"],
            "take_profit_1": consensus_res["take_profit_1"],
            "take_profit_2": consensus_res.get("take_profit_2"),
            "risk_reward": consensus_res.get("risk_reward_ratio"),
            "paper_trade": paper_res,
            "report_english": consensus_res.get("report_english"),
            "report_khmer": consensus_res.get("report_khmer"),
            **({"chat_id": TELEGRAM_CHAT_ID, "telegram_chat_id": TELEGRAM_CHAT_ID} if TELEGRAM_CHAT_ID else {}),
            "timestamp": now_utc.isoformat()
        }
        dispatch_to_make(payload, event_type="critical_market_alert")

        self.cooldown_tracker[sym] = now_utc

    def _notify_trade_closure(self, trade_event: Dict[str, Any]):
        """Dispatches trade completion notification."""
        msg = f"""🔔 <b>PAPER TRADE CLOSED: {trade_event['direction']} {trade_event['symbol']}</b>

Reason: <b>{trade_event['exit_reason']}</b>
Exit Price: <code>{trade_event['exit_price']}</code>
Net PnL: <b>${trade_event['net_pnl']:+,.2f}</b>
R-Multiple: <b>{trade_event['r_multiple']:+.2f}R</b>
"""
        telegram_service.send_message(msg)

    def _run_loop(self):
        """Internal continuous loop."""
        while self.is_running:
            try:
                self.scan_once()
            except Exception:
                self.stats["errors_handled"] += 1

            # Sleep in small increments for responsive stop
            sleep_chunks = self.interval_seconds // 2
            for _ in range(sleep_chunks):
                if not self.is_running:
                    break
                time.sleep(2)

market_monitor_247 = MarketMonitor247()
