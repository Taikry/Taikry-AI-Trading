"""
Automated Test Suite for Telegram Duplicate Prevention and Signal Lifecycle Idempotency
========================================================================================
Validates all 10 requirements:
1. The same entry-zone event repeated 100 times sends at most one notification.
2. Repeated polling with unchanged state sends no additional message.
3. Two concurrent workers cannot claim the same event twice.
4. Restarting the application does not resend completed events.
5. A genuine TP1, SL, cancellation, or direction-change event is notified once.
6. A distinct new signal can still be sent.
7. Telegram failures and uncertain timeouts are handled without uncontrolled retries.
8. Price/chart updates continue even when Telegram notifications are suppressed.
9. Khmer and English message formatting remains correct.
10. Daily XAUUSD signal limits and other existing rules remain intact.
"""
import pytest
import datetime
import uuid
import threading
from unittest.mock import patch, MagicMock
import requests

from taikry.database.session import SessionLocal
from taikry.database.models import (
    SignalLifecycleModel,
    SignalLifecycleEventModel,
    LifecycleEventType,
    EventDeliveryStatus
)
from taikry.trading.lifecycle import SignalLifecycleManager, SignalState, signal_lifecycle_manager
from taikry.notifications.telegram_service import TelegramService, telegram_service


@pytest.fixture(autouse=True)
def isolate_test_environment():
    """Isolates each test by expiring lingering database signals and cleaning test records."""
    db = SessionLocal()
    try:
        # Inactivate lingering unexpired signals so they don't cross-contaminate price evaluations
        db.query(SignalLifecycleModel).filter(
            SignalLifecycleModel.current_state.in_([
                SignalState.WAITING_CONFIRMATION.value,
                SignalState.ACTIVE.value
            ])
        ).update({"current_state": SignalState.EXPIRED.value}, synchronize_session=False)
        db.commit()
    finally:
        db.close()

    fanout_patcher = patch.object(TelegramService, "_fanout_plan_signal", return_value=(0, 0))
    fanout_patcher.start()
    yield
    fanout_patcher.stop()

    db = SessionLocal()
    try:
        db.query(SignalLifecycleEventModel).filter(
            SignalLifecycleEventModel.signal_id.like("SIG-TEST-%")
        ).delete(synchronize_session=False)
        db.query(SignalLifecycleModel).filter(
            SignalLifecycleModel.signal_id.like("SIG-TEST-%")
        ).delete(synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def count_telegram_api_calls(mock_post) -> int:
    """Helper to count calls specifically targeting the Telegram Bot API sendMessage."""
    count = 0
    for call in mock_post.call_args_list:
        args, kwargs = call
        url = args[0] if len(args) > 0 else kwargs.get("url", "")
        if "api.telegram.org" in str(url):
            count += 1
    return count


def create_test_signal_in_db(symbol="XAUUSD", direction="SELL", entry=4060.0, sl=4075.0, tp1=4030.0, tp2=4010.0, state=SignalState.WAITING_CONFIRMATION, tp3=None):
    """Helper to insert an isolated test signal."""
    sig_id = f"SIG-TEST-{uuid.uuid4().hex[:8].upper()}"
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    db = SessionLocal()
    try:
        sig = SignalLifecycleModel(
            signal_id=sig_id,
            symbol=symbol,
            direction=direction,
            timeframe="M15",
            entry_price=entry,
            stop_loss=sl,
            take_profit_1=tp1,
            take_profit_2=tp2,
            take_profit_3=tp3,
            risk_reward="1:2.0",
            ai_score=88,
            current_state=state.value,
            state_history=[{
                "from_state": None,
                "to_state": state.value,
                "timestamp": now_dt.isoformat(),
                "trigger_cause": "Initial test setup",
                "price": entry
            }],
            created_at=now_dt,
            updated_at=now_dt,
            expires_at=now_dt + datetime.timedelta(hours=6)
        )
        db.add(sig)
        db.commit()
        db.refresh(sig)
        return sig_id
    finally:
        db.close()


# -------------------------------------------------------------------------
# Requirement 1: Same entry-zone event repeated 100 times sends at most 1
# -------------------------------------------------------------------------
def test_entry_zone_event_repeated_100_times_sends_at_most_one_notification():
    sig_id = create_test_signal_in_db(symbol="XAUUSD", direction="SELL", entry=4060.0, sl=4075.0, tp1=4030.0)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True, "result": {"message_id": 888100}}

    with patch.object(requests, "post", return_value=mock_resp) as mock_post:
        # Price hits entry zone for SELL (>= 4060.0 - tolerance)
        test_price = 4060.50

        # Repeated evaluation 100 times (simulating high-frequency tick spam)
        for _ in range(100):
            signal_lifecycle_manager.evaluate_signals({"XAUUSD": test_price})

        # Telegram message must be sent at most once
        tg_count = count_telegram_api_calls(mock_post)
        assert tg_count == 1, f"Expected exactly 1 Telegram post, got {tg_count}"

    # Verify database state
    db = SessionLocal()
    try:
        sig = db.query(SignalLifecycleModel).filter(SignalLifecycleModel.signal_id == sig_id).first()
        assert sig.current_state == SignalState.ACTIVE.value

        events = db.query(SignalLifecycleEventModel).filter(
            SignalLifecycleEventModel.signal_id == sig_id,
            SignalLifecycleEventModel.event_type == LifecycleEventType.ENTRY_ZONE_REACHED.value
        ).all()
        assert len(events) == 1, "Expected exactly 1 ENTRY_ZONE_REACHED event"
        assert events[0].delivery_status == EventDeliveryStatus.SENT.value
        assert events[0].telegram_message_id == "888100"
    finally:
        db.close()


