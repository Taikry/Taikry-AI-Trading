"""Provider-aware, cached market symbol discovery and canonicalization."""

import datetime
import logging
import re
import threading
import time
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from taikry.config import WATCHLIST
from taikry.database.models import MarketSymbolRegistry
from taikry.database.session import SessionLocal
from taikry.data.providers import market_data_engine

logger = logging.getLogger("taikry.markets.registry")
DISCOVERY_TTL_SECONDS = 6 * 60 * 60
_discovery_lock = threading.Lock()
_last_discovery_at = 0.0


def normalize_symbol_text(value: str) -> str:
    """Normalize common input forms such as EUR/USD, EUR_USD, and BTCUSDT."""
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())[:32]


def _asset_class(symbol: str, provider_class: str = "") -> str:
    name = str(symbol or "").upper().replace("_", "")
    if name.startswith(("XAU", "XAG")):
        return "METALS"
    if provider_class.upper() in {"CRYPTO", "DIGITAL_CURRENCY"}:
        return "CRYPTO"
    crypto_codes = {"BTC", "ETH", "LTC", "XRP", "BCH", "SOL", "ADA", "DOT", "DOGE", "LINK", "AVAX", "BNB"}
    if name.endswith("USDT") or any(name.startswith(code) and name[len(code):] in {"USD", "USDT", "EUR", "GBP"} for code in crypto_codes):
        return "CRYPTO"
    return "FOREX"


def _canonical_provider_symbol(provider_symbol: str) -> str:
    return normalize_symbol_text(provider_symbol)


def _upsert_symbol(
    db: Session,
    *,
    symbol: str,
    display_name: str,
    asset_class: str,
    provider: str,
    provider_symbol: str,
    aliases: Optional[List[str]] = None,
    tv_symbol: Optional[str] = None,
    verified_at: Optional[datetime.datetime] = None,
) -> None:
    if not symbol or not provider_symbol:
        return
    existing = db.query(MarketSymbolRegistry).filter_by(
        provider=provider, provider_symbol=provider_symbol
    ).first()
    values = {
        "symbol": symbol,
        "display_name": display_name or symbol,
        "asset_class": asset_class,
        "aliases": list(dict.fromkeys([symbol, *(aliases or [])]))[:20],
        "tv_symbol": tv_symbol,
        "enabled": True,
        "last_verified_at": verified_at,
        "updated_at": datetime.datetime.utcnow(),
    }
    if existing:
        for field, value in values.items():
            setattr(existing, field, value)
    else:
        db.add(MarketSymbolRegistry(
            provider=provider,
            provider_symbol=provider_symbol,
            **values,
        ))


def refresh_provider_symbols(force: bool = False) -> Dict[str, int]:
    """Refresh provider symbol lists at most once per TTL, never per typed search."""
    global _last_discovery_at
    now = time.monotonic()
    if not force and now - _last_discovery_at < DISCOVERY_TTL_SECONDS:
        return {"cached": 1, "oanda": 0, "binance": 0}
    with _discovery_lock:
        now = time.monotonic()
        if not force and now - _last_discovery_at < DISCOVERY_TTL_SECONDS:
            return {"cached": 1, "oanda": 0, "binance": 0}
        counts = {"cached": 0, "oanda": 0, "binance": 0}
        db = SessionLocal()
        try:
            verified_at = datetime.datetime.utcnow()
            # OANDA discovery is account-authorized; it is skipped when no token is configured.
            for item in market_data_engine.oanda.discover_instruments(DISCOVERY_TTL_SECONDS):
                provider_symbol = str(item.get("name") or "").upper()
                if not re.fullmatch(r"[A-Z0-9]{2,6}_[A-Z0-9]{2,6}", provider_symbol):
                    continue
                symbol = _canonical_provider_symbol(provider_symbol)
                klass = _asset_class(provider_symbol)
                if klass not in {"FOREX", "METALS", "CRYPTO"}:
                    continue
                base_name = str(item.get("display_name") or provider_symbol.replace("_", "/"))
                _upsert_symbol(
                    db,
                    symbol=symbol,
                    display_name=base_name,
                    asset_class=klass,
                    provider="OANDA",
                    provider_symbol=provider_symbol,
                    aliases=[provider_symbol, provider_symbol.replace("_", "/"), symbol],
                    tv_symbol=f"FX:{symbol}" if klass == "FOREX" else f"OANDA:{symbol}",
                    verified_at=verified_at,
                )
                counts["oanda"] += 1

            for item in market_data_engine.binance.discover_spot_symbols(DISCOVERY_TTL_SECONDS):
                symbol = str(item.get("symbol") or "").upper()
                base = str(item.get("base_asset") or "").upper()
                if not symbol.endswith("USDT") or not re.fullmatch(r"[A-Z0-9]{2,24}USDT", symbol):
                    continue
                _upsert_symbol(
                    db,
                    symbol=symbol,
                    display_name=f"{base} / Tether" if base else symbol,
                    asset_class="CRYPTO",
                    provider="BINANCE_SPOT",
                    provider_symbol=symbol,
                    aliases=[symbol, base, f"{base}USDT"],
                    tv_symbol=f"BINANCE:{symbol}",
                    verified_at=verified_at,
                )
                counts["binance"] += 1
            db.commit()
            _last_discovery_at = time.monotonic()
            return counts
        except Exception:
            db.rollback()
            logger.exception("Provider market-symbol refresh failed; existing registry is retained.")
            # Avoid a provider outage causing a network call for every search.
            _last_discovery_at = time.monotonic()
            return counts
        finally:
            db.close()


