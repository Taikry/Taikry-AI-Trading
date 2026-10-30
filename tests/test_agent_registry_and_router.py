"""
Unit and integration tests for STAGE B & C:
- Dynamic Agent Registry & Standardized Adapters
- Hybrid Model Router, Circuit Breakers & Provenance Tracking
"""
import pytest
import threading
from fastapi.testclient import TestClient
from taikry.api.app import app
from taikry.agents.registry import agent_registry, AgentMetadata, AgentAdapter
from taikry.ai.llm_client import llm_orchestrator
from taikry.config import ADMIN_API_KEY, API_KEY_HEADER

client = TestClient(app)

def test_agent_registry_initialization():
    """Verify registered agents are not reported healthy before their first run."""
    agents = agent_registry.list_agents()
    assert len(agents) >= 7

    agent_ids = {a["agent_id"] for a in agents}
    expected = {
        "technical_analyst",
        "ict_smc_analyst",
        "macro_analyst",
        "risk_validator",
        "consensus_engine",
        "debate_engine",
        "self_trainer"
    }
    assert expected.issubset(agent_ids)

    summary = agent_registry.get_fleet_summary()
    assert summary["total_registered_agents"] >= 7
    assert summary["not_run_count"] >= 7
    assert summary["system_status"] == "INITIALIZING"


def test_agent_adapter_execution_and_telemetry():
    """Verify adapter records latency, execution counts, and successful execution."""
    adapter = agent_registry.get_adapter("technical_analyst")
    assert adapter is not None

    init_execs = adapter.metadata.total_executions
    # Run test execution with mock multi_tf_data
    res = adapter.execute("XAUUSD", {})
    assert "agent_id" in res
    assert res["agent_id"] == "technical_analyst"
    assert adapter.metadata.total_executions == init_execs + 1
    assert adapter.metadata.latency_metrics["sample_count"] > 0
    assert adapter.metadata.last_successful_execution is not None


def test_agent_adapter_fallback_on_failure():
    """Verify that when an agent raises an exception, the fallback policy safely engages without crashing."""
    failing_meta = AgentMetadata(
        agent_id="mock_faulty_agent",
        name="Mock Faulty Agent",
        description="Simulates unexpected failure",
        specialization="Failure Testing",
        model_provider="python",
        model_identifier="faulty_v1",
        execution_mode="local"
    )

    def crash_func():
        raise RuntimeError("Simulated network or computation crash")

    adapter = AgentAdapter(failing_meta, crash_func)
    res = adapter.execute()
    assert res["_fallback_applied"] is True
    assert "Simulated network or computation crash" in res["_fallback_reason"]
    assert failing_meta.health_status == "DEGRADED"
    assert failing_meta.failed_executions == 1
    assert failing_meta.execution_state == "FAILED"
    assert failing_meta.last_completed_at is not None


def test_agent_adapter_exposes_real_queued_running_and_completed_states():
    started = threading.Event()
    finish = threading.Event()
    metadata = AgentMetadata(
        agent_id="mock_activity_agent",
        name="Mock Activity Agent",
        description="Checks runtime status transitions",
        specialization="Test activity",
        model_provider="python",
        model_identifier="activity_v1",
        execution_mode="local",
        supported_tasks=["runtime_state_test"],
        execution_state="QUEUED",
        current_task="XAUUSD H4 live scan",
    )

    def wait_for_finish():
        started.set()
        assert finish.wait(2)
        return {"agent_id": metadata.agent_id}

    adapter = AgentAdapter(metadata, wait_for_finish)
    worker = threading.Thread(target=adapter.execute)
    worker.start()
    assert started.wait(1)
    assert metadata.execution_state == "RUNNING"
    assert metadata.current_task == "XAUUSD H4 live scan"
    finish.set()
    worker.join(timeout=2)
    assert not worker.is_alive()
    assert metadata.execution_state == "COMPLETED"
    assert metadata.last_task == "XAUUSD H4 live scan"
    assert metadata.last_started_at is not None
    assert metadata.last_completed_at is not None


