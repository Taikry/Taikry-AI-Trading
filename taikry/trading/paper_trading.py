"""
Institutional Paper Trading Engine for TAIKRY AI MARKET INTELLIGENCE PRO
Simulates paper-only trade records with:
- Position sizing based on configured equity risk
- Spread, commission, and slippage simulation
- Stop-Loss and Take-Profit tracking
- Daily drawdown circuit breaker (2.5% max daily loss)
- Full SQLite/PostgreSQL persistence and audit logging
"""
import datetime
import math
from typing import Dict, Any, List, Optional
from taikry.config import (
    INITIAL_PAPER_BALANCE,
    RISK_PER_TRADE_PERCENT,
    MAX_RISK_PER_TRADE_PERCENT,
    MAX_DAILY_LOSS_PERCENT,
    MAX_SIMULTANEOUS_POSITIONS,
    MIN_RISK_REWARD_RATIO,
    SLIPPAGE_PIPS,
    COMMISSION_PER_LOT,
    get_symbol_config
)
from taikry.database.session import SessionLocal
from taikry.database.models import PaperTrade

class PaperTradingEngine:
    """Simulated execution and position manager."""

    def __init__(self):
        self.initial_balance = INITIAL_PAPER_BALANCE

    def get_account_summary(self) -> Dict[str, Any]:
        """Calculates current paper balance, equity, and realized PnL."""
        db = SessionLocal()
        try:
            trades = db.query(PaperTrade).all()
            realized_pnl = sum(t.pnl for t in trades if t.status == "CLOSED")
            open_trades = [t for t in trades if t.status == "OPEN"]

            balance = round(self.initial_balance + realized_pnl, 2)
            # Floating PnL will be added when market prices are checked
            equity = balance

            return {
                "initial_balance": self.initial_balance,
                "current_balance": balance,
                "current_equity": equity,
                "total_trades": len(trades),
                "open_trades_count": len(open_trades),
                "closed_trades_count": len(trades) - len(open_trades),
                "realized_pnl": round(realized_pnl, 2),
                "currency": "USD"
            }
        finally:
            db.close()

    def check_daily_loss_limit(self) -> bool:
        """
        Circuit breaker: Checks if today's closed losses exceed MAX_DAILY_LOSS_PERCENT (2.5%).
        """
        db = SessionLocal()
        try:
            today_start = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            today_trades = db.query(PaperTrade).filter(
                PaperTrade.status == "CLOSED",
                PaperTrade.exit_time >= today_start
            ).all()

            today_loss = sum(t.pnl for t in today_trades if t.pnl < 0)
            max_allowed_loss = -(self.initial_balance * (MAX_DAILY_LOSS_PERCENT / 100.0))

            if today_loss <= max_allowed_loss:
                return False  # Limit breached
            return True
        finally:
            db.close()

    def open_trade(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit_1: float,
        take_profit_2: Optional[float] = None,
        risk_percentage: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Opens a simulated paper trade with configured risk and modeled friction.
        """
        direction = direction.upper()
        if direction not in ("BUY", "SELL"):
            return {"success": False, "reason": "Direction must be BUY or SELL."}
        try:
            entry_price = float(entry_price)
            stop_loss = float(stop_loss)
            take_profit_1 = float(take_profit_1)
            take_profit_2 = float(take_profit_2) if take_profit_2 is not None else None
            effective_risk_pct = RISK_PER_TRADE_PERCENT if risk_percentage is None else float(risk_percentage)
        except (TypeError, ValueError):
            return {"success": False, "reason": "Prices and risk percentage must be valid numbers."}
        numeric_levels = [entry_price, stop_loss, take_profit_1] + ([take_profit_2] if take_profit_2 is not None else [])
        if not all(math.isfinite(level) and level > 0 for level in numeric_levels):
            return {"success": False, "reason": "All supplied price levels must be finite positive values."}
        if not 0 < effective_risk_pct <= MAX_RISK_PER_TRADE_PERCENT:
            return {"success": False, "reason": f"Risk percentage must be above 0 and at most {MAX_RISK_PER_TRADE_PERCENT:g}%."}
        if (direction == "BUY" and not stop_loss < entry_price < take_profit_1) or (direction == "SELL" and not stop_loss > entry_price > take_profit_1):
            return {"success": False, "reason": "Entry, stop-loss, and take-profit levels do not match the trade direction."}
        if take_profit_2 is not None and (
            (direction == "BUY" and take_profit_2 <= take_profit_1)
            or (direction == "SELL" and take_profit_2 >= take_profit_1)
        ):
            return {"success": False, "reason": "Take-profit 2 must be beyond take-profit 1 in the trade direction."}
        configured_rr = abs(take_profit_1 - entry_price) / abs(entry_price - stop_loss)
        if configured_rr < MIN_RISK_REWARD_RATIO:
            return {
                "success": False,
                "reason": f"Take-profit 1 offers R:R 1:{configured_rr:.2f}, below the configured 1:{MIN_RISK_REWARD_RATIO:g} minimum.",
            }

        cfg = get_symbol_config(symbol)
        decimals = cfg.get("decimals", 2)
        lot_size_multiplier = cfg.get("lot_size", 100)
        pip_val = cfg.get("pip_value", 0.1)

        # 1. Circuit breaker checks
        if not self.check_daily_loss_limit():
            return {
                "success": False,
                "reason": f"Daily loss limit ({MAX_DAILY_LOSS_PERCENT}%) breached. Trading paused for today."
            }

        db = SessionLocal()
        try:
            open_count = db.query(PaperTrade).filter(PaperTrade.status == "OPEN").count()
            if open_count >= MAX_SIMULTANEOUS_POSITIONS:
                return {
                    "success": False,
                    "reason": f"Maximum open position limit ({MAX_SIMULTANEOUS_POSITIONS}) reached."
                }

            # 2. Apply simulated slippage
            slippage_amount = SLIPPAGE_PIPS * pip_val
            actual_entry = entry_price + slippage_amount if direction == "BUY" else entry_price - slippage_amount
            actual_entry = round(actual_entry, decimals)
            if (direction == "BUY" and not stop_loss < actual_entry < take_profit_1) or (direction == "SELL" and not stop_loss > actual_entry > take_profit_1):
                return {"success": False, "reason": "Modeled slippage moves entry outside the approved price range."}
            actual_rr = abs(take_profit_1 - actual_entry) / abs(actual_entry - stop_loss)
            if actual_rr < MIN_RISK_REWARD_RATIO:
                return {
                    "success": False,
                    "reason": f"Modeled slippage reduces R:R to 1:{actual_rr:.2f}, below the configured minimum 1:{MIN_RISK_REWARD_RATIO:g}.",
                }

            # 3. Position Sizing
            risk_pts = abs(actual_entry - stop_loss)
            if risk_pts <= 0:
                return {"success": False, "reason": "Invalid Stop Loss equal to Entry price."}

            account = self.get_account_summary()
            current_balance = account["current_balance"]
            max_risk_dollars = current_balance * (effective_risk_pct / 100.0)

            # Calculate volume in lots
            raw_lots = max_risk_dollars / (risk_pts * lot_size_multiplier)
            if raw_lots < 0.01:
                return {
                    "success": False,
                    "reason": "Minimum supported position size would exceed the configured risk limit."
                }
            calculated_lots = min(10.0, math.floor(raw_lots * 100) / 100.0)
            actual_risk_dollars = risk_pts * lot_size_multiplier * calculated_lots

            # 4. Commission
            est_commission = round(COMMISSION_PER_LOT * calculated_lots, 2)

            trade = PaperTrade(
                symbol=symbol,
                direction=direction,
                entry_price=actual_entry,
                stop_loss=round(stop_loss, decimals),
                take_profit_1=round(take_profit_1, decimals),
                take_profit_2=round(take_profit_2, decimals) if take_profit_2 else None,
                lot_size=calculated_lots,
                risk_amount=round(actual_risk_dollars, 2),
                balance_before=current_balance,
                status="OPEN",
                trade_log={
                    "slippage_applied_pips": SLIPPAGE_PIPS,
                    "commission_usd": est_commission,
                    "opened_at": datetime.datetime.utcnow().isoformat()
                }
            )
            db.add(trade)
            db.commit()
            db.refresh(trade)

            return {
                "success": True,
                "trade_id": trade.id,
                "symbol": symbol,
                "direction": direction,
                "entry_price": actual_entry,
                "stop_loss": stop_loss,
                "take_profit_1": take_profit_1,
                "lot_size": calculated_lots,
                "risk_amount": round(actual_risk_dollars, 2),
                "risk_percentage": round((actual_risk_dollars / current_balance) * 100.0, 4) if current_balance > 0 else 0.0,
                "balance_before": current_balance,
                "commission": est_commission,
                "status": "OPEN"
            }
        finally:
            db.close()

    def update_open_trades(self, current_prices: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        Evaluates active trades against current prices to trigger TP/SL hits.
        """
        closed_events = []
        db = SessionLocal()
        try:
            open_trades = db.query(PaperTrade).filter(PaperTrade.status == "OPEN").all()
            for t in open_trades:
                price = current_prices.get(t.symbol)
                if not price or price <= 0:
                    continue

                cfg = get_symbol_config(t.symbol)
                lot_mult = cfg.get("lot_size", 100)

                hit_sl = False
                hit_tp1 = False
                hit_tp2 = False
                exit_price = price
                exit_reason = None

                if t.direction == "BUY":
                    if price <= t.stop_loss:
                        hit_sl = True
                        exit_price = t.stop_loss
                        exit_reason = "HIT_SL"
                    elif t.take_profit_2 and price >= t.take_profit_2:
                        hit_tp2 = True
                        exit_price = t.take_profit_2
                        exit_reason = "HIT_TP2"
                    elif price >= t.take_profit_1:
                        hit_tp1 = True
                        exit_price = t.take_profit_1
                        exit_reason = "HIT_TP1"

                    pts = exit_price - t.entry_price
                else: # SELL
                    if price >= t.stop_loss:
                        hit_sl = True
                        exit_price = t.stop_loss
                        exit_reason = "HIT_SL"
                    elif t.take_profit_2 and price <= t.take_profit_2:
                        hit_tp2 = True
                        exit_price = t.take_profit_2
                        exit_reason = "HIT_TP2"
                    elif price <= t.take_profit_1:
                        hit_tp1 = True
                        exit_price = t.take_profit_1
                        exit_reason = "HIT_TP1"

                    pts = t.entry_price - exit_price

                if hit_sl or hit_tp1 or hit_tp2:
                    gross_pnl = pts * lot_mult * t.lot_size
                    commission = t.trade_log.get("commission_usd", 7.0) if t.trade_log else 7.0
                    net_pnl = round(gross_pnl - commission, 2)
                    risk_dollars = t.risk_amount if t.risk_amount > 0 else 500.0
                    r_mult = round(net_pnl / risk_dollars, 2)

                    t.status = "CLOSED"
                    t.exit_price = exit_price
                    t.exit_time = datetime.datetime.utcnow()
                    t.pnl = net_pnl
                    t.r_multiple = r_mult
                    t.exit_reason = exit_reason

                    closed_events.append({
                        "trade_id": t.id,
                        "symbol": t.symbol,
                        "direction": t.direction,
                        "exit_price": exit_price,
                        "exit_reason": exit_reason,
                        "net_pnl": net_pnl,
                        "r_multiple": r_mult
                    })

            if closed_events:
                db.commit()

            return closed_events
        finally:
            db.close()

    # -------------------------------------------------------------------------
    # SHADOW MODE STRICT SAFETY ENFORCEMENT
    # -------------------------------------------------------------------------

    @property
    def is_shadow_mode(self) -> bool:
        """Returns True: Engine runs in strictly non-executable shadow simulation mode."""
        return True

    @property
    def can_place_live_orders(self) -> bool:
        """Strict safety invariant: Shadow mode is prohibited from live order execution."""
        return False

    def place_live_broker_order(self, *args, **kwargs):
        """Security guard: raises PermissionError to enforce Shadow Mode separation."""
        raise PermissionError(
            "SECURITY VETO: Shadow mode has zero permission to place live broker orders. "
            "Real order routing must run through a separate explicitly authorized execution service."
        )


paper_trading_engine = PaperTradingEngine()

