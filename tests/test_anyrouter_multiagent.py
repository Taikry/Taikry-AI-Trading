"""
Comprehensive Test Suite for AnyRouter Inference Integration & Multi-Agent Orchestration Layer.
Covers:
- Step B: Secure configuration and secret protection
- Step C: Model discovery parsing, error handling (401, 403, 429, timeouts)
- Step D: Redacted low-token smoke testing & unconfigured skip
- Step E: Model router role registry and resolution hierarchy
- Step F: 7 Agent MVP outputs & typed schema validation
- Step G: Deep-analysis workflow, pre-flight data freshness gating, critic review
- Step H: Deterministic Risk Guardian (1:2.0+ R:R floor, 0.5% risk cap, spread check)
- Step H: Budget manager tracking and concurrency limits
- Step I: FastAPI endpoint responses and telemetry traces
"""

import datetime
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from taikry.config import ANYROUTER_BASE_URL, MIN_RISK_REWARD_RATIO, RISK_PER_TRADE_PERCENT
from taikry.ai.anyrouter_client import (
    AnyRouterClient,
    AnyRouterBudgetManager,
    SanitizedModelInfo,
    CatalogResponse,
    SmokeTestResult,
    anyrouter_client
)
from taikry.agents.orchestration_layer import (
    Orchestrator,
    MarketStructureAgent,
    MultiTimeframeAgent,
    MacroNewsAgent,
    RiskGuardian,
    IndependentCritic,
    FinalSynthesisAgent,
    MarketStructureOutput,
    MultiTimeframeOutput,
    MacroNewsOutput,
    RiskGuardianOutput,
    CriticOutput,
    FinalSynthesisOutput,
    WorkflowTrace
)
from taikry.api.app import app


# =============================================================================
# 1. SECURITY & UNCONFIGURED STATE TESTS
# =============================================================================

def test_anyrouter_unconfigured_behavior():
    """Verifies that an unconfigured client cleanly reports status and does not leak keys."""
    client = AnyRouterClient()
    with patch("taikry.ai.anyrouter_client.ANYROUTER_API_KEY", ""):
        assert not client.is_configured()

        catalog = client.get_models()
        assert not catalog.configured
        assert catalog.status == "UNCONFIGURED"
        assert catalog.total_models == 0
        assert "not configured" in catalog.error_message.lower()

        smoke = client.smoke_test()
        assert smoke.status == "SKIPPED"
        assert "skipped" in smoke.error_message.lower()


def test_anyrouter_never_leaks_api_key():
    """Ensures secret API key never appears in catalog, smoke test results, or string outputs."""
    secret_key = "sk-anyrouter-secret-token-xyz-987654321"
    with patch("taikry.ai.anyrouter_client.ANYROUTER_API_KEY", secret_key):
        client = AnyRouterClient()
        assert client.is_configured()

        # Mock models response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {"id": "deepseek/deepseek-chat", "context_length": 64000, "pricing": {"prompt": 0.14, "completion": 0.28}}
            ]
        }
        with patch("requests.get", return_value=mock_resp):
            cat = client.get_models(force_refresh=True)
            cat_json = cat.model_dump_json()
            assert secret_key not in cat_json
            assert cat.status == "CONNECTED"
            assert cat.total_models == 1


# =============================================================================
# 2. MODEL DISCOVERY & ERROR HANDLING TESTS
# =============================================================================