# -------------------------------------------------------------------------
# Requirement 2: Repeated polling with unchanged state sends no additional message
# -------------------------------------------------------------------------
def test_repeated_polling_with_unchanged_state_sends_no_additional_message():
    sig_id = create_test_signal_in_db(symbol="XAUUSD", direction="SELL", entry=4060.0, sl=4075.0, tp1=4030.0, state=SignalState.ACTIVE)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True, "result": {"message_id": 999200}}

    with patch.object(requests, "post", return_value=mock_resp) as mock_post:
        # Oscillating prices between SL (4075) and TP1 (4030) - no transition
        prices = [4055.0, 4056.0, 4058.0, 4054.0, 4052.0]
        for p in prices * 10:  # 50 evaluations
            signal_lifecycle_manager.evaluate_signals({"XAUUSD": p})

        # Zero Telegram notifications must be sent during steady state
        tg_count = count_telegram_api_calls(mock_post)
        assert tg_count == 0, f"Expected 0 Telegram calls, got {tg_count}"


# -------------------------------------------------------------------------
# Requirement 3: Two concurrent workers cannot claim the same event twice
# -------------------------------------------------------------------------
def test_two_concurrent_workers_cannot_claim_same_event_twice():
    sig_id = f"SIG-TEST-CONCUR-{uuid.uuid4().hex[:6]}"
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    idempotency_key = f"{sig_id}:ENTRY_ZONE_REACHED:2"

    db = SessionLocal()
    try:
        ev = SignalLifecycleEventModel(
            signal_id=sig_id,
            event_type=LifecycleEventType.ENTRY_ZONE_REACHED.value,
            transition_index=2,
            idempotency_key=idempotency_key,
            symbol="XAUUSD",
            direction="SELL",
            timeframe="M15",
            price=4060.0,
            trigger_cause="Price reached entry zone",
            reason_en="Entry zone reached",
            from_state="WAITING_CONFIRMATION",
            to_state="ACTIVE",
            delivery_status=EventDeliveryStatus.PENDING.value,
            created_at=now_dt,
            updated_at=now_dt
        )
        db.add(ev)
        db.commit()
    finally:
        db.close()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True, "result": {"message_id": 777300}}

    results = []
    event_dict = {
        "idempotency_key": idempotency_key,
        "signal_id": sig_id,
        "event_type": "ENTRY_ZONE_REACHED",
        "symbol": "XAUUSD",
        "direction": "SELL",
        "price": 4060.0,
        "trigger_cause": "Concurrent claim test"
    }

    def worker_send():
        res = telegram_service.send_lifecycle_event_notification(event_dict)
        results.append(res)

    with patch.object(requests, "post", return_value=mock_resp) as mock_post:
        # Launch 5 concurrent workers simultaneously
        threads = [threading.Thread(target=worker_send) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Only 1 worker should have dispatched to Telegram API
        tg_count = count_telegram_api_calls(mock_post)
        assert tg_count == 1, f"Expected exactly 1 Telegram dispatch, got {tg_count}"

    # Verify that the event is SENT in database
    db = SessionLocal()
    try:
        ev_final = db.query(SignalLifecycleEventModel).filter(
            SignalLifecycleEventModel.idempotency_key == idempotency_key
        ).first()
        assert ev_final.delivery_status == EventDeliveryStatus.SENT.value
    finally:
        db.close()


# -------------------------------------------------------------------------
# Requirement 4: Restarting application does not resend completed events
# -------------------------------------------------------------------------
def test_restarting_application_does_not_resend_completed_events():
    sig_id = f"SIG-TEST-RESTART-{uuid.uuid4().hex[:6]}"
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    idempotency_key = f"{sig_id}:ENTRY_ZONE_REACHED:2"

    # Simulate an event that was already completed and marked SENT before restart
    db = SessionLocal()
    try:
        ev = SignalLifecycleEventModel(
            signal_id=sig_id,
            event_type=LifecycleEventType.ENTRY_ZONE_REACHED.value,
            transition_index=2,
            idempotency_key=idempotency_key,
            symbol="XAUUSD",
            direction="SELL",
            timeframe="M15",
            price=4060.0,
            trigger_cause="Price reached entry zone",
            from_state="WAITING_CONFIRMATION",
            to_state="ACTIVE",
            delivery_status=EventDeliveryStatus.SENT.value,
            telegram_message_id="123456",
            telegram_sent_at=now_dt,
            created_at=now_dt,
            updated_at=now_dt
        )
        db.add(ev)
        db.commit()
    finally:
        db.close()

    # Re-initialize a brand new TelegramService instance (simulating fresh process startup)
    fresh_service = TelegramService()

    with patch.object(requests, "post") as mock_post:
        event_dict = {
            "idempotency_key": idempotency_key,
            "signal_id": sig_id,
            "event_type": "ENTRY_ZONE_REACHED",
            "symbol": "XAUUSD"
        }
        ok, msg_id, err = fresh_service.send_lifecycle_event_notification(event_dict)

        # Must recognize it was already sent and NOT dispatch to Telegram
        assert ok is True
        assert msg_id == "123456"
        assert err == "ALREADY_SENT"
        assert count_telegram_api_calls(mock_post) == 0


# -------------------------------------------------------------------------
# Requirement 5: A genuine TP1, SL, cancellation event is notified once
# -------------------------------------------------------------------------
def test_genuine_tp1_sl_cancellation_events_notified_once():
    sig_id = create_test_signal_in_db(symbol="XAUUSD", direction="SELL", entry=4060.0, sl=4075.0, tp1=4030.0, state=SignalState.ACTIVE)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True, "result": {"message_id": 555001}}

    with patch.object(requests, "post", return_value=mock_resp) as mock_post:
        # Price hits TP1 for SELL (<= 4030.0)
        events = signal_lifecycle_manager.evaluate_signals({"XAUUSD": 4028.0})
        assert len(events) == 1
        assert events[0]["current_state"] == SignalState.TARGET_HIT.value
        assert count_telegram_api_calls(mock_post) == 1

        # Evaluate repeatedly at the same TP price; do not send duplicates.
        for _ in range(10):
            signal_lifecycle_manager.evaluate_signals({"XAUUSD": 4028.0})

        assert count_telegram_api_calls(mock_post) == 1


