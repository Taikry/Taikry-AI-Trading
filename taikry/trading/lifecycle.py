"""
Deterministic Signal Lifecycle State Machine for TAIKRY AI MARKET INTELLIGENCE PRO
==================================================================================
Signals are treated as stateful, persistent entities with deterministic idempotency.

Lifecycle States:
1. CANDIDATE: Initial bias/pattern identified by analysis agents
2. WAITING_CONFIRMATION: Validated setup awaiting entry trigger / candle confirmation
3. ACTIVE: Entry reached, live SL & TP monitoring engaged
4. TARGET_HIT: Take profit 1 or 2 achieved (tracks partial closures)
5. STOP_HIT: Stop loss breached
6. INVALIDATED: Setup negated prior to entry by contrary structure or news blackout
7. EXPIRED: Time window elapsed without entry execution

Explicit Lifecycle Events:
- SIGNAL_CREATED
- SIGNAL_UPDATED
- ENTRY_ZONE_REACHED
- ENTRY_CONFIRMED
- TP1_HIT
- TP2_HIT
- TP3_HIT
- SL_HIT
- SIGNAL_EXPIRED
- SIGNAL_CANCELLED
- SIGNAL_CLOSED

Guarantees:
- Persistent event deduplication via unique idempotency key (signal_id:event_type:transition_index).
- Atomic event claiming across concurrent workers.
- At-most-once delivery on Telegram timeouts (UNCERTAIN_TIMEOUT).
- Accurate event naming (ENTRY_ZONE_REACHED when price touches zone, no fabricated fills).
- Decouples high-frequency price updates from Telegram notifications.
"""

import time
import uuid
import datetime
import logging
from typing import Dict, Any, List, Optional
from enum import Enum

from taikry.database.session import SessionLocal
from taikry.database.models import (
    SignalLifecycleModel,
    SignalLifecycleEventModel,
    LifecycleEventType,
    EventDeliveryStatus
)
# from taikry.notifications.telegram_service import telegram_service (lazy imported in _notify_transition to avoid circular import)
from taikry.notifications.make_webhook_dispatcher import dispatch_to_make
from taikry.config import TELEGRAM_CHAT_ID, RISK_PER_TRADE_PERCENT

logger = logging.getLogger("taikry.trading.lifecycle")


class SignalState(str, Enum):
    CANDIDATE = "CANDIDATE"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    ACTIVE = "ACTIVE"
    TARGET_HIT = "TARGET_HIT"
    STOP_HIT = "STOP_HIT"
    CLOSED = "CLOSED"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"


# Allowed state transitions
VALID_TRANSITIONS = {
    SignalState.CANDIDATE: [SignalState.WAITING_CONFIRMATION, SignalState.INVALIDATED, SignalState.EXPIRED],
    SignalState.WAITING_CONFIRMATION: [SignalState.ACTIVE, SignalState.INVALIDATED, SignalState.EXPIRED],
    SignalState.ACTIVE: [SignalState.TARGET_HIT, SignalState.STOP_HIT, SignalState.EXPIRED, SignalState.INVALIDATED, SignalState.CLOSED],
    SignalState.TARGET_HIT: [SignalState.TARGET_HIT, SignalState.STOP_HIT, SignalState.EXPIRED, SignalState.INVALIDATED, SignalState.CLOSED],
    SignalState.STOP_HIT: [],
    SignalState.CLOSED: [],
    SignalState.INVALIDATED: [],
    SignalState.EXPIRED: []
}


