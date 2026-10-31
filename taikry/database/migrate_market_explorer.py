"""Create Market Explorer tables and seed the configured market catalog."""

import datetime
import logging

from sqlalchemy import inspect

from taikry.config import WATCHLIST
from taikry.database.models import Base, MarketSymbolRegistry
from taikry.database.session import SessionLocal, engine

logger = logging.getLogger("taikry.database.migrate_market_explorer")


def _asset_class(category: str) -> str:
    value = str(category or "").strip().upper()
    if value in {"COMMODITIES", "METALS"}:
        return "METALS"
    if value == "CRYPTO":
        return "CRYPTO"
    return "FOREX"


def run_migration(database_engine=None) -> None:
    database_engine = database_engine or engine
    Base.metadata.create_all(bind=database_engine)
    inspector = inspect(database_engine)
    for table_name in (
        "market_symbol_registry", "user_watchlists", "user_watchlist_items",
        "user_recent_analysis", "market_analysis_jobs",
    ):
        if not inspector.has_table(table_name):
            raise RuntimeError(f"Market Explorer table {table_name} was not created")

    db = SessionLocal()
    try:
        now = datetime.datetime.utcnow()
        for item in WATCHLIST:
            symbol = str(item.get("symbol") or "").upper()
            if not symbol:
                continue
            provider = "CONFIGURED"
            provider_symbol = symbol
            existing = db.query(MarketSymbolRegistry).filter_by(
                provider=provider, provider_symbol=provider_symbol
            ).first()
            fields = {
                "symbol": symbol,
                "display_name": str(item.get("name") or symbol),
                "asset_class": _asset_class(item.get("category")),
                "aliases": [symbol, str(item.get("name") or symbol)],
                "tv_symbol": item.get("tv_reference_symbol"),
                "enabled": True,
                "updated_at": now,
            }
            if existing:
                for key, value in fields.items():
                    setattr(existing, key, value)
            else:
                db.add(MarketSymbolRegistry(
                    provider=provider,
                    provider_symbol=provider_symbol,
                    last_verified_at=None,
                    **fields,
                ))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    logger.info("Market Explorer schema and configured symbol registry are ready.")