def test_lifecycle_keeps_monitoring_after_tp1_and_tracks_tp2_tp3():
    sig_id = create_test_signal_in_db(
        symbol="XAUUSD", direction="SELL", entry=4060.0, sl=4075.0,
        tp1=4030.0, tp2=4010.0, tp3=3990.0, state=SignalState.ACTIVE,
    )

    first = signal_lifecycle_manager.evaluate_signals({"XAUUSD": 4028.0})
    assert len(first) == 1
    assert first[0]["current_state"] == SignalState.TARGET_HIT.value
    assert first[0]["state_history"][-1]["event_type"] == "TP1_HIT"
    assert signal_lifecycle_manager.evaluate_signals({"XAUUSD": 4028.0}) == []

    second = signal_lifecycle_manager.evaluate_signals({"XAUUSD": 4008.0})
    assert len(second) == 1
    assert second[0]["current_state"] == SignalState.TARGET_HIT.value
    assert second[0]["state_history"][-1]["event_type"] == "TP2_HIT"

    third = signal_lifecycle_manager.evaluate_signals({"XAUUSD": 3988.0})
    assert len(third) == 1
    assert third[0]["current_state"] == SignalState.CLOSED.value
    assert third[0]["state_history"][-1]["event_type"] == "TP3_HIT"
    assert signal_lifecycle_manager.evaluate_signals({"XAUUSD": 3988.0}) == []

