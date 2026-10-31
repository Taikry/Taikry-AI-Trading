"""Focused coverage for provider-backed Market Explorer and analysis jobs."""

import uuid

import pytest
from fastapi.testclient import TestClient

from taikry.api.app import app
from taikry.api import market_routes
from taikry.config import WATCHLIST
from taikry.data.providers import OandaDataProvider, get_symbol_config
from taikry.database.models import MarketSymbolRegistry
from taikry.database.session import SessionLocal, init_db
from taikry.markets.registry import normalize_symbol_text, resolve_market_symbol


@pytest.fixture
def signed_in_client():
    init_db()
    with TestClient(app) as client:
        email = f"market_{uuid.uuid4().hex[:12]}@example.test"
        response = client.post("/api/v1/auth/signup", json={
            "email": email,
            "password": "MarketExplorer#12345",
            "full_name": "Explorer Test",
            "language": "kh",
        })
        assert response.status_code == 200
        yield client


def test_symbol_alias_normalization_and_provider_mappings():
    assert normalize_symbol_text("EUR/USD") == "EURUSD"
    assert normalize_symbol_text("EUR_USD") == "EURUSD"
    assert OandaDataProvider.instrument_for("EURUSD") == "EUR_USD"
    assert get_symbol_config("BTCUSDT")["binance_symbol"] == "BTCUSDT"


def test_market_registry_search_and_timeframe_api(signed_in_client):
    response = signed_in_client.get("/api/v1/markets", params={"q": "EUR/USD", "discover": "false"})
    assert response.status_code == 200
    symbols = response.json()["symbols"]
    assert any(item["symbol"] == "EURUSD" for item in symbols)

    timeframes = signed_in_client.get("/api/v1/markets/BTCUSDT/timeframes")
    assert timeframes.status_code == 200
    assert timeframes.json()["timeframes"] == ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1"]


def test_dynamic_registry_alias_resolves_from_database():
    init_db()
    with SessionLocal() as db:
        row = MarketSymbolRegistry(
            symbol="AUDCAD",
            display_name="Australian Dollar / Canadian Dollar",
            asset_class="FOREX",
            provider="TEST_PROVIDER",
            provider_symbol="AUD_CAD",
            aliases=["AUDCAD", "AUD/CAD", "Australian Dollar / Canadian Dollar"],
            tv_symbol="FX:AUDCAD",
            enabled=True,
        )
        db.add(row)
        db.commit()
        found = resolve_market_symbol("AUD/CAD", db)
        assert found and found["symbol"] == "AUDCAD"
        db.delete(row)
        db.commit()


def test_market_registry_adds_common_commodity_and_crypto_aliases():
    init_db()
    with SessionLocal() as db:
        rows = [
            MarketSymbolRegistry(
                symbol="XAUUSD", display_name="Gold", asset_class="METALS",
                provider="TEST_PROVIDER", provider_symbol="XAU_USD",
                aliases=["XAUUSD"], tv_symbol="OANDA:XAUUSD", enabled=True,
            ),
            MarketSymbolRegistry(
                symbol="BTCUSDT", display_name="Bitcoin / Tether", asset_class="CRYPTO",
                provider="TEST_PROVIDER", provider_symbol="BTCUSDT",
                aliases=["BTCUSDT"], tv_symbol="BINANCE:BTCUSDT", enabled=True,
            ),
        ]
        db.add_all(rows)
        db.commit()
        assert resolve_market_symbol("Gold", db)["symbol"] == "XAUUSD"
        assert resolve_market_symbol("BTC", db)["symbol"] == "BTCUSDT"
        for row in rows:
            db.delete(row)
        db.commit()


def test_personal_favorites_and_watchlist_crud(signed_in_client):
    added = signed_in_client.post("/api/v1/me/market-favorites/EURUSD")
    assert added.status_code == 200
    favorites = signed_in_client.get("/api/v1/me/market-favorites")
    assert [item["symbol"] for item in favorites.json()["symbols"]] == ["EURUSD"]
    removed = signed_in_client.delete("/api/v1/me/market-favorites/EURUSD")
    assert removed.status_code == 200

    created = signed_in_client.post("/api/v1/me/watchlists", json={"name": "My Crypto"})
    assert created.status_code == 201
    list_id = created.json()["id"]
    assert signed_in_client.post(
        f"/api/v1/me/watchlists/{list_id}/symbols", json={"symbol": "BTCUSDT"}
    ).status_code == 200
    lists = signed_in_client.get("/api/v1/me/watchlists").json()["watchlists"]
    assert any(row["name"] == "My Crypto" and row["symbols"][0]["symbol"] == "BTCUSDT" for row in lists)
    assert signed_in_client.delete(
        f"/api/v1/me/watchlists/{list_id}/symbols/BTCUSDT"
    ).status_code == 200


def test_quick_analysis_job_uses_user_quota_and_persists_progress(signed_in_client, monkeypatch):
    class InlineExecutor:
        @staticmethod
        def submit(function, *args):
            return function(*args)

    monkeypatch.setattr(market_routes, "_analysis_executor", InlineExecutor())
    monkeypatch.setattr(market_routes, "_run_quick_analysis", lambda symbol, timeframe: {
        "symbol": symbol,
        "timeframe": timeframe,
        "mode": "QUICK",
        "data_status": "LIVE",
        "metrics": {"trend": "NEUTRAL"},
        "telegram_dispatched": False,
    })
    response = signed_in_client.post("/api/v1/analysis", json={
        "symbol": "EUR/USD", "mode": "QUICK", "timeframe": "M5", "profile": "SCALPING",
    })
    assert response.status_code == 202
    analysis_id = response.json()["analysis_id"]
    job = signed_in_client.get(f"/api/v1/analysis/{analysis_id}")
    assert job.status_code == 200
    assert job.json()["status"] == "COMPLETED"
    assert job.json()["result"]["telegram_dispatched"] is False
    recent = signed_in_client.get("/api/v1/me/recent-analysis")
    assert recent.status_code == 200
    assert recent.json()["items"][0]["symbol"] == "EURUSD"


def test_provider_failure_does_not_add_custom_market(signed_in_client, monkeypatch):
    monkeypatch.setattr(
        market_routes.market_data_engine,
        "get_verified_price",
        lambda symbol: (0.0, "UNAVAILABLE", None),
    )
    response = signed_in_client.post("/api/v1/markets/resolve", json={"symbol": "AUDCAD"})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "PROVIDER_UNAVAILABLE"


def test_scanner_universe_is_preserved_and_mobile_explorer_styles_exist():
    assert any(item["symbol"] == "XAUUSD" for item in WATCHLIST)
    assert any(item["symbol"] == "BTCUSDT" for item in WATCHLIST)
    with open("taikry/web/styles.css", encoding="utf-8") as css_file:
        css = css_file.read()
    assert ".market-explorer-card" in css
    assert "@media (max-width: 700px)" in css
