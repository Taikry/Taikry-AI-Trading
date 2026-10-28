"""
Comprehensive Verification Tests for Real-Time High-Impact News (FOMC, PPI, CPI, NFP),
Frontier AI Models (Claude 3.7/3.5, OpenAI o3/o1/4o, Gemini 2.5, DeepSeek R1/V3, Manus AI),
Multi-Agent News Debate, and Khmer Language Integration.
"""
import pytest
from fastapi.testclient import TestClient
from taikry.api.app import app
from taikry.ai.llm_client import llm_orchestrator, get_llm_status, LLM_SYSTEM_PROMPT
from taikry.data.economic_calendar import economic_calendar_provider
from taikry.agents.debate_engine import agent_debate_engine
from taikry.notifications.telegram_service import telegram_service

@pytest.fixture
def client():
    return TestClient(app)

def test_frontier_llm_models_registration():
    """Verifies that all Frontier AI models are registered in LLM status and prompt contains news & Khmer mandates."""
    status = get_llm_status()
    assert "claude" in status
    assert "openai" in status
    assert "gemini" in status
    assert "deepseek" in status
    assert "manus" in status

    # Check frontier model tags
    assert "claude-3-7-sonnet" in status["claude"]["frontier_models"]
    assert "o3-mini" in status["openai"]["frontier_models"]
    assert "gemini-2.5-pro" in status["gemini"]["frontier_models"]
    assert "deepseek-r1" in status["deepseek"]["frontier_models"]

    # Check that system prompt mandates news catalysts and Khmer analysis
    assert "FOMC" in LLM_SYSTEM_PROMPT
    assert "PPI" in LLM_SYSTEM_PROMPT
    assert "CPI" in LLM_SYSTEM_PROMPT
    assert "synthesis_summary_kh" in LLM_SYSTEM_PROMPT
    assert "វិភាគមូលហេតុ" in LLM_SYSTEM_PROMPT

def test_high_impact_economic_calendar():
    """Verifies high-impact calendar retrieval, countdown calculation, and Khmer translations."""
    events = economic_calendar_provider.get_upcoming_high_impact_events()
    assert len(events) >= 2

    # Check fields in top event
    ev = events[0]
    assert "title" in ev
    assert "title_kh" in ev
    assert "time_until" in ev
    assert "countdown_seconds" in ev
    assert "gold_impact_kh" in ev
    assert "forex_impact_kh" in ev
    assert len(ev["title_kh"]) > 0

    # Ensure key catalysts (FOMC, PPI, CPI, or NFP) are represented in catalog
    all_titles = " ".join([e["title"] for e in events])
    assert any(k in all_titles.upper() for k in ["FOMC", "PPI", "CPI", "NFP", "INFLATION", "POLICY", "RATE"])

def test_live_macro_news_feed():
    """Verifies live breaking financial news retrieval from verified RSS feeds."""
    news = economic_calendar_provider.get_live_macro_news(limit=5)
    assert len(news) > 0
    top_news = news[0]
    assert "title" in top_news
    assert "source" in top_news
    assert "published_at" in top_news
    assert top_news["source"] in ["Investing.com", "MarketWatch", "Institutional Macro Desk"]

def test_news_blackout_audit():
    """Verifies news blackout detection mechanism."""
    blackout = economic_calendar_provider.check_news_blackout("XAUUSD")
    assert "is_blackout" in blackout
    assert "advisory_en" in blackout
    assert "advisory_kh" in blackout
    assert isinstance(blackout["is_blackout"], bool)

def test_multi_agent_debate_with_news_and_khmer():
    """Verifies that multi-agent debate integrates real-time news in Turn 3 and risk audit in Turn 4 with Khmer."""
    res = agent_debate_engine.conduct_debate("XAUUSD", "M15")
    assert res["status"] in ["CONSENSUS_REACHED", "RISK_VETOED", "DISSENT_RESOLVED"]
    assert len(res["turns"]) == 4

    # Turn 3: Macro Analyst
    t3 = res["turns"][2]
    assert t3["agent_id"] == "macro_analyst"
    assert "message_en" in t3
    assert "message_kh" in t3
    assert len(t3["message_kh"]) > 20
    # Must contain DXY or macro catalyst
    assert "DXY" in t3["message_en"] or "Dollar" in t3["message_en"] or "Catalyst" in t3["message_en"]

    # Turn 4: Risk Arbiter
    t4 = res["turns"][3]
    assert t4["agent_id"] == "risk_validator"
    assert "message_en" in t4
    assert "message_kh" in t4
    assert len(t4["message_kh"]) > 20

def test_api_calendar_and_news_endpoints(client):
    """Verifies FastAPI endpoints for calendar and live news."""
    # Calendar endpoint
    r_cal = client.get("/api/v1/calendar/high-impact")
    assert r_cal.status_code == 200
    cal_data = r_cal.json()
    assert cal_data["status"] == "SUCCESS"
    assert len(cal_data["events"]) > 0
    assert "blackout_status" in cal_data

    # Live news endpoint
    r_news = client.get("/api/v1/news/live")
    assert r_news.status_code == 200
    news_data = r_news.json()
    assert news_data["status"] == "SUCCESS"
    assert len(news_data["news"]) > 0

    # LLM status endpoint
    r_llm = client.get("/api/v1/llm/status")
    assert r_llm.status_code == 200
    llm_data = r_llm.json()
    assert "claude" in llm_data
    assert "deepseek" in llm_data

def test_telegram_calendar_command():
    """Verifies Telegram /calendar and /news command formatting with Khmer descriptions."""
    resp = telegram_service.handle_command("/news", user_id=123, chat_id="-1004341134868")
    resp_text = resp["text"] if isinstance(resp, dict) else resp
    assert "REAL-TIME HIGH-IMPACT ECONOMIC CALENDAR" in resp_text
    assert "ភាសាខ្មែរ" in resp_text or "🇰🇭" in resp_text
    if isinstance(resp, dict):
        assert "reply_markup" in resp