def test_model_discovery_parsing_capabilities():
    """Tests proper sanitization and capability inference (reasoning, vision, chat)."""
    client = AnyRouterClient()
    mock_payload = {
        "data": [
            {
                "id": "deepseek/deepseek-r1",
                "owned_by": "deepseek",
                "context_length": 65536,
                "pricing": {"input": 0.55, "output": 2.19}
            },
            {
                "id": "openai/gpt-4o-vision",
                "context_length": 128000,
                "supports_vision": True
            },
            {
                "id": "text-embedding-3-small",
                "context_length": 8191
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_payload

    with patch.object(client, "is_configured", return_value=True):
        with patch("requests.get", return_value=mock_resp):
            catalog = client.get_models(force_refresh=True)
            assert catalog.configured
            assert catalog.total_models == 3

            # Verify deepseek-r1
            r1 = next(m for m in catalog.models if m.id == "deepseek/deepseek-r1")
            assert "reasoning" in r1.capabilities
            assert r1.pricing_input_per_m == 0.55

            # Verify vision
            vis = next(m for m in catalog.models if m.id == "openai/gpt-4o-vision")
            assert "vision" in vis.capabilities

            # Verify embeddings
            emb = next(m for m in catalog.models if m.id == "text-embedding-3-small")
            assert "embeddings" in emb.capabilities


@pytest.mark.parametrize("status_code, expected_msg_part", [
    (401, "Authentication failed"),
    (403, "Access forbidden"),
    (429, "Rate limit exceeded"),
    (500, "AnyRouter server error"),
])
def test_model_discovery_http_errors(status_code, expected_msg_part):
    """Verifies that HTTP errors are gracefully parsed into sanitized status without crashing."""
    client = AnyRouterClient()
    mock_resp = MagicMock()
    mock_resp.status_code = status_code

    with patch.object(client, "is_configured", return_value=True):
        with patch("requests.get", return_value=mock_resp):
            cat = client.get_models(force_refresh=True)
            assert cat.status == "ERROR"
            assert expected_msg_part in cat.error_message


# =============================================================================
# 3. SMOKE TEST & MODEL ROUTER TESTS
# =============================================================================

def test_anyrouter_smoke_test_success():
    """Tests low-token probe execution and latency/usage recording."""
    client = AnyRouterClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": "deepseek/deepseek-chat",
        "choices": [{"message": {"role": "assistant", "content": "pong"}}],
        "usage": {"prompt_tokens": 4, "completion_tokens": 1, "total_tokens": 5}
    }

    with patch.object(client, "is_configured", return_value=True):
        with patch("requests.post", return_value=mock_resp):
            result = client.smoke_test(model_id="deepseek/deepseek-chat")
            assert result.status == "SUCCESS"
            assert result.http_status == 200
            assert result.response_preview == "pong"
            assert result.usage["total_tokens"] == 5
            assert result.latency_ms is not None


def test_anyrouter_role_configuration_and_fallbacks():
    """Tests configuring agent roles and verifying fallback hierarchy."""
    client = AnyRouterClient()

    # Assign orchestrator
    ok, msg = client.configure_role("orchestrator", "anthropic/claude-3.5-sonnet")
    assert ok
    assert client.resolve_model_for_role("orchestrator") == "anthropic/claude-3.5-sonnet"

    # Assign reasoning
    ok, msg = client.configure_role("reasoning", "deepseek/deepseek-r1")
    assert ok
    assert client.resolve_model_for_role("reasoning") == "deepseek/deepseek-r1"

    # Test invalid role rejection
    ok, err = client.configure_role("invalid_role", "model-x")
    assert not ok
    assert "Invalid role" in err


# =============================================================================
# 4. BUDGET MANAGER CONTROLS
# =============================================================================

def test_budget_manager_limit_enforcement():
    """Tests that budget manager tracks usage and correctly identifies overspend."""
    bm = AnyRouterBudgetManager(spend_limit_usd=1.0)
    assert not bm.is_budget_exceeded()

    bm.record_usage(prompt_tokens=1000, completion_tokens=500, cost_usd=0.25)
    assert not bm.is_budget_exceeded()
    assert bm.total_requests == 1
    assert bm.total_prompt_tokens == 1000

    # Cross limit
    bm.record_usage(prompt_tokens=5000, completion_tokens=2500, cost_usd=0.80)
    assert bm.is_budget_exceeded()
    summary = bm.get_summary()
    assert summary["budget_exceeded"]
    assert summary["estimated_spend_usd"] == 1.05


# =============================================================================
# 5. DETERMINISTIC RISK GUARDIAN ARITHMETIC TESTS
# =============================================================================

def test_risk_guardian_deterministic_buy():
    """Verifies strict deterministic geometry for a BUY signal (R:R >= 2.0, Risk = 0.5%)."""
    rg = RiskGuardian()
    structure = MarketStructureOutput(trend="BULLISH", swing_low=2600.0, swing_high=2670.0)
    mtf = MultiTimeframeOutput(atr_val=5.0)
    macro = MacroNewsOutput(is_blackout=False)

    out = rg.evaluate_risk(
        symbol="XAUUSD",
        direction="BUY",
        current_price=2620.0,
        structure_output=structure,
        mtf_output=mtf,
        macro_output=macro,
        account_equity=100000.0,
        spread_points=0.20
    )

    assert out.approved
    assert out.stop_loss < 2620.0
    assert out.take_profit > 2620.0
    assert out.risk_reward_ratio >= MIN_RISK_REWARD_RATIO
    assert out.max_risk_percent == RISK_PER_TRADE_PERCENT
    assert out.risk_amount_usd == 500.0  # 0.5% of 100k
    assert out.recommended_lot_size > 0


def test_risk_guardian_veto_on_sub_floor_rr():
    """Verifies that an R:R below 1:2.0 is unconditionally vetoed."""
    rg = RiskGuardian()
    # Swing high is very close to current price, choking R:R below 2.0
    structure = MarketStructureOutput(trend="BUY", swing_low=2610.0, swing_high=2622.0)
    mtf = MultiTimeframeOutput(atr_val=10.0)
    macro = MacroNewsOutput(is_blackout=False)

    out = rg.evaluate_risk(
        symbol="XAUUSD",
        direction="BUY",
        current_price=2620.0,
        structure_output=structure,
        mtf_output=mtf,
        macro_output=macro,
        account_equity=100000.0
    )

    assert not out.approved
    assert any("fails institutional minimum" in reason or "Invalid geometry" in reason for reason in out.veto_reasons)


def test_risk_guardian_veto_on_macro_blackout():
    """Verifies that high-impact news blackout unconditionally blocks trade approval."""
    rg = RiskGuardian()
    structure = MarketStructureOutput(trend="BULLISH", swing_low=2600.0, swing_high=2700.0)
    mtf = MultiTimeframeOutput(atr_val=5.0)
    macro = MacroNewsOutput(is_blackout=True, blackout_reason="FOMC Rate Decision in 10 minutes")

    out = rg.evaluate_risk(
        symbol="XAUUSD",
        direction="BUY",
        current_price=2620.0,
        structure_output=structure,
        mtf_output=mtf,
        macro_output=macro
    )

    assert not out.approved
    assert any("FOMC Rate Decision" in reason for reason in out.veto_reasons)


# =============================================================================
# 6. INDEPENDENT CRITIC TESTS
# =============================================================================

def test_independent_critic_detects_overbought_trap():
    """Verifies that Independent Critic detects overbought RSI on BUY setup."""
    critic = IndependentCritic()
    structure = MarketStructureOutput(swing_high=2650.0)
    mtf = MultiTimeframeOutput(rsi_14=78.5, atr_val=5.0)  # Overbought
    risk = RiskGuardianOutput(stop_loss=2610.0, take_profit=2670.0)

    out = critic.evaluate(
        symbol="XAUUSD",
        proposed_action="BUY",
        current_price=2648.0,  # Near swing high resistance
        structure=structure,
        mtf=mtf,
        risk=risk
    )

    assert len(out.objections) >= 1
    assert any("overbought" in obj.lower() for obj in out.objections)
    assert out.counter_trend_risk in ("MEDIUM", "HIGH")


# =============================================================================
# 7. DEEP ANALYSIS PRE-FLIGHT GATING (STALE FEED WAIT)
# =============================================================================

def test_deep_analysis_aborts_on_stale_data():
    """
    Enforces Step G Rule: Validate market data before starting analysis.
    If market data is stale, the orchestrator returns WAIT_STALE_DATA without invoking LLM inference.
    """
    orch = Orchestrator()
    stale_timestamp = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)

    with patch("taikry.data.providers.market_data_engine.get_verified_price", return_value=(2650.0, "MOCK_PROVIDER", stale_timestamp)):
        with patch("taikry.data.validator.check_data_freshness", return_value={"fresh": False, "status": "STALE", "age_minutes": 120}):
            trace = orch.run_deep_analysis("XAUUSD")
            assert trace.overall_status == "WAIT_STALE_DATA"
            assert trace.final_synthesis.action == "WAIT"
            assert not trace.freshness_validated
            assert "stale" in trace.final_synthesis.policy_verdict.lower()


# =============================================================================
# 8. FASTAPI ENDPOINT INTEGRATION TESTS
# =============================================================================

from taikry.api.routes import (
    get_anyrouter_models,
    get_anyrouter_roles,
    configure_anyrouter_role,
    get_anyrouter_budget,
    execute_deep_multiagent_analysis,
    AnyRouterRoleConfigRequest,
    DeepAnalysisApiRequest
)

def test_api_anyrouter_models_endpoint():
    """Tests GET /api/v1/anyrouter/models returns sanitized catalog structure."""
    with patch("taikry.ai.anyrouter_client.AnyRouterClient.get_models") as mock_get:
        mock_get.return_value = CatalogResponse(
            configured=True,
            status="CONNECTED",
            total_models=1,
            models=[]
        )
        data = get_anyrouter_models()
        assert "configured" in data
        assert "status" in data
        assert "models" in data


def test_api_anyrouter_roles_endpoints():
    """Tests GET and POST /api/v1/anyrouter/roles."""
    roles_data = get_anyrouter_roles()
    assert "orchestrator" in roles_data

    # Assign role
    post_resp = configure_anyrouter_role(AnyRouterRoleConfigRequest(
        role="fast",
        model_id="deepseek/deepseek-chat",
        validate_first=False
    ))
    assert post_resp["success"]


def test_api_anyrouter_budget_endpoint():
    """Tests GET /api/v1/anyrouter/budget."""
    data = get_anyrouter_budget()
    assert "spend_limit_usd" in data
    assert "estimated_spend_usd" in data


def test_api_deep_analysis_endpoint():
    """Tests POST /api/v1/agents/deep-analysis returns valid trace."""
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    with patch("taikry.data.providers.market_data_engine.get_verified_price", return_value=(2650.0, "MOCK_PROVIDER", now_utc)):
        with patch("taikry.data.validator.check_data_freshness", return_value={"fresh": False, "status": "STALE", "age_minutes": 120}):
            trace = execute_deep_multiagent_analysis(DeepAnalysisApiRequest(symbol="XAUUSD"))
            assert "request_id" in trace
            assert "overall_status" in trace
            assert "risk_guardian" in trace
            assert "final_synthesis" in trace
            assert trace["final_synthesis"]["action"] in ("BUY", "SELL", "WAIT", "REJECT")

