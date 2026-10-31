"""Persistent signal notification and Telegram analysis progress coverage."""
import datetime
import uuid
from unittest.mock import MagicMock, patch

import requests

from taikry.database.models import TelegramAnalysisRun, TelegramNotification
from taikry.database.session import SessionLocal
from taikry.notifications.telegram_service import TelegramService


def _valid_consensus(symbol="EURUSD"):
    entry = 1.12345 + (uuid.uuid4().int % 1000) / 1_000_000
    return {
        "symbol": symbol,
        "setup_status": "APPROVE",
        "proposed_direction": "BUY",
        "ai_score": 88,
        "entry_price": entry,
        "stop_loss": entry - 0.01,
        "take_profit_1": entry + 0.02,
        "take_profit_2": entry + 0.03,
        "price_source": "OANDA_V20",
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "timeframe": "M15",
        "agents": {"technical_analyst": {"status": "COMPLETED"}},
    }


def _delete_notification(key):
    db = SessionLocal()
    try:
        db.query(TelegramNotification).filter(TelegramNotification.idempotency_key == key).delete()
        db.commit()
    finally:
        db.close()


def test_validated_signal_outbox_sends_once_after_restart_style_reuse():
    service = TelegramService()
    service.token = "unit-test-token"
    service.default_chat_id = "-1001234567890"
    result = _valid_consensus()
    key = service._signal_idempotency_key(result, service.default_chat_id)
    _delete_notification(key)

    response = MagicMock(status_code=200)
    response.json.return_value = {"ok": True, "result": {"message_id": 901}}
    try:
        with patch("requests.post", return_value=response) as post, patch(
            "taikry.data.validator.check_data_freshness", return_value={"fresh": True, "status": "LIVE_FRESH"}
        ), patch("taikry.saas.entitlement_service.get_telegram_signal_recipients", return_value=[]):
            assert service.send_validated_signal_report(result) is True
            assert service.send_validated_signal_report(result) is True
            assert post.call_count == 1

        db = SessionLocal()
        try:
            notification = db.query(TelegramNotification).filter(
                TelegramNotification.idempotency_key == key
            ).one()
            assert notification.delivery_status == "SENT"
            assert notification.telegram_message_id == "901"
            assert notification.attempt_count == 1
        finally:
            db.close()
    finally:
        _delete_notification(key)


def test_uncertain_timeout_is_not_resent():
    service = TelegramService()
    service.token = "unit-test-token"
    service.default_chat_id = "-1001234567890"
    result = _valid_consensus()
    key = service._signal_idempotency_key(result, service.default_chat_id)
    _delete_notification(key)

    try:
        with patch("requests.post", side_effect=requests.Timeout("request timed out")) as post, patch(
            "taikry.data.validator.check_data_freshness", return_value={"fresh": True, "status": "LIVE_FRESH"}
        ), patch("taikry.saas.entitlement_service.get_telegram_signal_recipients", return_value=[]):
            assert service.send_validated_signal_report(result) is False
            assert service.send_validated_signal_report(result) is False
            assert post.call_count == 1

        db = SessionLocal()
        try:
            notification = db.query(TelegramNotification).filter(
                TelegramNotification.idempotency_key == key
            ).one()
            assert notification.delivery_status == "UNCERTAIN"
            assert notification.attempt_count == 1
        finally:
            db.close()
    finally:
        _delete_notification(key)


def test_analysis_progress_run_persists_message_and_actual_agent_status():
    service = TelegramService()
    service.token = "unit-test-token"
    service.default_chat_id = "-1001234567890"
    with patch.object(service, "send_text", return_value=(True, "902", None)), patch.object(
        service, "edit_message_text_detailed", return_value=(True, None, "SUCCESS")
    ):
        run_id = service.begin_analysis_run("EURUSD", timeframe="H1")
        assert run_id
        assert service.finish_analysis_run(
            run_id,
            "APPROVED",
            "✅ <b>Validated setup</b>",
            {"technical_analyst": "COMPLETED", "risk_validator": "COMPLETED"},
            "SIG-TEST-ANALYSIS",
        ) is True

    db = SessionLocal()
    try:
        run = db.query(TelegramAnalysisRun).filter(TelegramAnalysisRun.run_id == run_id).one()
        assert run.status == "APPROVED"
        assert run.telegram_message_id == "902"
        assert run.signal_candidate_id == "SIG-TEST-ANALYSIS"
        assert run.message_type == "text"
        assert run.agent_statuses["technical_analyst"] == "COMPLETED"
        assert run.signal_id == "SIG-TEST-ANALYSIS"
        db.delete(run)
        db.commit()
    finally:
        db.close()


def test_telegram_disabled_blocks_direct_send_edit_and_callback_helpers():
    service = TelegramService()
    service.enabled = False
    service.token = "unit-test-token"
    service.default_chat_id = "-1001234567890"

    with patch("requests.post") as post:
        assert service.send_message("test") is False
        assert service.send_text("test") == (False, None, "Telegram notifications are disabled")
        assert service.answer_callback_query("callback-id") is False
        assert service.edit_message_text_detailed("test", service.default_chat_id, 1) == (
            False, "Telegram notifications are disabled", "REJECTED"
        )
        assert post.call_count == 0