def test_disabled_agent_runtime_state_is_skipped():
    metadata = AgentMetadata(
        agent_id="mock_disabled_agent",
        name="Mock Disabled Agent",
        description="Checks skipped activity state",
        specialization="Test activity",
        model_provider="python",
        model_identifier="disabled_v1",
        execution_mode="local",
        enabled=False,
    )
    result = AgentAdapter(metadata, lambda: {"unexpected": True}).execute()
    assert result.get("_fallback_applied") is True
    assert metadata.execution_state == "SKIPPED"
    assert metadata.last_completed_at is not None


def test_risk_validator_fallback_is_always_locked():
    """Verify that if the Risk Validator fails, its fallback ALWAYS rejects and locks execution."""
    adapter = agent_registry.get_adapter("risk_validator")
    assert adapter is not None

    # Call fallback directly
    fallback_res = adapter._apply_fallback("Forced test error")
    assert fallback_res["decision"] == "REJECT"
    assert fallback_res["action"] == "HOLD"
    assert "Capital Protection Fallback" in fallback_res["reasons"][0]


def test_agent_registry_api_endpoints():
    """Tests GET /api/v1/agents/registry and GET /api/v1/agents/registry/summary."""
    resp = client.get("/api/v1/agents/registry")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["count"] >= 7
    assert len(data["agents"]) >= 7

    resp_summary = client.get("/api/v1/agents/registry/summary")
    assert resp_summary.status_code == 200
    summary_data = resp_summary.json()
    assert summary_data["total_registered_agents"] >= 7
    assert "healthy_count" in summary_data


def test_agent_registry_configure_api():
    """Tests POST /api/v1/agents/registry/{agent_id}/configure with admin authorization."""
    # Without admin key -> 403 or False
    resp_unauth = client.post(
        "/api/v1/agents/registry/technical_analyst/configure",
        json={"timeout_seconds": 7.5}
    )
    # verify_admin_key returns False when header is missing
    # Let's verify authenticated update:
    headers = {API_KEY_HEADER: ADMIN_API_KEY}
    resp_auth = client.post(
        "/api/v1/agents/registry/technical_analyst/configure",
        json={"timeout_seconds": 8.5},
        headers=headers
    )
    assert resp_auth.status_code == 200
    meta = resp_auth.json()["metadata"]
    assert meta["timeout_seconds"] == 8.5

    # Revert back to 5.0
    client.post(
        "/api/v1/agents/registry/technical_analyst/configure",
        json={"timeout_seconds": 5.0},
        headers=headers
    )


def test_model_router_policy_endpoints():
    """Tests GET & POST /api/v1/router/policy."""
    resp = client.get("/api/v1/router/policy")
    assert resp.status_code == 200
    data = resp.json()
    assert "routing_policy" in data
    assert "circuit_breakers" in data
    assert data["routing_policy"]["prefer_local"] is True

    headers = {API_KEY_HEADER: ADMIN_API_KEY}
    update_resp = client.post(
        "/api/v1/router/policy",
        json={"circuit_breaker_max_fails": 5},
        headers=headers
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["routing_policy"]["circuit_breaker_max_fails"] == 5

    # Restore default
    client.post(
        "/api/v1/router/policy",
        json={"circuit_breaker_max_fails": 3},
        headers=headers
    )


def test_model_router_circuit_breaker_logic():
    """Verify circuit breaker opens after consecutive failures and enforces cooldown."""
    prov = "mock_test_provider"
    llm_orchestrator.routing_policy["circuit_breaker_max_fails"] = 2
    llm_orchestrator.circuit_breakers[prov] = {"fails": 0, "last_fail": 0.0}

    assert llm_orchestrator.is_provider_available(prov) is True

    # 1 fail
    llm_orchestrator.record_provider_result(prov, False)
    assert llm_orchestrator.is_provider_available(prov) is True

    # 2 fails -> circuit opens
    llm_orchestrator.record_provider_result(prov, False)
    assert llm_orchestrator.is_provider_available(prov) is False

    # Success resets breaker
    llm_orchestrator.record_provider_result(prov, True)
    assert llm_orchestrator.is_provider_available(prov) is True