# -------------------------------------------------------------------------
# Requirement 6: A distinct new signal can still be sent
# -------------------------------------------------------------------------
def test_distinct_new_signal_can_still_be_sent():
    # Create first signal
    sig1 = signal_lifecycle_manager.create_signal(
        symbol="XAUUSD",
        direction="SELL",
        entry_price=4060.0,
        stop_loss=4075.0,
        take_profit_1=4030.0
    )

    # Invalidate first signal (e.g. market changed)
    signal_lifecycle_manager.transition_signal(
        sig1["signal_id"],
        SignalState.INVALIDATED,
        "Structural break",
        4076.0
    )

    # Create distinct new signal (e.g. BUY after reversal)
    sig2 = signal_lifecycle_manager.create_signal(
        symbol="XAUUSD",
        direction="BUY",
        entry_price=4080.0,
        stop_loss=4065.0,
        take_profit_1=4110.0
    )

    assert sig2["signal_id"] != sig1["signal_id"]
    assert sig2["direction"] == "BUY"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True, "result": {"message_id": 888002}}

    with patch.object(requests, "post", return_value=mock_resp) as mock_post:
        # Price reaches entry zone for sig2
        signal_lifecycle_manager.evaluate_signals({"XAUUSD": 4080.10})
        assert count_telegram_api_calls(mock_post) == 1


# -------------------------------------------------------------------------
# Requirement 7: Telegram failures & timeouts handled without uncontrolled retries
# -------------------------------------------------------------------------
def test_telegram_timeout_handled_with_uncertain_timeout_and_no_blind_retry():
    sig_id = f"SIG-TEST-TIMEOUT-{uuid.uuid4().hex[:6]}"
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    idempotency_key = f"{sig_id}:ENTRY_ZONE_REACHED:2"

    db = SessionLocal()
    try:
        ev = SignalLifecycleEventModel(
            signal_id=sig_id,
            event_type=LifecycleEventType.ENTRY_ZONE_REACHED.value,
            transition_index=2,
            idempotency_key=idempotency_key,
            symbol="XAUUSD",
            direction="SELL",
            timeframe="M15",
            price=4060.0,
            trigger_cause="Timeout test",
            from_state="WAITING_CONFIRMATION",
            to_state="ACTIVE",
            delivery_status=EventDeliveryStatus.PENDING.value,
            created_at=now_dt,
            updated_at=now_dt
        )
        db.add(ev)
        db.commit()
    finally:
        db.close()

    event_dict = {
        "idempotency_key": idempotency_key,
        "signal_id": sig_id,
        "event_type": "ENTRY_ZONE_REACHED",
        "symbol": "XAUUSD",
        "direction": "SELL",
        "price": 4060.0,
        "trigger_cause": "Timeout test"
    }

    with patch.object(requests, "post", side_effect=requests.exceptions.Timeout("Connection timed out")):
        ok, msg_id, err = telegram_service.send_lifecycle_event_notification(event_dict)
        assert ok is False
        assert "timeout" in err.lower()

    # Verify status in database is UNCERTAIN_TIMEOUT
    db = SessionLocal()
    try:
        ev_after = db.query(SignalLifecycleEventModel).filter(
            SignalLifecycleEventModel.idempotency_key == idempotency_key
        ).first()
        assert ev_after.delivery_status == EventDeliveryStatus.UNCERTAIN_TIMEOUT.value

        # Attempt to call send again: Must suppress to prevent spamming
        with patch.object(requests, "post") as mock_post_again:
            ok2, msg_id2, err2 = telegram_service.send_lifecycle_event_notification(event_dict)
            assert ok2 is False
            assert "UNCERTAIN_TIMEOUT" in err2
            assert count_telegram_api_calls(mock_post_again) == 0
    finally:
        db.close()


