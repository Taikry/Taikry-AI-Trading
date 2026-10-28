"""
Integration tests for Milestone 5: FastAPI Production Endpoints
"""
import pytest
from fastapi.testclient import TestClient
from taikry.api.app import app
from taikry.database.session import init_db

@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c

def test_get_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "HEALTHY"
    assert "market_status" in data
    assert data["live_trading_status"] == "STRICTLY_DISABLED"

def test_post_analyze_endpoint(client):
    r = client.post("/api/v1/analyze", json={"symbol": "XAUUSD", "timeframe": "M15"})
    assert r.status_code == 200
    data = r.json()
    assert data["symbol"] == "XAUUSD"
    assert "market_bias" in data
    assert "agents" in data
    assert "report_english" in data
    assert "report_khmer" in data

def test_post_events_assess(client):
    r = client.post("/api/v1/events/assess", json={
        "event_title": "US Non-Farm Payrolls (NFP)",
        "country": "USD",
        "impact": "HIGH",
        "affected_symbol": "XAUUSD"
    })
    assert r.status_code == 200
    data = r.json()
    assert data["recommended_action"] in ["TIGHTEN_STOPS_OR_WAIT", "MONITOR"]
    assert "assessment" in data

def test_paper_trade_lifecycle(client):
    from taikry.database.session import SessionLocal
    from taikry.database.models import PaperTrade
    with SessionLocal() as db:
        for t in db.query(PaperTrade).filter(PaperTrade.status == "OPEN").all():
            t.status = "CLOSED"
        for t in db.query(PaperTrade).all():
            if t.pnl and t.pnl < 0:
                t.pnl = 0.0
        db.commit()

    # 1. Open trade
    r1 = client.post("/api/v1/paper-trades/evaluate", json={
        "symbol": "BTCUSDT",
        "direction": "BUY",
        "entry_price": 60000.0,
        "stop_loss": 59000.0,
        "take_profit_1": 62000.0
    })
    assert r1.status_code == 200
    trade = r1.json()
    assert trade["success"] is True

    # 2. Get ledger
    r2 = client.get("/api/v1/paper-trades")
    assert r2.status_code == 200
    data = r2.json()
    assert "account_summary" in data
    assert len(data["trades"]) > 0

def test_backtest_run_and_query(client):
    # 1. Run backtest
    r1 = client.post("/api/v1/backtests/run", json={
        "symbol": "XAUUSD",
        "timeframe": "M15",
        "candle_limit": 80
    })
    assert r1.status_code == 200
    data1 = r1.json()
    job_id = data1["job_id"]
    assert data1["status"] == "COMPLETED"

    # 2. Query backtest results
    r2 = client.get(f"/api/v1/backtests/{job_id}")
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["job_id"] == job_id
    assert "win_rate_percent" in data2

def test_daily_report_endpoint(client):
    r = client.get("/api/v1/reports/daily")
    assert r.status_code == 200
    data = r.json()
    assert "daily_briefing_english" in data
    assert "gold_summary" in data

def test_notification_ack_endpoint(client):
    r = client.post("/api/v1/notifications/ack", json={
        "event_id": "evt_test_123",
        "channel": "telegram",
        "status": "DELIVERED"
    })
    assert r.status_code == 200
    assert r.json()["acknowledged"] is True

def test_ai_chat_endpoint(client):
    r = client.post("/api/v1/ai/chat", json={
        "query": "Analyze XAUUSD current setup",
        "symbol": "XAUUSD",
        "timeframe": "15m",
        "provider": "auto"
    })
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "SUCCESS"
    assert "trade_execution" in data
    assert "smart_analysis" in data
    assert "action" in data["trade_execution"]
    assert "synthesis_summary_kh" in data["smart_analysis"]

def test_ai_chat_photo_endpoint(client):
    tiny_png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    r = client.post("/api/v1/ai/chat", json={
        "query": "Analyze chart screenshot",
        "symbol": "XAUUSD",
        "timeframe": "15m",
        "image_base64": tiny_png
    })
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "SUCCESS"
    assert data["has_photo"] is True
    assert "trade_execution" in data

