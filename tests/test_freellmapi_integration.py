"""
Comprehensive Test Suite for FreeLLMAPI Unified Gateway Integration
Verifies FreeLLMAPI client, dynamic model discovery, chat completion,
LLM orchestrator integration, circuit breaker management, and REST API endpoints.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from taikry.api.app import app
from taikry.ai.freellmapi_client import FreeLLMAPIClient, freellmapi_client
from taikry.ai.llm_client import llm_orchestrator, call_freellmapi, chat_with_real_ai


@pytest.fixture
def test_client():
    return TestClient(app)


class TestFreeLLMAPIClient:
    """Tests unit behavior of FreeLLMAPIClient."""

    def test_client_init_defaults(self):
        client = FreeLLMAPIClient()
        assert client.base_url.startswith("http")
        assert client.default_model is not None
        assert client.timeout > 0

    def test_client_update_config(self):
        client = FreeLLMAPIClient(base_url="http://test-host:4000/v1")
        assert client.base_url == "http://test-host:4000/v1"
        
        client.update_config(
            base_url="https://cloud-freellmapi.onrender.com/v1/",
            api_key="sk-new-key-123",
            default_model="gemini-2.0-flash"
        )
        assert client.base_url == "https://cloud-freellmapi.onrender.com/v1"
        assert client.api_key == "sk-new-key-123"
        assert client.default_model == "gemini-2.0-flash"

    def test_get_status_standby_on_connection_error(self):
        client = FreeLLMAPIClient(base_url="http://127.0.0.1:40999/v1")
        status = client.get_status()
        assert status["status"] in ["STANDBY", "OFFLINE"]
        assert "github_url" in status
        assert "tashfeenahmed/freellmapi" in status["github_url"]

    @patch("requests.get")
    def test_get_status_connected_when_mocked(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {"id": "deepseek-r1", "owned_by": "groq"},
                {"id": "llama-3.3-70b-versatile", "owned_by": "groq"}
            ]
        }
        mock_get.return_value = mock_resp

        client = FreeLLMAPIClient()
        status = client.get_status()
        assert status["status"] == "CONNECTED"
        assert status["models_count"] == 2
        assert "latency_ms" in status

    @patch("requests.get")
    def test_discover_models_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {"id": "qwen-2.5-72b", "owned_by": "sambanova"},
                {"id": "gemini-2.0-flash", "owned_by": "google"}
            ]
        }
        mock_get.return_value = mock_resp

        client = FreeLLMAPIClient()
        models = client.discover_models(force_refresh=True)
        assert len(models) == 2
        assert models[0]["id"] == "qwen-2.5-72b"
        assert models[0]["free_tier"] is True

    @patch("requests.get")
    def test_discover_models_fallback_when_unreachable(self, mock_get):
        mock_get.side_effect = Exception("Docker proxy not yet started")
        client = FreeLLMAPIClient()
        models = client.discover_models(force_refresh=True)
        assert len(models) >= 3
        # Should contain standard popular free model fallback IDs
        model_ids = [m["id"] for m in models]
        assert "deepseek-r1" in model_ids

    @patch("requests.post")
    def test_chat_completion_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [
                {"message": {"content": "{\"signal\": \"BUY\", \"confidence\": 88}"}}
            ],
            "usage": {"total_tokens": 120}
        }
        mock_post.return_value = mock_resp

        client = FreeLLMAPIClient()
        res = client.chat_completion(
            messages=[{"role": "user", "content": "Analyze market"}]
        )
        assert res["success"] is True
        assert res["provider"] == "freellmapi"
        assert "confidence" in res["content"]

    @patch("requests.post")
    def test_test_connection_smoke(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "PONG"}}]
        }
        mock_post.return_value = mock_resp

        client = FreeLLMAPIClient()
        test_res = client.test_connection()
        assert test_res["success"] is True
        assert test_res["response"] == "PONG"


class TestLLMOrchestratorFreeLLMAPI:
    """Verifies integration into the central LLM Orchestrator."""

    def test_freellmapi_in_orchestrator_status(self):
        status = llm_orchestrator.get_status()
        assert "freellmapi" in status
        f_meta = status["freellmapi"]
        assert f_meta["tier"] == "100% FREE"
        assert "tashfeenahmed/freellmapi" in f_meta.get("github_url", "")
        assert "deepseek-r1" in f_meta.get("frontier_models", [])

    def test_circuit_breaker_registered(self):
        assert "freellmapi" in llm_orchestrator.circuit_breakers
        assert llm_orchestrator.is_provider_available("freellmapi") is True

    @patch("taikry.ai.freellmapi_client.freellmapi_client.chat_completion")
    def test_call_freellmapi_structured(self, mock_chat):
        mock_chat.return_value = {
            "success": True,
            "content": """{
                "smart_analysis": "Liquidity sweep at $2,735 followed by bullish FVG confirmation.",
                "trade_execution": {
                    "action": "BUY",
                    "entry_price": 2736.50,
                    "stop_loss": 2728.00,
                    "take_profit_1": 2755.00,
                    "take_profit_2": 2770.00,
                    "risk_reward_ratio": "1:2.4",
                    "confidence": 85
                }
            }""",
            "model": "deepseek-r1",
            "latency_ms": 180
        }

        res = call_freellmapi(
            symbol_info={"symbol": "XAUUSD", "name": "Gold"},
            timeframe="15",
            metrics={"rsi": 42.0, "current_price": 2736.50}
        )
        assert res is not None
        assert res["trade_execution"]["action"] == "BUY"
        assert res["_llm_meta"]["provider"] == "freellmapi"
        assert res["_llm_meta"]["status"] == "SUCCESS"


class TestFreeLLMAPIRoutes:
    """Verifies the REST API endpoints under /api/v1/freellmapi/*."""

    def test_get_status_route(self, test_client):
        res = test_client.get("/api/v1/freellmapi/status")
        assert res.status_code == 200
        data = res.json()
        assert "status" in data
        assert "base_url" in data
        assert "github_url" in data

    def test_get_models_route(self, test_client):
        res = test_client.get("/api/v1/freellmapi/models")
        assert res.status_code == 200
        data = res.json()
        assert "models" in data
        assert isinstance(data["models"], list)
        assert len(data["models"]) > 0

    def test_configure_route(self, test_client):
        res = test_client.post(
            "/api/v1/freellmapi/configure",
            json={
                "base_url": "http://localhost:4000/v1",
                "default_model": "deepseek-r1",
                "api_key": "sk-custom-test-key"
            }
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["status"]["default_model"] == "deepseek-r1"

    @patch("taikry.ai.freellmapi_client.freellmapi_client.test_connection")
    def test_test_route_mocked(self, mock_test, test_client):
        mock_test.return_value = {
            "success": True,
            "response": "PONG",
            "model_used": "deepseek-r1",
            "latency_ms": 115,
            "message": "FreeLLMAPI verified!"
        }
        res = test_client.post("/api/v1/freellmapi/test")
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["response"] == "PONG"