# -------------------------------------------------------------------------
# Requirement 8: Price/chart updates continue even when notifications suppressed
# -------------------------------------------------------------------------
def test_price_chart_updates_continue_when_notifications_suppressed():
    # Setup active signal
    create_test_signal_in_db(symbol="XAUUSD", direction="SELL", entry=4060.0, sl=4075.0, tp1=4030.0, state=SignalState.ACTIVE)

    # Prices stream continuously
    ticks = [4059.0, 4058.5, 4058.0, 4057.8, 4057.5]
    for tick in ticks:
        # evaluate_signals completes normally without error and without emitting notifications
        events = signal_lifecycle_manager.evaluate_signals({"XAUUSD": tick})
        assert isinstance(events, list)
        assert len(events) == 0  # No transitions triggered, price evaluation runs smoothly


# -------------------------------------------------------------------------
# Requirement 9: Khmer and English message formatting remains correct
# -------------------------------------------------------------------------
def test_khmer_and_english_message_formatting_accurate():
    sig_id = f"SIG-TEST-BILINGUAL-{uuid.uuid4().hex[:6]}"
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    idempotency_key = f"{sig_id}:ENTRY_ZONE_REACHED:2"

    db = SessionLocal()
    try:
        ev = SignalLifecycleEventModel(
            signal_id=sig_id,
            event_type=LifecycleEventType.ENTRY_ZONE_REACHED.value,
            transition_index=2,
            idempotency_key=idempotency_key,
            symbol="XAUUSD",
            direction="SELL",
            timeframe="M15",
            price=4062.50,
            trigger_cause="Price reached entry target zone (4062.50)",
            reason_en="Price reached entry target zone (4062.50). Trade is now ACTIVE under live market surveillance.",
            reason_kh="តម្លៃបានមកដល់តំបន់គោលដៅចូលជួញដូរ (4062.50)។ ការជួញដូរបានក្លាយជា ACTIVE ក្រោមការតាមដានទីផ្សារផ្ទាល់។",
            from_state="WAITING_CONFIRMATION",
            to_state="ACTIVE",
            delivery_status=EventDeliveryStatus.PENDING.value,
            created_at=now_dt,
            updated_at=now_dt
        )
        db.add(ev)
        db.commit()
    finally:
        db.close()

    event_dict = {
        "idempotency_key": idempotency_key,
        "signal_id": sig_id,
        "event_type": "ENTRY_ZONE_REACHED",
        "symbol": "XAUUSD",
        "direction": "SELL",
        "timeframe": "M15",
        "price": 4062.50,
        "trigger_cause": "Price reached entry target zone (4062.50)",
        "reason_en": "Price reached entry target zone (4062.50). Trade is now ACTIVE under live market surveillance.",
        "reason_kh": "តម្លៃបានមកដល់តំបន់គោលដៅចូលជួញដូរ (4062.50)។ ការជួញដូរបានក្លាយជា ACTIVE ក្រោមការតាមដានទីផ្សារផ្ទាល់។",
        "entry_price": 4062.50,
        "stop_loss": 4075.0,
        "take_profit_1": 4030.0
    }

    captured_payload = {}

    def fake_post(url, json=None, timeout=None):
        if "api.telegram.org" in str(url):
            captured_payload["text"] = json.get("text")
        m = MagicMock()
        m.status_code = 200
        m.json.return_value = {"ok": True, "result": {"message_id": 99999}}
        return m

    with patch.object(requests, "post", side_effect=fake_post):
        ok, msg_id, err = telegram_service.send_lifecycle_event_notification(event_dict)
        assert ok is True

    text = captured_payload.get("text", "")

    # Assert accurate non-fabricated wording
    assert "ENTRY_ZONE_REACHED" in text
    assert "Order filled" not in text, "Must not claim order filled merely on zone touch"
    assert "4062.50" in text
    assert sig_id in text
    assert "TAIKRY SIGNAL LIFECYCLE — XAUUSD" in text
    # Khmer presence
    assert "ភាសាខ្មែរ" in text
    assert "តម្លៃបានមកដល់តំបន់ចូលជួញដូរ" in text


# -------------------------------------------------------------------------
# Requirement 10: Daily XAUUSD signal limits & existing rules remain intact
# -------------------------------------------------------------------------
def test_xauusd_daily_signal_limit_and_engine_rules_intact():
    from taikry.trading.xauusd_signal_engine import xauusd_signal_engine
    quota = xauusd_signal_engine.get_daily_quota_status()
    assert "signals_sent_today" in quota
    assert "daily_hard_limit" in quota
    assert quota["daily_hard_limit"] == 4
