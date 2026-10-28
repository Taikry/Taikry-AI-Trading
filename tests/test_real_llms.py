"""
Unit and Integration Tests for Real AI LLMs:
Claude, OpenAI, Gemini, and Manus AI.
"""
import pytest
from unittest.mock import patch, MagicMock
from taikry.ai.llm_client import (
    get_llm_status,
    call_claude,
    call_openai,
    call_gemini,
    call_manus,
    llm_orchestrator,
    _extract_json_from_response
)
from ai_agent import generate_signal


def test_llm_status_structure():
    """Verify LLM status reports all 4 required models."""
    status = get_llm_status()
    assert "claude" in status
    assert "openai" in status
    assert "gemini" in status
    assert "manus" in status
    assert "active_mode" in status
    assert "Anthropic Claude" in status["claude"]["name"]
    assert "OpenAI GPT-4o" in status["openai"]["name"]
    assert "Google Gemini" in status["gemini"]["name"]
    assert "Manus AI" in status["manus"]["name"]


def test_json_extractor_handles_markdown_fences():
    """Ensure JSON extractor parses markdown blocks from LLMs."""
    raw_markdown = """Here is the institutional trading analysis:
```json
{
  "smart_analysis": {
    "synthesis_summary_en": "Bullish breakout on Gold",
    "synthesis_summary_kh": "ការទម្លុះឡើងលើមាស",
    "technical_causes": ["EMA 21 above EMA 50"],
    "smc_causes": ["OTE discount zone reached"],
    "macro_causes": ["DXY falling"],
    "risk_causes": ["R:R is 1:2.4"],
    "checklist": {
      "multi_agent_consensus": true,
      "institutional_liquidity_clear": true,
      "macro_dxy_aligned": true,
      "risk_reward_viable": true
    }
  },
  "trade_execution": {
    "action": "BUY",
    "status": "APPROVED",
    "confidence": 92,
    "entry_price": 2720.0,
    "stop_loss": 2710.0,
    "take_profit_1": 2740.0,
    "take_profit_2": 2755.0,
    "risk_reward_ratio": "1:2.0",
    "invalidation_level": 2710.0
  }
}
```
Thank you.
"""
    res = _extract_json_from_response(raw_markdown)
    assert res is not None
    assert res["trade_execution"]["action"] == "BUY"
    assert res["trade_execution"]["entry_price"] == 2720.0
    assert "smart_analysis" in res


@patch("taikry.ai.llm_client.requests.post")
def test_claude_client_mock_success(mock_post):
    """Test Claude API message handling."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "content": [
            {
                "type": "text",
                "text": '{"smart_analysis": {"synthesis_summary_en": "Claude Gold Analysis"}, "trade_execution": {"action": "BUY", "confidence": 91}}'
            }
        ]
    }
    mock_post.return_value = mock_resp

    with patch("taikry.ai.llm_client.CLAUDE_API_KEY", "mock_claude_key"):
        res = call_claude({"symbol": "XAUUSD", "name": "Gold"}, "M15", {"rsi": 50})
        assert res is not None
        assert res["trade_execution"]["action"] == "BUY"
        assert res["_llm_meta"]["provider"] == "claude"


@patch("taikry.ai.llm_client.requests.post")
def test_openai_client_mock_success(mock_post):
    """Test OpenAI GPT-4o API chat completions."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"smart_analysis": {"synthesis_summary_en": "GPT-4o Analysis"}, "trade_execution": {"action": "SELL", "confidence": 88}}'
                }
            }
        ]
    }
    mock_post.return_value = mock_resp

    with patch("taikry.ai.llm_client.OPENAI_API_KEY", "mock_openai_key"):
        res = call_openai({"symbol": "BTCUSD", "name": "Bitcoin"}, "M15", {"rsi": 65})
        assert res is not None
        assert res["trade_execution"]["action"] == "SELL"
        assert res["_llm_meta"]["provider"] == "openai"


@patch("taikry.ai.llm_client.requests.post")
def test_gemini_client_mock_success(mock_post):
    """Test Google Gemini API content generation."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": '{"smart_analysis": {"synthesis_summary_en": "Gemini Analysis"}, "trade_execution": {"action": "BUY", "confidence": 95}}'}
                    ]
                }
            }
        ]
    }
    mock_post.return_value = mock_resp

    with patch("taikry.ai.llm_client.GEMINI_API_KEY", "mock_gemini_key"):
        res = call_gemini({"symbol": "ETHUSD", "name": "Ethereum"}, "M15", {"rsi": 45})
        assert res is not None
        assert res["trade_execution"]["action"] == "BUY"
        assert res["_llm_meta"]["provider"] == "gemini"


@patch("taikry.ai.llm_client.requests.post")
def test_manus_client_mock_success(mock_post):
    """Test Manus AI Agent API reasoning."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"smart_analysis": {"synthesis_summary_en": "Manus AI Agent Causal Analysis"}, "trade_execution": {"action": "HOLD", "status": "REJECTED_LOCKED"}}'
                }
            }
        ]
    }
    mock_post.return_value = mock_resp

    with patch("taikry.ai.llm_client.MANUS_API_KEY", "mock_manus_key"):
        res = call_manus({"symbol": "SOLUSD", "name": "Solana"}, "M15", {"rsi": 50})
        assert res is not None
        assert res["trade_execution"]["action"] == "HOLD"
        assert res["_llm_meta"]["provider"] == "manus"


def test_ai_agent_fallback_when_keys_missing():
    """Verify that ai_agent.generate_signal executes cleanly even if no LLM keys are supplied."""
    metrics = {
        "current_price": 2715.0,
        "rsi": 52.0,
        "atr": 7.5,
        "trend": "BULLISH",
        "macd_hist": 0.35,
        "ema_9": 2718.0,
        "ema_21": 2710.0,
        "ema_50": 2700.0,
        "swing_high": 2740.0,
        "swing_low": 2705.0
    }
    sig = generate_signal({"symbol": "XAUUSD", "name": "Gold", "category": "Commodities"}, "M15", metrics)
    assert "action" in sig
    assert "smart_analysis" in sig
    assert "trade_execution" in sig
    assert "_llm_meta" in sig
    assert "synthesis_summary_kh" in sig["smart_analysis"]
