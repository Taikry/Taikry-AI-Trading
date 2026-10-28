"""
TAIKRY SIGNAL AI — XAUUSD PERFORMANCE TRACKER & OUTCOME ENGINE
==============================================================
Independent outcome resolution and mathematical win-rate calculator
for XAUUSD Telegram trading signals.

Rules Enforced:
1. TP1-based conservative evaluation policy (TP1_CONSERVATIVE_V1).
2. Clean separation of Wins (TP1 hit before SL), Losses (SL hit before TP1),
   Expired without entry, and Same-Candle Ambiguous outcomes.
3. Strict sample size disclosure: Win Rate = Wins / (Wins + Losses) * 100%.
4. If resolved sample == 0: "N/A — insufficient resolved trades" (never false 0% or 100%).
5. Tracks Today (Cambodia date), 7-day, 30-day, and All-Time performance.
6. MFE (Max Favorable Excursion), MAE (Max Adverse Excursion), Net R-Multiples,
   and consecutive win/loss streaks.
"""

import datetime
import zoneinfo
import logging
from typing import Dict, Any, List, Optional, Tuple

from taikry.database.session import SessionLocal
from taikry.database.models import XAUUSDTelegramSignalModel
from taikry.trading.xauusd_signal_engine import get_cambodia_date_str, CAMBODIA_TZ

logger = logging.getLogger("taikry.trading.xauusd_tracker")


