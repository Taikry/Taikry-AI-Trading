"""
Tests for AI Agents Debate ("និយាយគ្នាវិភាគ ទៅវិញទៅមក"),
Autonomous Self-Training ("Train ខ្លួនឯង"), and Alert-Auto-Fix Sentinel.
"""
import pytest
from fastapi.testclient import TestClient

from taikry.api.app import app
from taikry.agents.debate_engine import agent_debate_engine
from taikry.learning.self_trainer import agent_self_trainer
from taikry.monitoring.auto_fixer import auto_fix_engine

client = TestClient(app)

def test_agent_debate_engine_direct():
    """Verify that 4 AI agents engage in turn-by-turn debate with English and Khmer output."""
    res = agent_debate_engine.conduct_debate(symbol="XAUUSD", timeframe="M15")
    assert res is not None
    assert "turns" in res
    assert len(res["turns"]) == 4

    # Turn 1: Technical Analyst
    turn1 = res["turns"][0]
    assert turn1["agent_id"] == "technical_analyst"
    assert "message_en" in turn1 and len(turn1["message_en"]) > 20
    assert "message_kh" in turn1 and len(turn1["message_kh"]) > 20

    # Turn 2: ICT/SMC Analyst
    turn2 = res["turns"][1]
    assert turn2["agent_id"] == "ict_smc_analyst"
    assert "message_en" in turn2
    assert "message_kh" in turn2

    # Turn 3: Macro Analyst
    turn3 = res["turns"][2]
    assert turn3["agent_id"] == "macro_analyst"
    assert "message_en" in turn3
    assert "message_kh" in turn3

    # Turn 4: Risk Validator & Arbiter
    turn4 = res["turns"][3]
    assert turn4["agent_id"] == "risk_validator"
    assert "message_en" in turn4
    assert "message_kh" in turn4

    # Binding Decision & Verdict
    assert "consensus_decision" in res
    assert res["consensus_decision"] in ["APPROVE", "REJECT", "WAIT"]
    assert "debate_summary_en" in res and len(res["debate_summary_en"]) > 10
    assert "debate_summary_kh" in res and len(res["debate_summary_kh"]) > 10


def test_agent_self_trainer_direct():
    """Verify autonomous self-training and dynamic weight adjustments."""
    stats = agent_self_trainer.get_learning_stats()
    assert "total_epochs" in stats
    assert "weights" in stats
    assert "agents_scorecard" in stats
    assert len(stats["agents_scorecard"]) == 4

    # Check initial sum of weights close to 1.0
    weights_sum = sum(stats["weights"].values())
    assert 0.99 <= weights_sum <= 1.01

    # Run training epoch
    train_result = agent_self_trainer.train_epoch(symbol="XAUUSD")
    assert train_result["status"] == "EPOCH_COMPLETED"
    assert "epoch" in train_result
    assert "updated_weights" in train_result

    # Check updated weights sum to 1.0
    updated_sum = sum(train_result["updated_weights"].values())
    assert 0.99 <= updated_sum <= 1.01


def test_auto_fix_engine_direct():
    """Verify alert detection, diagnostic execution, and self-healing action logging."""
    incidents = auto_fix_engine.get_incidents(limit=5)
    assert isinstance(incidents, list)
    assert len(incidents) > 0

    # Trigger diagnostic and auto-fix
    fix_result = auto_fix_engine.run_diagnostic_and_fix()
    assert fix_result["status"] == "SYSTEM_OPTIMIZED"
    assert "incident_id" in fix_result
    assert "remediation_actions" in fix_result
    assert "message_kh" in fix_result


def test_api_endpoint_agents_debate():
    """Verify GET /api/v1/agents/debate returns 200 with structured turns."""
    res = client.get("/api/v1/agents/debate?symbol=XAUUSD&timeframe=M15")
    assert res.status_code == 200
    data = res.json()
    assert "turns" in data
    assert len(data["turns"]) == 4
    assert "consensus_decision" in data


def test_api_endpoint_self_training_and_stats():
    """Verify GET /api/v1/agents/learning-stats and POST /api/v1/agents/train."""
    res_stats = client.get("/api/v1/agents/learning-stats")
    assert res_stats.status_code == 200
    stats = res_stats.json()
    assert "weights" in stats

    res_train = client.post("/api/v1/agents/train?symbol=XAUUSD")
    assert res_train.status_code == 200
    train_data = res_train.json()
    assert train_data["status"] == "EPOCH_COMPLETED"


def test_api_endpoint_auto_fix():
    """Verify GET /api/v1/system/auto-fix/alerts and POST /api/v1/system/auto-fix/trigger."""
    res_alerts = client.get("/api/v1/system/auto-fix/alerts")
    assert res_alerts.status_code == 200
    alerts = res_alerts.json()
    assert isinstance(alerts, list)

    res_trigger = client.post("/api/v1/system/auto-fix/trigger")
    assert res_trigger.status_code == 200
    trigger_data = res_trigger.json()
    assert trigger_data["status"] == "SYSTEM_OPTIMIZED"
