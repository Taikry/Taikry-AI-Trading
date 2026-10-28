"""
Unit & Integration Tests for Telegram Interactive Buttons,
Callback Query Handling, Webhook Endpoint, and Telegram Mini App (WebApp) Integration.
"""
import pytest
from fastapi.testclient import TestClient

from taikry.api.app import app
from taikry.notifications.telegram_service import telegram_service

@pytest.fixture
def client():
    return TestClient(app)

def test_telegram_service_keyboards():
    """Verifies that main menu and signal keyboards build valid inline_keyboard schemas."""
    main_kb = telegram_service.build_main_menu_keyboard()
    assert "inline_keyboard" in main_kb
    assert len(main_kb["inline_keyboard"]) >= 3

    # Check button texts and callback data
    callbacks = [btn.get("callback_data") for row in main_kb["inline_keyboard"] for btn in row if "callback_data" in btn]
    assert "scan:XAUUSD" in callbacks
    assert "debate:XAUUSD" in callbacks
    assert "calendar:news" in callbacks
    assert "risk:audit" in callbacks

    sig_kb = telegram_service.build_signal_keyboard("XAUUSD")
    assert "inline_keyboard" in sig_kb
    sig_callbacks = [btn.get("callback_data") for row in sig_kb["inline_keyboard"] for btn in row if "callback_data" in btn]
    assert "debate:XAUUSD" in sig_callbacks
    assert "calendar:news" in sig_callbacks

from unittest.mock import patch, MagicMock

@pytest.fixture(autouse=True)
def mock_external_services():
    """Mocks external services (Telegram API, Consensus, Debate) for fast unit testing."""
    mock_consensus = {
        "symbol": "XAUUSD",
        "market_bias": "BULLISH",
        "setup_status": "APPROVE",
        "verified_price": 4065.50,
        "risk_reward_ratio": "1:2.4",
        "proposed_direction": "BUY",
        "report_english": "Bullish institutional order flow detected.",
        "report_khmer": "រចនាសម្ព័ន្ធទីផ្សារកើនឡើងខ្លាំង និងមានតំបន់ OTE ច្បាស់លាស់។"
    }
    mock_debate = {
        "status": "APPROVED",
        "verdict": {"decision": "APPROVE"},
        "debate_summary_en": "Consensus approved with 1:2.4 RR.",
        "debate_summary_kh": "ក្រុម AI Agents ទាំងអស់បានឯកភាពអនុម័តសញ្ញាជួញដូរ។"
    }
    with patch("taikry.agents.consensus_engine.ai_consensus_engine.analyze_symbol", return_value=mock_consensus), \
         patch("taikry.agents.debate_engine.agent_debate_engine.conduct_debate", return_value=mock_debate), \
         patch.object(telegram_service, "send_message", return_value=True), \
         patch.object(telegram_service, "edit_message_text", return_value=True), \
         patch.object(telegram_service, "answer_callback_query", return_value=True):
        yield

def test_telegram_handle_command_with_keyboards():
    """Verifies that /start and /gold commands return rich text with interactive keyboards."""
    # /start
    res_start = telegram_service.handle_command("/start", user_id=1001, chat_id="-1004341134868")
    assert "text" in res_start
    assert "TAIKRY AI" in res_start["text"]
    assert "reply_markup" in res_start
    assert "inline_keyboard" in res_start["reply_markup"]

    # /gold
    res_gold = telegram_service.handle_command("/gold", user_id=1001, chat_id="-1004341134868")
    assert "text" in res_gold
    assert "XAUUSD" in res_gold["text"]
    assert "reply_markup" in res_gold

    # /risk
    res_risk = telegram_service.handle_command("/risk", user_id=1001, chat_id="-1004341134868")
    assert "text" in res_risk
    assert "0.5%" in res_risk["text"]

def test_telegram_handle_callback_query_actions():
    """Tests execution of inline button clicks for scan, debate, news, risk, train, and autofix."""
    # 1. Scan callback
    cb_scan = telegram_service.handle_callback_query("scan:XAUUSD", user_id=1001, chat_id="-1004341134868")
    assert cb_scan["status"] == "SUCCESS"
    assert cb_scan["action"] == "scan"

    # 2. Debate callback
    cb_debate = telegram_service.handle_callback_query("debate:XAUUSD", user_id=1001, chat_id="-1004341134868")
    assert cb_debate["status"] == "SUCCESS"
    assert cb_debate["action"] == "debate"

    # 3. Calendar callback
    cb_cal = telegram_service.handle_callback_query("calendar:news", user_id=1001, chat_id="-1004341134868")
    assert cb_cal["status"] == "SUCCESS"
    assert cb_cal["action"] == "calendar"

    # 4. Risk callback
    cb_risk = telegram_service.handle_callback_query("risk:audit", user_id=1001, chat_id="-1004341134868")
    assert cb_risk["status"] == "SUCCESS"
    assert cb_risk["action"] == "risk"

    # 5. Train callback
    cb_train = telegram_service.handle_callback_query("train:epoch", user_id=1001, chat_id="-1004341134868")
    assert cb_train["status"] == "SUCCESS"
    assert cb_train["action"] == "train"

    # 6. Auto-fix callback
    cb_fix = telegram_service.handle_callback_query("system:autofix", user_id=1001, chat_id="-1004341134868")
    assert cb_fix["status"] == "SUCCESS"
    assert cb_fix["action"] == "autofix"

def test_telegram_master_update_dispatcher():
    """Verifies that handle_update dispatches messages and callback queries."""
    # Message update
    msg_update = {
        "update_id": 99991,
        "message": {
            "message_id": 501,
            "from": {"id": 1001, "first_name": "Trader"},
            "chat": {"id": -1004341134868},
            "text": "/gold"
        }
    }
    r_msg = telegram_service.handle_update(msg_update)
    assert r_msg["status"] == "COMMAND_PROCESSED"

    # Callback Query update
    cb_update = {
        "update_id": 99992,
        "callback_query": {
            "id": "cb_query_12345",
            "from": {"id": 1001, "first_name": "Trader"},
            "message": {
                "message_id": 502,
                "chat": {"id": -1004341134868}
            },
            "data": "calendar:news"
        }
    }
    r_cb = telegram_service.handle_update(cb_update)
    assert r_cb["status"] == "SUCCESS"

def test_api_telegram_endpoints(client):
    """Verifies FastAPI endpoints for Telegram webhook and status."""
    # Status endpoint
    r_stat = client.get("/api/v1/telegram/status")
    assert r_stat.status_code == 200
    st_data = r_stat.json()
    assert "default_chat_id" in st_data
    assert st_data["default_chat_id"] == "-1004341134868"
    assert st_data["interactive_buttons_enabled"] is True

    # Webhook endpoint with command
    update_payload = {
        "update_id": 10001,
        "message": {
            "message_id": 700,
            "from": {"id": 1001},
            "chat": {"id": -1004341134868},
            "text": "/risk"
        }
    }
    r_wh = client.post("/api/v1/telegram/webhook", json=update_payload)
    assert r_wh.status_code == 200
    assert r_wh.json()["ok"] is True

def test_telegram_webapp_sdk_in_frontend():
    """Verifies that index.html embeds Telegram WebApp SDK and app.js initializes it."""
    with open("taikry/web/index.html", "r", encoding="utf-8") as f:
        html = f.read()
    assert "telegram-web-app.js" in html

    with open("taikry/web/app.js", "r", encoding="utf-8") as f:
        js = f.read()
    assert "initTelegramWebApp" in js
    assert "Telegram.WebApp" in js