def market_catalog(
    db: Optional[Session] = None,
    *,
    query: str = "",
    asset_class: str = "ALL",
    limit: int = 100,
    discover: bool = False,
) -> List[Dict[str, Any]]:
    if discover:
        refresh_provider_symbols()
    own_session = db is None
    session = db or SessionLocal()
    try:
        rows = session.query(MarketSymbolRegistry).filter(
            MarketSymbolRegistry.enabled.is_(True)
        ).order_by(MarketSymbolRegistry.symbol.asc()).all()
        grouped: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            item = grouped.setdefault(row.symbol, {
                "symbol": row.symbol,
                "name": row.display_name,
                "asset_class": row.asset_class,
                "providers": [],
                "aliases": [],
                "tv_symbol": row.tv_symbol,
                "last_verified_at": None,
                "scanner_priority": None,
            })
            if row.provider not in item["providers"]:
                item["providers"].append(row.provider)
            item["aliases"].extend(row.aliases or [])
            item["last_verified_at"] = max(
                [value for value in (item["last_verified_at"], row.last_verified_at) if value],
                default=None,
            )
            if row.provider == "CONFIGURED":
                item["name"] = row.display_name
                item["tv_symbol"] = row.tv_symbol
        for item in grouped.values():
            symbol = item["symbol"]
            aliases = item["aliases"]
            if len(symbol) == 6 and symbol.isalpha() and item["asset_class"] == "FOREX":
                aliases.append(f"{symbol[:3]}/{symbol[3:]}")
            if symbol.endswith("USDT"):
                aliases.append(symbol[:-4])
            if "/" in item["name"]:
                aliases.append(item["name"].split("/", 1)[0].strip())
            if symbol == "XAUUSD":
                aliases.extend(["Gold", "XAU", "XAU/USD"])
            elif symbol == "XAGUSD":
                aliases.extend(["Silver", "XAG", "XAG/USD"])
            item["aliases"] = list(dict.fromkeys(aliases))
            configured = next((w for w in WATCHLIST if w["symbol"] == item["symbol"]), None)
            item["scanner_priority"] = configured.get("priority") if configured else None
            item["data_status"] = "PROVIDER_SUPPORTED"
            item["last_verified_at"] = item["last_verified_at"].isoformat() if item["last_verified_at"] else None

        q_norm = normalize_symbol_text(query)
        selected_class = str(asset_class or "ALL").upper()
        results = []
        for item in grouped.values():
            if selected_class not in {"ALL", "FAVORITES", "AI_SCANNER"} and item["asset_class"] != selected_class:
                continue
            if selected_class == "AI_SCANNER" and item["scanner_priority"] is None:
                continue
            search_values = [item["symbol"], item["name"], *item["aliases"]]
            if q_norm and not any(q_norm in normalize_symbol_text(value) for value in search_values):
                continue
            results.append(item)
        results.sort(key=lambda item: (item["scanner_priority"] is None, item["scanner_priority"] or 999, item["symbol"]))
        return results[:max(1, min(int(limit), 2000))]
    finally:
        if own_session:
            session.close()


def resolve_market_symbol(value: str, db: Optional[Session] = None) -> Optional[Dict[str, Any]]:
    normalized = normalize_symbol_text(value)
    if not normalized:
        return None
    for item in market_catalog(db, limit=2000):
        candidates = [item["symbol"], item["name"], *item["aliases"]]
        if any(normalized == normalize_symbol_text(candidate) for candidate in candidates):
            return item
    return None