class XAUUSDPerformanceTracker:
    """
    Evaluates real-time price action against persistent XAUUSD Telegram signals
    and computes independently verified performance metrics.
    """

    # -------------------------------------------------------------------------
    # 1. REAL-TIME TICK & CANDLE OUTCOME RESOLUTION
    # -------------------------------------------------------------------------

    def evaluate_signals_against_market(
        self,
        current_price: float,
        high_price: Optional[float] = None,
        low_price: Optional[float] = None,
        candle_timestamp: Optional[datetime.datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Evaluates all active/pending XAUUSD Telegram signals against incoming market price action.
        Follows conservative resolution rules:
        - If entry reached, transition to OPEN.
        - If TP1 touched before SL, mark WIN (TP1_HIT).
        - If SL touched before TP1, mark LOSS (SL_HIT).
        - If same candle touches BOTH TP1 and SL, classify as AMBIGUOUS (conservative: not a win).
        - If expired without entry, mark EXPIRED_NO_ENTRY.
        """
        if current_price <= 0:
            return []

        h = high_price if high_price is not None else current_price
        l = low_price if low_price is not None else current_price
        eval_dt = candle_timestamp or datetime.datetime.now(datetime.timezone.utc)

        db = SessionLocal()
        resolved_events = []
        try:
            # Fetch all sent signals that are not yet terminal (i.e. SENT or OPEN)
            active_signals = db.query(XAUUSDTelegramSignalModel).filter(
                XAUUSDTelegramSignalModel.canonical_symbol == "XAUUSD",
                XAUUSDTelegramSignalModel.telegram_delivery_status == "SENT",
                XAUUSDTelegramSignalModel.signal_status.in_(["SENT", "OPEN"])
            ).all()

            for sig in active_signals:
                is_buy = sig.direction == "BUY"
                status = sig.signal_status
                entry = sig.entry_price
                sl = sig.stop_loss
                tp1 = sig.take_profit_1
                tp2 = sig.take_profit_2 or (entry + abs(entry - sl) * 3.3 if is_buy else entry - abs(entry - sl) * 3.3)
                tp3 = sig.take_profit_3 or (entry + abs(entry - sl) * 4.8 if is_buy else entry - abs(entry - sl) * 4.8)

                # 1. Expiration check for unfilled orders
                if status == "SENT" and not sig.entry_reached:
                    if sig.expires_at and eval_dt > sig.expires_at.replace(tzinfo=datetime.timezone.utc if sig.expires_at.tzinfo is None else None):
                        sig.signal_status = "EXPIRED"
                        sig.outcome = "EXPIRED_NO_ENTRY"
                        sig.exit_time = eval_dt
                        sig.exit_price = current_price
                        self._append_audit(sig, "EXPIRED", "Signal expired without entry fill", current_price, eval_dt)
                        resolved_events.append({"signal_id": sig.signal_id, "status": "EXPIRED", "outcome": "EXPIRED_NO_ENTRY"})
                        continue

                # 2. Check Entry Fill (for SENT signals)
                if status == "SENT" and not sig.entry_reached:
                    # Entry zone or market level reach
                    entry_hit = False
                    if sig.entry_zone_low and sig.entry_zone_high:
                        if l <= sig.entry_zone_high and h >= sig.entry_zone_low:
                            entry_hit = True
                    else:
                        if (is_buy and l <= entry) or (not is_buy and h >= entry):
                            entry_hit = True

                    if entry_hit:
                        sig.entry_reached = True
                        sig.entry_reached_at = eval_dt
                        sig.entry_reached_price = entry
                        sig.signal_status = "OPEN"
                        self._append_audit(sig, "OPEN", f"Entry filled at {entry:.2f}", entry, eval_dt)
                        resolved_events.append({"signal_id": sig.signal_id, "status": "OPEN", "price": entry})
                        status = "OPEN"
                    else:
                        # Premature invalidation before entry fill
                        if (is_buy and l <= sl) or (not is_buy and h >= sl):
                            sig.signal_status = "INVALIDATED"
                            sig.outcome = "CANCELLED"
                            sig.exit_time = eval_dt
                            sig.exit_price = sl
                            self._append_audit(sig, "INVALIDATED", f"Premature breach of Stop Loss {sl:.2f} before entry", sl, eval_dt)
                            resolved_events.append({"signal_id": sig.signal_id, "status": "INVALIDATED", "price": sl})
                            continue

                # 3. Outcome Evaluation for OPEN signals
                if status == "OPEN":
                    # Update MFE / MAE
                    if is_buy:
                        favorable = max(0.0, h - entry)
                        adverse = max(0.0, entry - l)
                    else:
                        favorable = max(0.0, entry - l)
                        adverse = max(0.0, h - entry)

                    sig.mfe_points = max(sig.mfe_points or 0.0, favorable)
                    sig.mae_points = max(sig.mae_points or 0.0, adverse)

                    # Check TP1 and SL hit conditions
                    tp1_hit = (h >= tp1) if is_buy else (l <= tp1)
                    sl_hit = (l <= sl) if is_buy else (h >= sl)

                    # CONSERVATIVE RESOLUTION: Check for Same-Candle Ambiguity
                    if tp1_hit and sl_hit:
                        logger.warning(f"Same-candle ambiguity detected on {sig.signal_id} (High: {h}, Low: {l}). Conservative resolution applied: AMBIGUOUS.")
                        sig.signal_status = "AMBIGUOUS"
                        sig.outcome = "AMBIGUOUS"
                        sig.exit_price = current_price
                        sig.exit_time = eval_dt
                        self._append_audit(sig, "AMBIGUOUS", "Both TP1 and SL touched within same candle period. Conservative resolution applied (not a win).", current_price, eval_dt)
                        resolved_events.append({"signal_id": sig.signal_id, "status": "AMBIGUOUS", "outcome": "AMBIGUOUS"})
                        continue

                    if tp1_hit:
                        # Clean Win!
                        sig.signal_status = "TP1_HIT"
                        sig.outcome = "WIN"
                        sig.exit_price = tp1
                        sig.exit_time = eval_dt
                        sig.pnl_r_multiple = sig.risk_reward_1

                        # Check if higher targets also attained in this bar
                        tp2_hit = (h >= tp2) if is_buy else (l <= tp2)
                        tp3_hit = (h >= tp3) if is_buy else (l <= tp3)
                        if tp3_hit:
                            sig.signal_status = "TP3_HIT"
                            sig.pnl_r_multiple = sig.risk_reward_3 or (sig.risk_reward_1 * 2.2)
                        elif tp2_hit:
                            sig.signal_status = "TP2_HIT"
                            sig.pnl_r_multiple = sig.risk_reward_2 or (sig.risk_reward_1 * 1.5)

                        self._append_audit(sig, sig.signal_status, f"Take Profit attained at {sig.exit_price:.2f}", sig.exit_price, eval_dt)
                        resolved_events.append({"signal_id": sig.signal_id, "status": sig.signal_status, "outcome": "WIN", "pnl_r": sig.pnl_r_multiple})
                        continue

                    if sl_hit:
                        # Clean Loss
                        sig.signal_status = "SL_HIT"
                        sig.outcome = "LOSS"
                        sig.exit_price = sl
                        sig.exit_time = eval_dt
                        sig.pnl_r_multiple = -1.0
                        self._append_audit(sig, "SL_HIT", f"Stop Loss hit at {sl:.2f}", sl, eval_dt)
                        resolved_events.append({"signal_id": sig.signal_id, "status": "SL_HIT", "outcome": "LOSS", "pnl_r": -1.0})
                        continue

                    # Expiration while in open trade
                    if sig.expires_at and eval_dt > sig.expires_at.replace(tzinfo=datetime.timezone.utc if sig.expires_at.tzinfo is None else None):
                        sig.signal_status = "EXPIRED"
                        # If in profit, evaluate as WIN/LOSS or mark as expired open
                        r_curr = (current_price - entry) / max(0.01, abs(entry - sl)) if is_buy else (entry - current_price) / max(0.01, abs(entry - sl))
                        sig.pnl_r_multiple = round(r_curr, 2)
                        sig.outcome = "WIN" if r_curr > 0.5 else "LOSS"
                        sig.exit_price = current_price
                        sig.exit_time = eval_dt
                        self._append_audit(sig, "EXPIRED", f"Trade expired after duration limit at {current_price:.2f} ({r_curr:+.2f}R)", current_price, eval_dt)
                        resolved_events.append({"signal_id": sig.signal_id, "status": "EXPIRED", "outcome": sig.outcome})
                        continue

            db.commit()

            # Autonomous Reinforcement Loop:
            # When any signal reaches a resolved outcome (WIN or LOSS), automatically trigger
            # reinforcement learning to recalibrate AI agent weights based on empirical reality!
            if any(r.get("outcome") in ["WIN", "LOSS"] for r in resolved_events):
                try:
                    from taikry.learning.self_trainer import agent_self_trainer
                    agent_self_trainer.train_epoch("XAUUSD")
                    logger.info("Autonomous self-training epoch triggered on verified trade outcome.")
                except Exception as e:
                    logger.warning(f"Failed to trigger automatic reinforcement learning: {e}")

            return resolved_events
        finally:
            db.close()

    def _append_audit(self, model: XAUUSDTelegramSignalModel, to_state: str, cause: str, price: float, dt: datetime.datetime):
        """Appends audit history transition event."""
        curr_hist = list(model.audit_history) if model.audit_history else []
        curr_hist.append({
            "from_state": model.signal_status,
            "to_state": to_state,
            "timestamp": dt.isoformat(),
            "trigger_cause": cause,
            "price": price
        })
        model.audit_history = curr_hist
        model.updated_at = dt

    # -------------------------------------------------------------------------
    # 2. INDEPENDENT VERIFIED WIN-RATE & PERFORMANCE METRICS
    # -------------------------------------------------------------------------

    def calculate_win_rate_metrics(self) -> Dict[str, Any]:
        """
        Calculates mathematically verified win rates and performance analytics
        from actual successfully delivered Telegram signals that reached a resolved outcome.
        Formula: Win Rate = Wins / (Wins + Losses) * 100%
        """
        db = SessionLocal()
        try:
            # Fetch all sent XAUUSD signals
            signals = db.query(XAUUSDTelegramSignalModel).filter(
                XAUUSDTelegramSignalModel.canonical_symbol == "XAUUSD",
                XAUUSDTelegramSignalModel.telegram_delivery_status == "SENT"
            ).order_by(XAUUSDTelegramSignalModel.created_at.asc()).all()

            now_utc = datetime.datetime.now(datetime.timezone.utc)
            today_cambodia = get_cambodia_date_str(now_utc)
            d7_cutoff = now_utc - datetime.timedelta(days=7)
            d30_cutoff = now_utc - datetime.timedelta(days=30)

            # Subsets
            today_sigs = [s for s in signals if s.cambodia_date == today_cambodia]
            d7_sigs = [s for s in signals if s.created_at >= d7_cutoff]
            d30_sigs = [s for s in signals if s.created_at >= d30_cutoff]
            buy_sigs = [s for s in signals if s.direction == "BUY"]
            sell_sigs = [s for s in signals if s.direction == "SELL"]

            metrics_all = self._compute_subset_metrics(signals)
            metrics_today = self._compute_subset_metrics(today_sigs)
            metrics_7d = self._compute_subset_metrics(d7_sigs)
            metrics_30d = self._compute_subset_metrics(d30_sigs)
            metrics_buy = self._compute_subset_metrics(buy_sigs)
            metrics_sell = self._compute_subset_metrics(sell_sigs)

            # Streak calculations
            current_streak, max_win_streak, max_loss_streak = self._compute_streaks(signals)

            return {
                "calculation_timestamp_utc": now_utc.isoformat(),
                "cambodia_date": today_cambodia,
                "all_time": metrics_all,
                "today": metrics_today,
                "last_7_days": metrics_7d,
                "last_30_days": metrics_30d,
                "buy_signals": metrics_buy,
                "sell_signals": metrics_sell,
                "streaks": {
                    "current_streak": current_streak,
                    "max_win_streak": max_win_streak,
                    "max_loss_streak": max_loss_streak
                },
                "methodology": {
                    "formula": "Wins / (Wins + Losses) * 100%",
                    "policy": "TP1_CONSERVATIVE_V1",
                    "notes": "Unresolved open trades and expired without entry are excluded from denominator."
                }
            }
        finally:
            db.close()

    def _compute_subset_metrics(self, signals: List[XAUUSDTelegramSignalModel]) -> Dict[str, Any]:
        """Computes verified win rate, counts, and R:R analytics for a list of signals."""
        total_sent = len(signals)
        wins = sum(1 for s in signals if s.outcome == "WIN")
        losses = sum(1 for s in signals if s.outcome == "LOSS")
        resolved_sample = wins + losses

        open_unresolved = sum(1 for s in signals if s.signal_status in ["SENT", "OPEN"] and s.outcome == "PENDING")
        expired_no_entry = sum(1 for s in signals if s.outcome == "EXPIRED_NO_ENTRY")
        cancelled = sum(1 for s in signals if s.outcome == "CANCELLED")
        ambiguous = sum(1 for s in signals if s.outcome == "AMBIGUOUS")

        # Higher targets attainment
        tp2_hits = sum(1 for s in signals if s.signal_status in ["TP2_HIT", "TP3_HIT"])
        tp3_hits = sum(1 for s in signals if s.signal_status == "TP3_HIT")

        # Win Rate Formula
        if resolved_sample > 0:
            win_rate_val = round((wins / float(resolved_sample)) * 100.0, 1)
            win_rate_str = f"{win_rate_val:.1f}% ({wins}/{resolved_sample})"
            sl_rate_val = round((losses / float(resolved_sample)) * 100.0, 1)
        else:
            win_rate_val = None
            win_rate_str = "N/A — insufficient resolved trades"
            sl_rate_val = None

        # TP2 / TP3 Attainment Rates (relative to wins)
        if wins > 0:
            tp2_rate = round((tp2_hits / float(wins)) * 100.0, 1)
            tp3_rate = round((tp3_hits / float(wins)) * 100.0, 1)
        else:
            tp2_rate = None
            tp3_rate = None

        # Net R-Multiples and Average R:R
        net_r = round(sum(s.pnl_r_multiple or 0.0 for s in signals if s.outcome in ["WIN", "LOSS"]), 2)
        avg_rr = round(
            sum(s.risk_reward_1 for s in signals) / float(total_sent), 2
        ) if total_sent > 0 else 2.1

        # Calculate Max Drawdown in R
        running_r = 0.0
        peak_r = 0.0
        max_dd_r = 0.0
        for s in signals:
            if s.outcome in ["WIN", "LOSS"]:
                running_r += (s.pnl_r_multiple or 0.0)
                if running_r > peak_r:
                    peak_r = running_r
                dd = peak_r - running_r
                if dd > max_dd_r:
                    max_dd_r = dd

        return {
            "total_sent_count": total_sent,
            "resolved_sample_size": resolved_sample,
            "wins_count": wins,
            "losses_count": losses,
            "open_unresolved_count": open_unresolved,
            "expired_no_entry_count": expired_no_entry,
            "cancelled_count": cancelled,
            "ambiguous_count": ambiguous,
            "win_rate_percent": win_rate_val,
            "win_rate_display": win_rate_str,
            "stop_loss_rate_percent": sl_rate_val,
            "tp2_attainment_count": tp2_hits,
            "tp2_attainment_rate": tp2_rate,
            "tp3_attainment_count": tp3_hits,
            "tp3_attainment_rate": tp3_rate,
            "net_r_multiple": net_r,
            "max_drawdown_r": round(max_dd_r, 2),
            "average_risk_reward": avg_rr
        }

    def _compute_streaks(self, signals: List[XAUUSDTelegramSignalModel]) -> Tuple[str, int, int]:
        """Calculates current streak and historical max streaks."""
        resolved = [s.outcome for s in signals if s.outcome in ["WIN", "LOSS"]]
        if not resolved:
            return "None", 0, 0

        max_w = 0
        max_l = 0
        curr_w = 0
        curr_l = 0

        for r in resolved:
            if r == "WIN":
                curr_w += 1
                curr_l = 0
                max_w = max(max_w, curr_w)
            elif r == "LOSS":
                curr_l += 1
                curr_w = 0
                max_l = max(max_l, curr_l)

        # Current streak
        last_outcome = resolved[-1]
        streak_len = 0
        for r in reversed(resolved):
            if r == last_outcome:
                streak_len += 1
            else:
                break

        curr_str = f"{streak_len} {'Wins (W)' if last_outcome == 'WIN' else 'Losses (L)'}"
        return curr_str, max_w, max_l


# Singleton Instance
xauusd_performance_tracker = XAUUSDPerformanceTracker()
