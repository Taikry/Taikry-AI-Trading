"""
Unit and Integration tests for Milestone 4: Paper Trading and Backtesting Engine
"""
import pytest
import datetime
import pandas as pd
from taikry.trading.paper_trading import paper_trading_engine
from taikry.trading.backtester import backtest_engine
from taikry.data.providers import market_data_engine
from taikry.database.session import SessionLocal
from taikry.database.models import PaperTrade

@pytest.fixture(autouse=True)
def clean_open_trades():
    db = SessionLocal()
    try:
        db.query(PaperTrade).filter(PaperTrade.status == "OPEN").update({"status": "CLOSED", "exit_price": 2000.0, "pnl": 0.0})
        db.commit()
    finally:
        db.close()
    yield

def test_paper_trading_account_summary():
    summary = paper_trading_engine.get_account_summary()
    assert summary["initial_balance"] == 100000.0
    assert summary["current_balance"] > 0
    assert "currency" in summary

def test_open_paper_trade():
    res = paper_trading_engine.open_trade(
        symbol="XAUUSD",
        direction="BUY",
        entry_price=2000.0,
        stop_loss=1990.0,       # Risk = $10 / oz
        take_profit_1=2020.0,   # Reward = $20 / oz (1:2 R:R)
        take_profit_2=2035.0
    )
    assert res["success"] is True
    assert res["status"] == "OPEN"
    assert res["lot_size"] > 0
    assert res["risk_amount"] > 0

def test_paper_trade_tp_trigger():
    paper_trading_engine.open_trade(
        symbol="XAUUSD",
        direction="BUY",
        entry_price=2000.0,
        stop_loss=1990.0,
        take_profit_1=2020.0,
        take_profit_2=2035.0
    )
    # Simulate market price rally to 2025 -> should trigger TP1 (2020)
    closed = paper_trading_engine.update_open_trades({"XAUUSD": 2025.0})
    assert len(closed) > 0
    first = closed[0]
    assert first["exit_reason"] in ["HIT_TP1", "HIT_TP2"]
    assert first["net_pnl"] > 0
    assert first["r_multiple"] >= 1.5

def test_backtest_execution():
    # Fetch real historical candles for XAUUSD
    df = market_data_engine.get_candles("XAUUSD", "M15", limit=100)
    assert not df.empty and len(df) >= 50

    scorecard = backtest_engine.run_backtest(
        symbol="XAUUSD",
        timeframe="M15",
        candles_df=df,
        initial_balance=100000.0
    )

    assert scorecard["status"] == "COMPLETED"
    assert "job_id" in scorecard
    assert "win_rate_percent" in scorecard
    assert "net_profit" in scorecard
    assert "profit_factor" in scorecard
    assert "max_drawdown_percent" in scorecard
    assert "average_r_multiple" in scorecard
    assert "trades" in scorecard
    assert "equity_curve_sample" in scorecard
