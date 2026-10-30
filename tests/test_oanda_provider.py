import datetime
import importlib

import pandas as pd

from taikry.data import providers
from taikry.data.providers import MultiProviderMarketData, OandaDataProvider
from taikry.agents.data_quality_agent import data_quality_agent


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_oanda_symbol_mapping():
    assert OandaDataProvider.instrument_for("XAUUSD") == "XAU_USD"
    assert OandaDataProvider.instrument_for("EURUSD") == "EUR_USD"
    assert OandaDataProvider.instrument_for("BTCUSDT") == "BTC_USD"
    assert OandaDataProvider.instrument_for("AVAXUSDT") == "AVAX_USD"
    assert OandaDataProvider.instrument_for("unknown") is None


def test_oanda_quote_returns_verified_bid_ask(monkeypatch):
    provider = OandaDataProvider(api_token="test-token", account_id="demo-account", environment="practice")
    quote_time = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    requests = []

    def fake_get(url, **kwargs):
        requests.append((url, kwargs))
        return FakeResponse(200, {
            "prices": [{
                "instrument": "EUR_USD",
                "status": "tradeable",
                "time": quote_time,
                "bids": [{"price": "1.10000"}],
                "asks": [{"price": "1.10020"}],
            }]
        })

    monkeypatch.setattr(provider.session, "get", fake_get)
    quote = provider.get_latest_quote("EURUSD")

    assert quote is not None
    assert quote["bid"] == 1.1
    assert quote["ask"] == 1.1002
    assert round(quote["price"], 5) == 1.1001
    assert quote["source"] == "OANDA_V20"
    assert "api-fxpractice.oanda.com/v3/accounts/demo-account/pricing" in requests[0][0]
    assert requests[0][1]["params"] == {"instruments": "EUR_USD"}


def test_oanda_candles_are_normalized(monkeypatch):
    provider = OandaDataProvider(api_token="test-token", account_id="demo-account", environment="practice")
    candle_time = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")

    def fake_get(url, **kwargs):
        return FakeResponse(200, {"candles": [{
            "time": candle_time,
            "complete": True,
            "volume": 7,
            "mid": {"o": "1.1", "h": "1.2", "l": "1.0", "c": "1.15"},
        }]})

    monkeypatch.setattr(provider.session, "get", fake_get)
    candles = provider.fetch_ohlcv("EURUSD", timeframe="M15", limit=10)

    assert len(candles) == 1
    assert candles.iloc[0]["close"] == 1.15
    assert candles.iloc[0]["source"] == "oanda_v20:EUR_USD"


def test_oanda_auto_detects_practice_account_without_exposing_token(monkeypatch):
    provider = OandaDataProvider(api_token="test-token", environment="auto")
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        if "api-fxpractice.oanda.com/v3/accounts" in url:
            return FakeResponse(200, {"accounts": [{"id": "practice-account"}]})
        return FakeResponse(401, {"errorCode": "AUTHENTICATION_FAILED"})

    monkeypatch.setattr(provider.session, "get", fake_get)
    base_url, account_id = provider._resolve_account()

    assert base_url == provider.BASE_URLS["practice"]
    assert account_id == "practice-account"
    assert calls == [f"{provider.BASE_URLS['practice']}/v3/accounts"]


def test_oanda_without_token_never_calls_network(monkeypatch):
    provider = OandaDataProvider(api_token="", account_id="", environment="auto")

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("OANDA must remain idle when no token is configured")

    monkeypatch.setattr(provider.session, "get", fail_if_called)
    assert provider.get_latest_quote("EURUSD") is None
    assert provider.fetch_ohlcv("EURUSD").empty


def test_market_data_engine_prefers_oanda_for_verified_quotes(monkeypatch):
    quote_time = datetime.datetime.now(datetime.timezone.utc)

    class FakeOanda:
        configured = True

        def get_latest_quote(self, symbol):
            return {
                "symbol": symbol,
                "price": 1.1001,
                "bid": 1.1,
                "ask": 1.1002,
                "spread": 0.0002,
                "timestamp": quote_time,
                "source": "OANDA_V20",
                "provider": "OANDA",
            }

    monkeypatch.setattr(providers.mt5_receiver, "get_latest_price", lambda _symbol: (0.0, "none", False, {}))
    engine = MultiProviderMarketData()
    engine.oanda = FakeOanda()

    price, source, timestamp = engine.get_verified_price("EURUSD")
    quote = engine.get_verified_quote("EURUSD")

    assert price == 1.1001
    assert source == "OANDA_V20"
    assert timestamp == quote_time
    assert quote["bid"] == 1.1
    assert quote["ask"] == 1.1002


def test_oanda_candles_take_priority_over_reference_fallbacks(monkeypatch):
    engine = MultiProviderMarketData()
    candles = pd.DataFrame([{
        "timestamp": datetime.datetime.now(datetime.timezone.utc),
        "open": 1.1,
        "high": 1.2,
        "low": 1.0,
        "close": 1.15,
        "volume": 3,
        "source": "oanda_v20:EUR_USD",
    } for _ in range(5)])

    class FakeOanda:
        configured = True

        def fetch_ohlcv(self, *_args, **_kwargs):
            return candles

    monkeypatch.setattr(providers.mt5_receiver, "get_candles", lambda *_args, **_kwargs: pd.DataFrame())
    engine.oanda = FakeOanda()
    monkeypatch.setattr(engine.yahoo, "fetch_ohlcv", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Yahoo fallback should not run")))

    result = engine.get_candles("EURUSD", "M15", limit=5)

    assert result.iloc[-1]["source"] == "oanda_v20:EUR_USD"


def test_data_quality_agent_accepts_fresh_oanda_bid_ask(monkeypatch):
    now = datetime.datetime.now(datetime.timezone.utc)
    quote = {
        "symbol": "EURUSD",
        "price": 1.1001,
        "bid": 1.1,
        "ask": 1.1002,
        "spread": 0.0002,
        "timestamp": now,
        "source": "OANDA_V20",
        "provider": "OANDA",
    }
    candles = pd.DataFrame([{
        "timestamp": now,
        "open": 1.1,
        "high": 1.101,
        "low": 1.099,
        "close": 1.1001,
        "volume": 2,
        "source": "oanda_v20:EUR_USD",
    }])

    monkeypatch.setattr(providers.market_data_engine, "get_verified_quote", lambda _symbol: quote)
    monkeypatch.setattr(providers.market_data_engine, "get_verified_price", lambda _symbol: (1.1001, "OANDA_V20", now))
    monkeypatch.setattr(providers.market_data_engine, "get_candles", lambda *_args, **_kwargs: candles)
    quality_module = importlib.import_module("taikry.agents.data_quality_agent")
    monkeypatch.setattr(
        quality_module,
        "check_data_freshness",
        lambda *_args, **_kwargs: {"fresh": True, "age_seconds": 1, "status": "FRESH"},
    )

    result = data_quality_agent.analyze("EURUSD")

    assert result["feed_status"] == "HEALTHY"
    assert result["is_broker_connected"] is True
    assert result["broker_name"] == "OANDA"
    assert result["bid_price"] == 1.1
    assert result["ask_price"] == 1.1002
    assert result["spread_status"] == "NORMAL"