class SignalLifecycleManager:
    """Manages the full state machine lifecycle of institutional trading signals."""

    def __init__(self):
        self.default_expiry_hours = 6

    def attach_telegram_message(
        self,
        signal_id: str,
        message_id: str,
        take_profit_3: Optional[float] = None,
    ) -> bool:
        """Attach its Telegram message and optional third target to the lifecycle record."""
        db = SessionLocal()
        try:
            update_values = {
                "telegram_message_id": str(message_id),
                "updated_at": datetime.datetime.now(datetime.timezone.utc),
            }
            if take_profit_3 is not None:
                update_values["take_profit_3"] = float(take_profit_3)
            updated = db.query(SignalLifecycleModel).filter(
                SignalLifecycleModel.signal_id == signal_id
            ).update({
                **update_values
            }, synchronize_session=False)
            db.commit()
            return updated == 1
        except Exception as exc:
            db.rollback()
            logger.warning("Could not attach Telegram message to lifecycle signal %s: %s", signal_id, str(exc))
            return False
        finally:
            db.close()

    def generate_signal_id(self, symbol: str) -> str:
        date_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")
        rand_suffix = uuid.uuid4().hex[:6].upper()
        return f"SIG-{date_str}-{symbol}-{rand_suffix}"

    def create_signal(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit_1: float,
        take_profit_2: Optional[float] = None,
        risk_reward: str = "N/A",
        ai_score: Optional[int] = None,
        timeframe: str = "M15",
        initial_state: SignalState = SignalState.WAITING_CONFIRMATION,
        trigger_cause: str = "Multi-agent institutional consensus approval",
        take_profit_3: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Creates and persists a stateful signal record with persistent deduplication.
        Suppresses duplicate creation if an unexpired signal with matching parameters exists.
        """
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        db = SessionLocal()
        try:
            # Check for existing active or waiting signal for this symbol
            existing = db.query(SignalLifecycleModel).filter(
                SignalLifecycleModel.symbol == symbol.upper(),
                SignalLifecycleModel.current_state.in_([
                    SignalState.WAITING_CONFIRMATION.value,
                    SignalState.ACTIVE.value,
                    SignalState.TARGET_HIT.value,
                ])
            ).order_by(SignalLifecycleModel.created_at.desc()).first()

            if existing:
                exp = existing.expires_at
                if exp and exp.tzinfo is None:
                    exp = exp.replace(tzinfo=datetime.timezone.utc)
                is_unexpired = not (exp and now_dt > exp)

                price_diff = abs(existing.entry_price - entry_price) / max(entry_price, 1.0)
                same_dir = (existing.direction.upper() == direction.upper())

                if is_unexpired and same_dir and price_diff < 0.002:
                    # Immaterial price variation and same direction -> Reuse existing signal
                    logger.debug(f"Reusing existing active signal {existing.signal_id} for {symbol}. Duplicate creation suppressed.")
                    return self._model_to_dict(existing)

                # Material change or direction flipped on unexpired setup: Invalidate existing first
                if is_unexpired and (not same_dir or price_diff >= 0.002):
                    self.transition_signal(
                        existing.signal_id,
                        SignalState.INVALIDATED,
                        f"Superseded by updated analysis: {direction.upper()} {symbol}",
                        entry_price,
                        reason_en=f"Setup replaced by new high-confluence {direction.upper()} analysis.",
                        reason_kh=f"ការវិភាគត្រូវបានជំនួសដោយសញ្ញា {direction.upper()} ថ្មីដែលមានកម្រិតជឿជាក់ខ្ពស់។",
                        event_type=LifecycleEventType.SIGNAL_CANCELLED
                    )

            sig_id = self.generate_signal_id(symbol)
            expires_at = now_dt + datetime.timedelta(hours=self.default_expiry_hours)

            history_entry = {
                "from_state": None,
                "to_state": initial_state.value,
                "timestamp": now_dt.isoformat(),
                "trigger_cause": trigger_cause,
                "price": entry_price
            }

            model = SignalLifecycleModel(
                signal_id=sig_id,
                symbol=symbol.upper(),
                timeframe=timeframe,
                direction=direction.upper(),
                current_state=initial_state.value,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit_1=take_profit_1,
                take_profit_2=take_profit_2,
                take_profit_3=take_profit_3,
                risk_reward=risk_reward,
                ai_score=ai_score,
                state_history=[history_entry],
                created_at=now_dt,
                updated_at=now_dt,
                expires_at=expires_at
            )
            db.add(model)
            db.commit()
            db.refresh(model)

            # Persist initial creation event for idempotency
            idempotency_key = f"{sig_id}:{LifecycleEventType.SIGNAL_CREATED.value}:1"
            ev_model = SignalLifecycleEventModel(
                signal_id=sig_id,
                event_type=LifecycleEventType.SIGNAL_CREATED.value,
                transition_index=1,
                idempotency_key=idempotency_key,
                symbol=symbol.upper(),
                direction=direction.upper(),
                timeframe=timeframe,
                price=entry_price,
                trigger_cause=trigger_cause,
                reason_en="Signal created from institutional consensus approval.",
                reason_kh="សញ្ញាត្រូវបានបង្កើតឡើងពីការអនុម័តមតិឯកភាពស្ថាប័ន។",
                from_state=None,
                to_state=initial_state.value,
                delivery_status=EventDeliveryStatus.PENDING.value,
                created_at=now_dt,
                updated_at=now_dt
            )
            db.add(ev_model)
            db.commit()

            return self._model_to_dict(model)
        finally:
            db.close()

    def transition_signal(
        self,
        signal_id: str,
        to_state: SignalState,
        trigger_cause: str,
        current_price: float,
        reason_en: Optional[str] = None,
        reason_kh: Optional[str] = None,
        event_type: Optional[LifecycleEventType] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Validates transition, persists new state with audit history,
        records deduplicated event in SignalLifecycleEventModel, and
        dispatches notification only if valid and previously unprocessed.
        """
        db = SessionLocal()
        try:
            model = db.query(SignalLifecycleModel).filter(
                SignalLifecycleModel.signal_id == signal_id
            ).first()

            if not model:
                return None

            current_st = SignalState(model.current_state)
            allowed = VALID_TRANSITIONS.get(current_st, [])

            if to_state not in allowed:
                logger.warning(f"Illegal transition requested for {signal_id}: {current_st} -> {to_state}")
                return None

            now_dt = datetime.datetime.now(datetime.timezone.utc)
            history_list = list(model.state_history) if model.state_history else []
            transition_index = len(history_list) + 1

            # Infer event type if not explicitly supplied
            if not event_type:
                if to_state == SignalState.ACTIVE:
                    event_type = LifecycleEventType.ENTRY_ZONE_REACHED
                elif to_state == SignalState.TARGET_HIT:
                    tp1_already = any(
                        h.get("event_type") == LifecycleEventType.TP1_HIT.value or "Take profit 1" in h.get("trigger_cause", "")
                        for h in history_list
                    )
                    event_type = LifecycleEventType.TP2_HIT if tp1_already else LifecycleEventType.TP1_HIT
                elif to_state == SignalState.STOP_HIT:
                    event_type = LifecycleEventType.SL_HIT
                elif to_state == SignalState.INVALIDATED:
                    event_type = LifecycleEventType.SIGNAL_CANCELLED
                elif to_state == SignalState.EXPIRED:
                    event_type = LifecycleEventType.SIGNAL_EXPIRED
                elif to_state == SignalState.CLOSED:
                    event_type = LifecycleEventType.SIGNAL_CLOSED
                else:
                    event_type = LifecycleEventType.SIGNAL_UPDATED

            history_list.append({
                "from_state": current_st.value,
                "to_state": to_state.value,
                "event_type": event_type.value,
                "transition_index": transition_index,
                "timestamp": now_dt.isoformat(),
                "trigger_cause": trigger_cause,
                "price": current_price,
                "reason_en": reason_en,
                "reason_kh": reason_kh
            })

            model.current_state = to_state.value
            model.state_history = history_list
            model.updated_at = now_dt

            if reason_en:
                model.invalidation_reason_en = reason_en
            if reason_kh:
                model.invalidation_reason_kh = reason_kh

            # Idempotency Key: {signal_id}:{event_type}:{transition_index}
            idempotency_key = f"{signal_id}:{event_type.value}:{transition_index}"

            # Atomic check / insert in SignalLifecycleEventModel
            existing_ev = db.query(SignalLifecycleEventModel).filter(
                SignalLifecycleEventModel.idempotency_key == idempotency_key
            ).first()

            event_id = None
            if not existing_ev:
                ev_model = SignalLifecycleEventModel(
                    signal_id=signal_id,
                    event_type=event_type.value,
                    transition_index=transition_index,
                    idempotency_key=idempotency_key,
                    symbol=model.symbol,
                    direction=model.direction,
                    timeframe=model.timeframe,
                    price=current_price,
                    trigger_cause=trigger_cause,
                    reason_en=reason_en,
                    reason_kh=reason_kh,
                    from_state=current_st.value,
                    to_state=to_state.value,
                    delivery_status=EventDeliveryStatus.PENDING.value,
                    created_at=now_dt,
                    updated_at=now_dt
                )
                db.add(ev_model)
                db.commit()
                db.refresh(ev_model)
                event_id = ev_model.id
            else:
                event_id = existing_ev.id
                db.commit()

            db.refresh(model)
            data = self._model_to_dict(model)

            # Dispatch deduplicated notification
            self._notify_transition(
                data,
                to_state,
                event_type,
                idempotency_key,
                event_id,
                trigger_cause,
                current_price,
                reason_en,
                reason_kh
            )
            return data
        finally:
            db.close()

    def evaluate_signals(self, current_prices: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        Deterministic tick evaluator.
        Audits WAITING_CONFIRMATION and ACTIVE signals against incoming market prices.
        Decouples price streaming from Telegram notification generation.
        Sends notifications ONLY when a genuine, valid, previously unprocessed lifecycle transition occurs.
        """
        updated_events = []
        db = SessionLocal()
        try:
            active_or_waiting = db.query(SignalLifecycleModel).filter(
                SignalLifecycleModel.current_state.in_([
                    SignalState.WAITING_CONFIRMATION.value,
                    SignalState.ACTIVE.value,
                    SignalState.TARGET_HIT.value,
                ])
            ).all()

            now_dt = datetime.datetime.now(datetime.timezone.utc)

            for sig in active_or_waiting:
                sym = sig.symbol
                price = current_prices.get(sym)
                if not price or price <= 0:
                    continue

                curr_st = SignalState(sig.current_state)
                is_buy = sig.direction in ["BUY", "LONG"]

                # 1. Expiration Check
                if sig.expires_at:
                    sig_exp = sig.expires_at
                    if sig_exp.tzinfo is None:
                        sig_exp = sig_exp.replace(tzinfo=datetime.timezone.utc)
                    if now_dt > sig_exp:
                        ev = self.transition_signal(
                            sig.signal_id,
                            SignalState.EXPIRED,
                            "Time horizon elapsed without execution",
                            price,
                            reason_en="Signal expired: Analysis time window exceeded without entry fill.",
                            reason_kh="សញ្ញាផុតកំណត់៖ រយៈពេលវិភាគបានកន្លងផុតដោយគ្មានការចូលជួញដូរ។",
                            event_type=LifecycleEventType.SIGNAL_EXPIRED
                        )
                        if ev:
                            updated_events.append(ev)
                        continue

                # 2. WAITING_CONFIRMATION Evaluation
                if curr_st == SignalState.WAITING_CONFIRMATION:
                    # Premature invalidation check (price moves past SL before reaching entry)
                    if (is_buy and price <= sig.stop_loss) or (not is_buy and price >= sig.stop_loss):
                        breach_side = "dropped to" if is_buy else "rose to"
                        breach_side_kh = "ធ្លាក់ចុះដល់" if is_buy else "ឡើងដល់"
                        ev = self.transition_signal(
                            sig.signal_id,
                            SignalState.INVALIDATED,
                            "Price broke invalidation level prior to entry",
                            price,
                            reason_en=f"Market structure invalidated: Price {breach_side} {price:.2f} breaching Stop Loss level {sig.stop_loss:.2f} prior to entry fill.",
                            reason_kh=f"រចនាសម្ព័ន្ធទីផ្សារត្រូវបានរំលោភ៖ តម្លៃបាន{breach_side_kh} {price:.2f} បំពានចំណុចទប់ស្កាត់ខាត {sig.stop_loss:.2f} មុនពេលចូលជួញដូរ។",
                            event_type=LifecycleEventType.SIGNAL_CANCELLED
                        )
                        if ev:
                            updated_events.append(ev)
                        continue

                    # Trigger Entry Check (Pullback/Rally into Entry Zone)
                    tolerance = sig.entry_price * 0.0005  # 0.05% tolerance zone
                    entry_triggered = False
                    if is_buy and price <= (sig.entry_price + tolerance):
                        entry_triggered = True
                    elif not is_buy and price >= (sig.entry_price - tolerance):
                        entry_triggered = True

                    if entry_triggered:
                        ev = self.transition_signal(
                            sig.signal_id,
                            SignalState.ACTIVE,
                            f"Price reached entry target zone ({price:.2f})",
                            price,
                            reason_en=f"Price reached entry target zone ({price:.2f}). Trade is now ACTIVE under live market surveillance.",
                            reason_kh=f"តម្លៃបានមកដល់តំបន់គោលដៅចូលជួញដូរ ({price:.2f})។ ការជួញដូរបានក្លាយជា ACTIVE ក្រោមការតាមដានទីផ្សារផ្ទាល់។",
                            event_type=LifecycleEventType.ENTRY_ZONE_REACHED
                        )
                        if ev:
                            updated_events.append(ev)
                        continue

                # 3. ACTIVE Evaluation
                elif curr_st in {SignalState.ACTIVE, SignalState.TARGET_HIT}:
                    # Stop Loss check
                    sl_hit = (price <= sig.stop_loss) if is_buy else (price >= sig.stop_loss)
                    if sl_hit:
                        ev = self.transition_signal(
                            sig.signal_id,
                              SignalState.STOP_HIT,
                            f"Stop loss triggered at {price:.2f}",
                            price,
                            reason_en=f"Stop loss triggered at {price:.2f}. Planned risk was capped at {RISK_PER_TRADE_PERCENT:g}% of equity.",
                            reason_kh=f"តម្លៃបានប៉ះ Stop Loss នៅ {price:.2f}។ ហានិភ័យដែលបានកំណត់គឺមិនលើស {RISK_PER_TRADE_PERCENT:g}% នៃទុនគណនីទេ។",
                            event_type=LifecycleEventType.SL_HIT
                        )
                        if ev:
                            updated_events.append(ev)
                        continue

                    # Evaluate each target once. TP2/TP3 are no longer skipped
                    # after the first target transition; all levels are stored
                    # as real milestones without claiming a broker stop move.
                    history = sig.state_history if isinstance(sig.state_history, list) else []
                    completed_targets = {
                        str(item.get("event_type"))
                        for item in history
                        if isinstance(item, dict) and item.get("event_type")
                    }
                    tp1_hit = (price >= sig.take_profit_1) if is_buy else (price <= sig.take_profit_1)
                    tp2_hit = bool(sig.take_profit_2 and ((price >= sig.take_profit_2) if is_buy else (price <= sig.take_profit_2)))
                    tp3_hit = bool(sig.take_profit_3 and ((price >= sig.take_profit_3) if is_buy else (price <= sig.take_profit_3)))

                    if tp3_hit and LifecycleEventType.TP3_HIT.value not in completed_targets:
                        ev = self.transition_signal(
                            sig.signal_id,
                            SignalState.CLOSED,
                            f"Take profit 3 final target achieved at {price:.2f}",
                            price,
                            reason_en=f"Take Profit 3 reached at {price:.2f}. The monitored signal is closed.",
                            reason_kh=f"បានដល់គោលដៅប្រាក់ចំណេញទី ៣ នៅ {price:.2f}។ សញ្ញាតាមដានត្រូវបានបិទ។",
                            event_type=LifecycleEventType.TP3_HIT,
                        )
                        if ev:
                            updated_events.append(ev)
                        continue

                    if tp2_hit and LifecycleEventType.TP2_HIT.value not in completed_targets:
                        final_target = sig.take_profit_3 is None
                        ev = self.transition_signal(
                            sig.signal_id,
                            SignalState.CLOSED if final_target else SignalState.TARGET_HIT,
                            f"Take profit 2 target achieved at {price:.2f}",
                            price,
                            reason_en=(
                                f"Take Profit 2 reached at {price:.2f}. The monitored signal is closed."
                                if final_target else f"Take Profit 2 reached at {price:.2f}; monitoring continues for TP3."
                            ),
                            reason_kh=(
                                f"បានដល់គោលដៅប្រាក់ចំណេញទី ២ នៅ {price:.2f} ហើយសញ្ញាត្រូវបានបិទ។"
                                if final_target else f"បានដល់គោលដៅប្រាក់ចំណេញទី ២ នៅ {price:.2f}។ កំពុងបន្តតាមដាន TP3។"
                            ),
                            event_type=LifecycleEventType.TP2_HIT,
                        )
                        if ev:
                            updated_events.append(ev)
                        continue

                    if tp1_hit and LifecycleEventType.TP1_HIT.value not in completed_targets:
                        ev = self.transition_signal(
                            sig.signal_id,
                            SignalState.TARGET_HIT,
                            f"Take profit 1 primary target achieved at {price:.2f}",
                            price,
                            reason_en=f"Take Profit 1 reached at {price:.2f}. The signal remains under lifecycle monitoring; no stop change or broker order was made.",
                            reason_kh=f"បានដល់គោលដៅប្រាក់ចំណេញទី ១ នៅ {price:.2f}។ សញ្ញានៅតែស្ថិតក្រោមការតាមដាន ហើយមិនបានផ្លាស់ប្តូរ Stop Loss ឬដាក់បញ្ជាទៅក្រុមហ៊ុនជើងសារទេ។",
                            event_type=LifecycleEventType.TP1_HIT,
                        )
                        if ev:
                            updated_events.append(ev)
                        continue

            return updated_events
        finally:
            db.close()

    def get_signals(
        self,
        state: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Queries stored signals with optional state and symbol filters."""
        db = SessionLocal()
        try:
            q = db.query(SignalLifecycleModel)
            if state:
                q = q.filter(SignalLifecycleModel.current_state == state.upper())
            if symbol:
                q = q.filter(SignalLifecycleModel.symbol == symbol.upper())
            q = q.order_by(SignalLifecycleModel.created_at.desc()).limit(limit)
            models = q.all()
            return [self._model_to_dict(m) for m in models]
        finally:
            db.close()

    def get_signal_by_id(self, signal_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single signal by its unique ID."""
        db = SessionLocal()
        try:
            m = db.query(SignalLifecycleModel).filter(
                SignalLifecycleModel.signal_id == signal_id
            ).first()
            return self._model_to_dict(m) if m else None
        finally:
            db.close()

    def _notify_transition(
        self,
        signal_data: Dict[str, Any],
        to_state: SignalState,
        event_type: LifecycleEventType,
        idempotency_key: str,
        event_id: int,
        trigger_cause: str,
        price: float,
        reason_en: Optional[str],
        reason_kh: Optional[str]
    ):
        """Dispatches state transition events via persistent idempotent handler."""
        event_dict = {
            "event_id": event_id,
            "signal_id": signal_data["signal_id"],
            "event_type": event_type.value,
            "idempotency_key": idempotency_key,
            "symbol": signal_data["symbol"],
            "direction": signal_data["direction"],
            "timeframe": signal_data.get("timeframe", "M15"),
            "price": price,
            "trigger_cause": trigger_cause,
            "reason_en": reason_en,
            "reason_kh": reason_kh,
            "entry_price": signal_data["entry_price"],
            "stop_loss": signal_data["stop_loss"],
            "take_profit_1": signal_data["take_profit_1"],
            "take_profit_2": signal_data.get("take_profit_2"),
            "take_profit_3": signal_data.get("take_profit_3"),
            "original_telegram_message_id": signal_data.get("telegram_message_id")
        }

        # 1. Telegram Alert with atomic idempotency (policy-controlled)
        from taikry.config import TELEGRAM_SEND_LIFECYCLE_EVENTS
        if TELEGRAM_SEND_LIFECYCLE_EVENTS:
            try:
                from taikry.notifications.telegram_service import telegram_service
                telegram_service.send_lifecycle_event_notification(event_dict, allow_edit=True)
            except Exception as e:
                logger.warning(
                    "Failed to dispatch Telegram lifecycle notification: %s",
                    telegram_service._redact_secret(str(e)),
                )
        else:
            logger.info(
                f"Telegram lifecycle dispatch suppressed by policy (TELEGRAM_SEND_LIFECYCLE_EVENTS=False). "
                f"Event {event_type.value} recorded for signal {signal_data['signal_id']} in internal state engine."
            )

        # 2. Make.com Webhook Dispatch
        payload = {
            "event": f"SIGNAL_TRANSITION_{to_state.value}",
            "event_type": event_type.value,
            "idempotency_key": idempotency_key,
            "signal_id": signal_data["signal_id"],
            "symbol": signal_data["symbol"],
            "direction": signal_data["direction"],
            "state": to_state.value,
            "price": price,
            "trigger_cause": trigger_cause,
            "reason_en": reason_en,
            "reason_kh": reason_kh,
            **({"chat_id": TELEGRAM_CHAT_ID} if TELEGRAM_CHAT_ID else {}),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        try:
            dispatch_to_make(payload, event_type="signal_lifecycle_transition")
        except Exception:
            pass

    def _model_to_dict(self, m: SignalLifecycleModel) -> Dict[str, Any]:
        return {
            "id": m.id,
            "signal_id": m.signal_id,
            "symbol": m.symbol,
            "timeframe": m.timeframe,
            "direction": m.direction,
            "current_state": m.current_state,
            "entry_price": m.entry_price,
            "stop_loss": m.stop_loss,
            "take_profit_1": m.take_profit_1,
            "take_profit_2": m.take_profit_2,
            "take_profit_3": m.take_profit_3,
            "risk_reward": m.risk_reward,
            "ai_score": m.ai_score,
            "invalidation_reason_en": m.invalidation_reason_en,
            "invalidation_reason_kh": m.invalidation_reason_kh,
            "state_history": m.state_history or [],
            "telegram_message_id": m.telegram_message_id,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "updated_at": m.updated_at.isoformat() if m.updated_at else None,
            "expires_at": m.expires_at.isoformat() if m.expires_at else None
        }


signal_lifecycle_manager = SignalLifecycleManager()
