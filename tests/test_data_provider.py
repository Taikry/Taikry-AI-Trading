"""
Unit and Integration tests for Milestone 1: Data Provider and Validation
"""
import pytest
import datetime
import pandas as pd
from taikry.database.session import init_db, SessionLocal
from taikry.database.models import MarketSnapshot
from taikry.data.validator import is_market_open, validate_dataframe, check_data_freshness
from taikry.data.providers import market_data_engine

def test_database_initialization():
    init_db()
    db = SessionLocal()
    assert db is not None
    db.close()

def test_market_validation_clean():
    clean_df = pd.DataFrame({
        "timestamp": [datetime.datetime.now(datetime.timezone.utc) for _ in range(50)],
        "open": [2000.0 + i for i in range(50)],
        "high": [2005.0 + i for i in range(50)],
        "low": [1995.0 + i for i in range(50)],
        "close": [2002.0 + i for i in range(50)],
        "volume": [100.0] * 50
    })
    res = validate_dataframe(clean_df, min_bars=30)
    assert res["valid"] is True
    assert res["rows"] == 50

def test_market_validation_corrupt():
    corrupt_df = pd.DataFrame({
        "timestamp": [datetime.datetime.now(datetime.timezone.utc) for _ in range(50)],
        "open": [2000.0] * 50,
        "high": [1990.0] * 50,  # Invalid: high < open
        "low": [2005.0] * 50,
        "close": [2000.0] * 50
    })
    res = validate_dataframe(corrupt_df, min_bars=30)
    assert res["valid"] is False

def test_crypto_is_always_open():
    open_now, _ = is_market_open("BTCUSDT")
    assert open_now is True

def test_real_market_fetch_gold():
    df = market_data_engine.get_candles("XAUUSD", "M15", limit=50)
    assert not df.empty, "Gold candle fetch should return data"
    assert "close" in df.columns
    assert len(df) > 10

def test_real_market_fetch_crypto():
    df = market_data_engine.get_candles("BTCUSDT", "M15", limit=50)
    assert not df.empty, "Crypto candle fetch should return data"
    assert "close" in df.columns
    assert len(df) > 10

def test_verified_price():
    price, source, ts = market_data_engine.get_verified_price("XAUUSD")
    assert price > 0, "XAUUSD price must be positive"
    assert source != "unavailable"
    assert ts is not None
