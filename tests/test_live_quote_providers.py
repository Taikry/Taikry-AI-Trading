from taikry.data import providers


class _FakeResponse:
    status_code = 200

    @staticmethod
    def json():
        return {"symbol": "BTCUSDT", "bidPrice": "64999.9", "askPrice": "65000.1"}


def test_binance_book_ticker_returns_verified_bid_ask(monkeypatch):
    monkeypatch.setattr(providers.circuit_breaker, "can_try_binance", lambda: True)
    monkeypatch.setattr(providers.circuit_breaker, "record_success", lambda _name: None)
    monkeypatch.setattr(providers.circuit_breaker, "record_failure", lambda _name: None)
    monkeypatch.setattr(providers.requests, "get", lambda *args, **kwargs: _FakeResponse())

    quote = providers.BinanceDataProvider().get_latest_quote("BTCUSDT")

    assert quote is not None
    assert quote["source"] == "BINANCE_SPOT"
    assert quote["provider"] == "Binance Spot"
    assert quote["bid"] == 64999.9
    assert quote["ask"] == 65000.1
    assert quote["spread"] > 0


def test_verified_quote_uses_binance_for_crypto_when_broker_quotes_are_missing(monkeypatch):
    quote = {
        "symbol": "BTCUSDT",
        "bid": 64999.9,
        "ask": 65000.1,
        "price": 65000.0,
        "spread": 0.2,
        "source": "BINANCE_SPOT",
        "provider": "Binance Spot",
    }
    monkeypatch.setattr(providers.mt5_receiver, "get_latest_price", lambda _symbol: (0.0, "", False, {}))
    monkeypatch.setattr(providers.market_data_engine.oanda, "get_latest_quote", lambda _symbol: None)
    monkeypatch.setattr(providers.market_data_engine.binance, "get_latest_quote", lambda _symbol: quote)

    result = providers.market_data_engine.get_verified_quote("BTCUSDT")

    assert result == quote
