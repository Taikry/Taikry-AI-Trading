"""
Automated Test Suite for Continuous AI Agent Reinforcement Learning & Weight Recalibration
========================================================================================
Validates:
1. Empirical evaluation of individual agent predictions against verified trade outcomes.
2. Reinforcement gradient ascent updating weights with institutional bounds [0.10, 0.50].
3. Normalization constraint: Sum of weights strictly equals 1.0000.
4. Database persistence in AgentLearningModel.
5. Autonomous trigger hook in xauusd_tracker on trade outcome resolution.
6. Scorecard and learning metrics formatting.
"""

import pytest
import datetime
import uuid
from unittest.mock import patch, MagicMock

from taikry.database.session import SessionLocal
from taikry.database.models import (
    AgentLearningModel,
    XAUUSDTelegramSignalModel,
    PaperTrade
)
from taikry.learning.self_trainer import (
    AgentSelfTrainer,
    agent_self_trainer,
    AGENT_METADATA,
    DEFAULT_WEIGHTS
)
from taikry.trading.xauusd_tracker import xauusd_performance_tracker


@pytest.fixture(autouse=True)
def cleanup_learning_test_data():
    """Cleans up mock signals created during test execution."""
    yield
    db = SessionLocal()
    try:
        db.query(XAUUSDTelegramSignalModel).filter(
            XAUUSDTelegramSignalModel.signal_id.like("SIG-TEST-RL-%")
        ).delete(synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def insert_mock_resolved_trade(sig_id: str, direction: str, outcome: str, agent_opinions: dict):
    """Helper to insert mock trade with known agent stances."""
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    db = SessionLocal()
    try:
        sig = XAUUSDTelegramSignalModel(
            signal_id=sig_id,
            canonical_symbol="XAUUSD",
            direction=direction,
            timeframes_analyzed=["M15", "H1"],
            entry_price=4050.0,
            stop_loss=4040.0 if direction == "BUY" else 4060.0,
            take_profit_1=4070.0 if direction == "BUY" else 4030.0,
            risk_reward_1=2.0,
            ai_confluence_score=85,
            consensus_summary="Mock test consensus",
            agent_opinions=agent_opinions,
            signal_status="TP1_HIT" if outcome == "WIN" else "SL_HIT",
            telegram_delivery_status="SENT",
            idempotency_key=f"idemp-{sig_id}",
            cambodia_date="2026-10-28",
            outcome=outcome,
            audit_history=[],
            created_at=now_dt,
            updated_at=now_dt
        )
        db.add(sig)
        db.commit()
    finally:
        db.close()


def test_empirical_evaluation_from_resolved_trades():
    """Verifies that individual agent predictions are correctly assessed against trade outcomes."""
    # Scenario:
    # Trade 1: BUY WIN. SMC was BULLISH (correct), Macro was BEARISH (incorrect).
    # Trade 2: BUY WIN. SMC was BULLISH (correct), Tech was BULLISH (correct).
    opinions_1 = {
        "ict_smc_analyst": {"bias": "BULLISH", "confidence": 85},
        "technical_analyst": {"bias": "BULLISH", "confidence": 75},
        "macro_analyst": {"bias": "BEARISH", "confidence": 60},
        "risk_validator": {"bias": "NEUTRAL", "confidence": 50}
    }
    insert_mock_resolved_trade("SIG-TEST-RL-1", "BUY", "WIN", opinions_1)

    opinions_2 = {
        "ict_smc_analyst": {"bias": "BULLISH", "confidence": 90},
        "technical_analyst": {"bias": "BULLISH", "confidence": 80},
        "macro_analyst": {"bias": "BULLISH", "confidence": 70},
        "risk_validator": {"bias": "NEUTRAL", "confidence": 50}
    }
    insert_mock_resolved_trade("SIG-TEST-RL-2", "BUY", "WIN", opinions_2)

    stats = agent_self_trainer.evaluate_empirical_contributions("XAUUSD")

    # SMC predicted BUY on both winning BUY trades
    assert stats["ict_smc_analyst"]["win_count"] >= 2
    assert stats["ict_smc_analyst"]["loss_count"] == 0

    # Macro was wrong on Trade 1 (BEARISH on a WINNING BUY)
    assert stats["macro_analyst"]["loss_count"] >= 1


def test_train_epoch_weight_recalibration_and_constraints():
    """Verifies that an empirical epoch recalibrates weights with strict bounds and normalization."""
    res = agent_self_trainer.train_epoch("XAUUSD")

    assert res["status"] == "EPOCH_COMPLETED"
    assert "updated_weights" in res
    weights = res["updated_weights"]

    # 1. Normalization constraint: Sum must equal exactly 1.0
    total_weight = round(sum(weights.values()), 4)
    assert total_weight == 1.0, f"Expected weight sum of 1.0, got {total_weight}"

    # 2. Institutional boundaries: Min 10% (0.10), Max 50% (0.50)
    for aid, w in weights.items():
        assert w >= 0.099, f"Agent {aid} weight {w} fell below 0.10 minimum bound"
        assert w <= 0.501, f"Agent {aid} weight {w} exceeded 0.50 maximum bound"

    # 3. Database persistence verification
    db = SessionLocal()
    try:
        db_records = db.query(AgentLearningModel).filter(
            AgentLearningModel.symbol == "XAUUSD"
        ).all()
        assert len(db_records) >= 4
        db_weights = {r.agent_id: round(r.current_weight, 4) for r in db_records}
        for aid, w in weights.items():
            assert abs(db_weights[aid] - w) < 0.001
    finally:
        db.close()


def test_learning_stats_scorecard_structure():
    """Verifies that learning stats returns a complete and rich scorecard for UI & Telegram."""
    stats = agent_self_trainer.get_learning_stats("XAUUSD")

    assert "total_epochs" in stats
    assert "overall_accuracy" in stats
    assert "weights" in stats
    assert "agents_scorecard" in stats
    assert len(stats["agents_scorecard"]) == 4

    for item in stats["agents_scorecard"]:
        assert "agent_id" in item
        assert "name" in item
        assert "specialization" in item
        assert "weight" in item
        assert "accuracy" in item
        assert "win_count" in item
        assert "brier_score" in item
        assert "status" in item
        assert item["status"] in ["ELITE_ACCURACY", "CALIBRATED", "OPTIMIZING"]


def test_xauusd_tracker_auto_triggers_reinforcement_on_trade_outcome():
    """Verifies that the performance tracker triggers self-training when a trade resolves."""
    # Create an active open signal in DB
    sig_id = f"SIG-TEST-RL-AUTO-{uuid.uuid4().hex[:6]}"
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    db = SessionLocal()
    try:
        sig = XAUUSDTelegramSignalModel(
            signal_id=sig_id,
            canonical_symbol="XAUUSD",
            direction="BUY",
            timeframes_analyzed=["M15"],
            entry_price=4050.0,
            stop_loss=4035.0,
            take_profit_1=4070.0,
            risk_reward_1=2.0,
            ai_confluence_score=88,
            consensus_summary="Auto-trigger test",
            agent_opinions={"ict_smc_analyst": {"bias": "BULLISH", "confidence": 85}},
            signal_status="OPEN",
            telegram_delivery_status="SENT",
            idempotency_key=f"idemp-{sig_id}",
            cambodia_date="2026-10-28",
            entry_reached=True,
            entry_reached_price=4050.0,
            outcome="PENDING",
            audit_history=[],
            created_at=now_dt,
            updated_at=now_dt
        )
        db.add(sig)
        db.commit()
    finally:
        db.close()

    # When market price hits TP1 (4070.0), tracker resolves outcome to WIN
    with patch.object(agent_self_trainer, "train_epoch") as mock_train:
        resolved = xauusd_performance_tracker.evaluate_signals_against_market(
            current_price=4071.0,
            high_price=4072.0,
            low_price=4050.0
        )
        # Should detect TP1_HIT / WIN
        win_event = [r for r in resolved if r.get("signal_id") == sig_id]
        assert len(win_event) == 1
        assert win_event[0]["outcome"] == "WIN"

        # Reinforcement training must have been automatically triggered!
        assert mock_train.call_count >= 1
        mock_train.assert_called_with("XAUUSD")
