"""User-controlled Market Explorer and asynchronous analysis endpoints."""

import datetime
import logging
import math
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from taikry.api.saas_routes import get_current_user
from taikry.config import INITIAL_PAPER_BALANCE, get_symbol_config
from taikry.data.providers import market_data_engine
from taikry.data.validator import check_data_freshness, is_market_open, validate_dataframe
from taikry.database.models import (
    MarketAnalysisJob,
    MarketSymbolRegistry,
    User,
    UserRecentAnalysis,
    UserWatchlist,
    UserWatchlistItem,
)
from taikry.database.session import SessionLocal, get_db
from taikry.indicators.technical import compute_technical_indicators, extract_technical_summary
from taikry.markets.registry import market_catalog, resolve_market_symbol

logger = logging.getLogger("taikry.api.market_routes")
market_router = APIRouter(tags=["Market Explorer"])
_analysis_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="market-analysis")
_job_update_lock = threading.Lock()
_analysis_slots = threading.BoundedSemaphore(8)

TIMEFRAME_PROFILES = {
    "SCALPING": ["M1", "M5", "M15", "H1"],
    "INTRADAY": ["M5", "M15", "H1", "H4"],
    "SWING": ["H1", "H4", "D1", "W1"],
    "FULL": ["M1", "M5", "M15", "M30", "H1", "H4", "D1"],
}
SUPPORTED_TIMEFRAMES = {"M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1"}


class WatchlistCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=64)


class WatchlistSymbolRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)


class MarketAnalysisRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)
    mode: Literal["QUICK", "STANDARD", "DEEP"] = "STANDARD"
    timeframe: Literal["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1"] = "M15"
    profile: Literal["SCALPING", "INTRADAY", "SWING", "FULL"] = "INTRADAY"
    force_fresh: bool = False


class MarketResolveRequest(BaseModel):
    symbol: str = Field(..., min_length=2, max_length=40)


def _allowed_timeframes(symbol_item: Dict[str, Any]) -> List[str]:
    providers = set(symbol_item.get("providers") or [])
    if providers.intersection({"BINANCE_SPOT", "OANDA"}):
        return ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1"]
    return ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1"]


def _market_row(db: Session, symbol: str) -> Optional[Dict[str, Any]]:
    return resolve_market_symbol(symbol, db)


@market_router.get("/api/v1/markets")
def list_markets(
    q: str = Query(default="", max_length=80),
    asset_class: str = Query(default="ALL", max_length=20),
    limit: int = Query(default=100, ge=1, le=250),
    discover: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    """Search configured and provider-discovered instruments; discovery is six-hour cached."""
    klass = asset_class.strip().upper()
    if klass not in {"ALL", "METALS", "FOREX", "CRYPTO", "AI_SCANNER", "FAVORITES"}:
        raise HTTPException(status_code=400, detail="Unsupported asset class.")
    symbols = market_catalog(db, query=q, asset_class=klass, limit=limit, discover=discover)
    return {
        "symbols": symbols,
        "count": len(symbols),
        "discovery_cache_seconds": 21600,
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


@market_router.get("/api/v1/markets/search")
def search_markets(
    q: str = Query(default="", min_length=1, max_length=80),
    asset_class: str = Query(default="ALL", max_length=20),
    limit: int = Query(default=50, ge=1, le=250),
    db: Session = Depends(get_db),
):
    return list_markets(q=q, asset_class=asset_class, limit=limit, discover=True, db=db)


@market_router.post("/api/v1/markets/resolve")
def verify_custom_market_symbol(
    payload: MarketResolveRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Explicitly verify an exact user-entered symbol once, then cache it in the registry."""
    from taikry.markets.registry import normalize_symbol_text

    raw = normalize_symbol_text(payload.symbol)
    existing = resolve_market_symbol(raw, db)
    if existing:
        return {"success": True, "symbol": existing, "cached": True}
    if raw in {"XAU", "GOLD"}:
        raw = "XAUUSD"
    elif raw in {"XAG", "SILVER"}:
        raw = "XAGUSD"
    allowed_currency_codes = {
        "USD", "EUR", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF", "SGD", "HKD",
        "NOK", "SEK", "MXN", "TRY", "PLN", "CNH", "ZAR", "CZK", "HUF", "THB",
    }
    is_forex = len(raw) == 6 and raw[:3] in allowed_currency_codes and raw[3:] in allowed_currency_codes
    if not is_forex and raw not in {"XAUUSD", "XAGUSD"} and not raw.endswith("USDT") and 2 <= len(raw) <= 15 and raw.isalnum():
        raw = f"{raw}USDT"
    is_crypto = raw.endswith("USDT") and 7 <= len(raw) <= 28
    if raw not in {"XAUUSD", "XAGUSD"} and not (is_crypto or is_forex):
        raise HTTPException(status_code=400, detail={"code": "SYMBOL_NOT_FOUND", "message": "Enter a supported currency pair or crypto base symbol."})

    cfg = get_symbol_config(raw)
    try:
        price, source, timestamp = market_data_engine.get_verified_price(raw)
        freshness = check_data_freshness(raw, timestamp, "M1")
        source_valid = not any(flag in str(source).upper() for flag in ("DEMO", "SYNTHETIC", "UNAVAILABLE", "NONE"))
        if not price or price <= 0 or not freshness.get("fresh") or not source_valid:
            raise HTTPException(status_code=422, detail={"code": "PROVIDER_UNAVAILABLE", "message": "No fresh verified provider quote was returned for that symbol."})
        candles = market_data_engine.get_candles(raw, "M15", limit=30)
        if candles is None or candles.empty or len(candles) < 15:
            raise HTTPException(status_code=422, detail={"code": "INSUFFICIENT_DATA", "message": "The provider did not return enough candles to analyze this symbol."})
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Explicit provider verification failed for %s", raw)
        raise HTTPException(status_code=503, detail={"code": "PROVIDER_UNAVAILABLE", "message": "The configured market provider is unavailable."}) from exc

    asset_class = "CRYPTO" if is_crypto else ("METALS" if raw.startswith(("XAU", "XAG")) else "FOREX")
    provider = str(source or "DIRECT_VERIFIED").split(":", 1)[0].upper()[:40]
    provider_symbol = str(cfg.get("binance_symbol") or raw)
    display_name = str(cfg.get("name") or (f"{raw[:-4]} / Tether" if is_crypto else f"{raw[:3]} / {raw[3:]}"))
    row = db.query(MarketSymbolRegistry).filter_by(provider=provider, provider_symbol=provider_symbol).first()
    if row:
        row.symbol = raw
        row.display_name = display_name
        row.asset_class = asset_class
        row.aliases = [raw, raw[: -4] if is_crypto else f"{raw[:3]}/{raw[3:]}", display_name]
        row.tv_symbol = f"BINANCE:{raw}" if is_crypto else f"FX:{raw}"
        row.enabled = True
        row.last_verified_at = datetime.datetime.utcnow()
        row.updated_at = datetime.datetime.utcnow()
    else:
        db.add(MarketSymbolRegistry(
            symbol=raw,
            display_name=display_name,
            asset_class=asset_class,
            provider=provider,
            provider_symbol=provider_symbol,
            aliases=[raw, raw[:-4] if is_crypto else f"{raw[:3]}/{raw[3:]}", display_name],
            tv_symbol=f"BINANCE:{raw}" if is_crypto else f"FX:{raw}",
            enabled=True,
            last_verified_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow(),
        ))
    db.commit()
    return {"success": True, "cached": False, "symbol": resolve_market_symbol(raw, db), "provider": source}


@market_router.get("/api/v1/markets/{symbol}/timeframes")
def get_market_timeframes(symbol: str, db: Session = Depends(get_db)):
    item = _market_row(db, symbol)
    if not item:
        raise HTTPException(status_code=404, detail={"code": "SYMBOL_NOT_FOUND", "message": "No configured provider supports this symbol."})
    return {"symbol": item["symbol"], "timeframes": _allowed_timeframes(item)}


@market_router.get("/api/v1/markets/{symbol}")
def get_market_details(symbol: str, db: Session = Depends(get_db)):
    item = _market_row(db, symbol)
    if not item:
        raise HTTPException(status_code=404, detail={"code": "SYMBOL_NOT_FOUND", "message": "No configured provider supports this symbol."})
    try:
        price, source, timestamp = market_data_engine.get_verified_price(item["symbol"])
        freshness = check_data_freshness(item["symbol"], timestamp, "M1")
        usable_source = not any(flag in str(source).upper() for flag in ("DEMO", "SYNTHETIC", "UNAVAILABLE"))
        market_open, _ = is_market_open(item["symbol"])
        verified = bool(price and price > 0 and freshness.get("fresh") and usable_source and market_open)
        state = "LIVE" if verified else ("DELAYED" if price and price > 0 else "UNAVAILABLE")
    except Exception:
        logger.exception("Market detail quote failed for %s", item["symbol"])
        price, source, timestamp, freshness, state = 0.0, "UNAVAILABLE", None, {}, "UNAVAILABLE"
    item.update({
        "provider": source,
        "status": state,
        "verified": state == "LIVE",
        "price": price if state == "LIVE" else None,
        "quote_timestamp": timestamp.isoformat() if hasattr(timestamp, "isoformat") else timestamp,
        "age_minutes": freshness.get("age_minutes"),
        "timeframes": _allowed_timeframes(item),
    })
    return item


def _watchlist_items(db: Session, watchlist: UserWatchlist) -> List[Dict[str, Any]]:
    items = db.query(UserWatchlistItem).filter(
        UserWatchlistItem.watchlist_id == watchlist.id
    ).order_by(UserWatchlistItem.created_at.desc()).all()
    by_symbol = {item["symbol"]: item for item in market_catalog(db, limit=2000)}
    return [by_symbol[symbol] for symbol in (row.symbol for row in items) if symbol in by_symbol]


def _favorite_list(db: Session, user_id: int, create: bool = False) -> Optional[UserWatchlist]:
    favorite = db.query(UserWatchlist).filter_by(user_id=user_id, name="Favorites").first()
    if favorite or not create:
        return favorite
    from taikry.saas.entitlement_service import get_user_entitlement
    limits = get_user_entitlement(db, user_id).get("quotas", {})
    count = db.query(UserWatchlist).filter_by(user_id=user_id).count()
    if count >= int(limits.get("max_watchlists", 0) or 0):
        raise HTTPException(status_code=403, detail="Your plan has reached its watchlist limit.")
    favorite = UserWatchlist(user_id=user_id, name="Favorites")
    db.add(favorite)
    db.commit()
    db.refresh(favorite)
    return favorite


@market_router.get("/api/v1/me/market-favorites")
def get_market_favorites(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    favorite = _favorite_list(db, user.id)
    return {"symbols": _watchlist_items(db, favorite) if favorite else []}


@market_router.post("/api/v1/me/market-favorites/{symbol}")
def add_market_favorite(symbol: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _market_row(db, symbol)
    if not item:
        raise HTTPException(status_code=404, detail={"code": "SYMBOL_NOT_FOUND"})
    favorite = _favorite_list(db, user.id, create=True)
    exists = db.query(UserWatchlistItem).filter_by(watchlist_id=favorite.id, symbol=item["symbol"]).first()
    if not exists:
        db.add(UserWatchlistItem(watchlist_id=favorite.id, symbol=item["symbol"]))
        db.commit()
    return {"success": True, "symbol": item["symbol"]}


@market_router.delete("/api/v1/me/market-favorites/{symbol}")
def remove_market_favorite(symbol: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    normalized = "".join(char for char in str(symbol).upper() if char.isalnum())
    favorite = _favorite_list(db, user.id)
    if favorite:
        db.query(UserWatchlistItem).filter_by(watchlist_id=favorite.id, symbol=normalized).delete()
        db.commit()
    return {"success": True, "symbol": normalized}


@market_router.get("/api/v1/me/watchlists")
def get_my_watchlists(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lists = db.query(UserWatchlist).filter_by(user_id=user.id).order_by(UserWatchlist.created_at.asc()).all()
    return {"watchlists": [{"id": row.id, "name": row.name, "symbols": _watchlist_items(db, row)} for row in lists]}


@market_router.post("/api/v1/me/watchlists", status_code=status.HTTP_201_CREATED)
def create_my_watchlist(payload: WatchlistCreateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    name = " ".join(payload.name.split())
    if name.casefold() == "favorites":
        raise HTTPException(status_code=400, detail="Favorites is a reserved watchlist name.")
    from taikry.saas.entitlement_service import get_user_entitlement
    max_lists = int(get_user_entitlement(db, user.id).get("quotas", {}).get("max_watchlists", 0) or 0)
    if db.query(UserWatchlist).filter_by(user_id=user.id).count() >= max_lists:
        raise HTTPException(status_code=403, detail="Your plan has reached its watchlist limit.")
    existing = db.query(UserWatchlist).filter_by(user_id=user.id, name=name).first()
    if existing:
        raise HTTPException(status_code=409, detail="A watchlist with this name already exists.")
    row = UserWatchlist(user_id=user.id, name=name)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "name": row.name, "symbols": []}


@market_router.post("/api/v1/me/watchlists/{watchlist_id}/symbols")
def add_watchlist_symbol(
    watchlist_id: int,
    payload: WatchlistSymbolRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    watchlist = db.query(UserWatchlist).filter_by(id=watchlist_id, user_id=user.id).first()
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found.")
    item = _market_row(db, payload.symbol)
    if not item:
        raise HTTPException(status_code=404, detail={"code": "SYMBOL_NOT_FOUND"})
    exists = db.query(UserWatchlistItem).filter_by(watchlist_id=watchlist.id, symbol=item["symbol"]).first()
    if not exists:
        db.add(UserWatchlistItem(watchlist_id=watchlist.id, symbol=item["symbol"]))
        db.commit()
    return {"success": True, "watchlist_id": watchlist.id, "symbol": item["symbol"]}


@market_router.delete("/api/v1/me/watchlists/{watchlist_id}/symbols/{symbol}")
def remove_watchlist_symbol(
    watchlist_id: int,
    symbol: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    watchlist = db.query(UserWatchlist).filter_by(id=watchlist_id, user_id=user.id).first()
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found.")
    normalized = "".join(char for char in str(symbol).upper() if char.isalnum())
    db.query(UserWatchlistItem).filter_by(watchlist_id=watchlist.id, symbol=normalized).delete()
    db.commit()
    return {"success": True}


@market_router.get("/api/v1/me/recent-analysis")
def get_my_recent_analysis(
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.query(UserRecentAnalysis).filter_by(user_id=user.id).order_by(
        UserRecentAnalysis.created_at.desc()
    ).limit(limit).all()
    return {"items": [{
        "symbol": row.symbol,
        "timeframe": row.timeframe,
        "mode": row.mode,
        "profile": row.profile,
        "created_at": row.created_at.isoformat(),
    } for row in rows]}


def _set_job(job_id: str, *, status_value: Optional[str] = None, stage: Optional[str] = None,
             result: Optional[Dict[str, Any]] = None, error_code: Optional[str] = None) -> None:
    with _job_update_lock:
        db = SessionLocal()
        try:
            job = db.query(MarketAnalysisJob).filter_by(id=job_id).first()
            if not job:
                return
            if status_value:
                job.status = status_value
            if stage:
                job.stage = stage
            if result is not None:
                job.result = _json_safe(result)
            if error_code is not None:
                job.error_code = error_code
            job.updated_at = datetime.datetime.utcnow()
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Could not update market analysis job %s", job_id)
        finally:
            db.close()


def _json_safe(value: Any) -> Any:
    """Convert provider, NumPy, and Pydantic values into portable JSON values."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump())
    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except Exception:
            pass
    return str(value)


def _run_quick_analysis(symbol: str, timeframe: str) -> Dict[str, Any]:
    candles = market_data_engine.get_candles(symbol, timeframe, limit=240)
    validation = validate_dataframe(candles, min_bars=50)
    if not validation.get("valid"):
        raise ValueError("INSUFFICIENT_DATA")
    last_timestamp = candles.iloc[-1].get("timestamp")
    freshness = check_data_freshness(symbol, last_timestamp, timeframe)
    source = str(candles.iloc[-1].get("source") or "UNKNOWN")
    if not freshness.get("fresh") or any(flag in source.upper() for flag in ("DEMO", "SYNTHETIC", "UNAVAILABLE")):
        raise ValueError("DATA_STALE")
    metrics = extract_technical_summary(compute_technical_indicators(candles))
    if not metrics:
        raise ValueError("INSUFFICIENT_DATA")
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "mode": "QUICK",
        "status": "ANALYSIS_ONLY",
        "data_status": "DELAYED" if freshness.get("status") == "WEEKEND_CLOSED" else "LIVE",
        "provider": source,
        "last_market_update": last_timestamp.isoformat() if hasattr(last_timestamp, "isoformat") else str(last_timestamp),
        "analysis_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "metrics": metrics,
        "message_en": "Technical snapshot completed. This is analysis, not an automatic trade signal.",
        "message_kh": "ការវិភាគសូចនាករបច្ចេកទេសបានបញ្ចប់។ នេះជាព័ត៌មានវិភាគ មិនមែនជាសញ្ញាបញ្ជាទិញស្វ័យប្រវត្តិទេ។",
    }


def _run_analysis_job(job_id: str, symbol: str, timeframe: str, mode: str, profile: str) -> None:
    try:
        _set_job(job_id, status_value="RUNNING", stage="VALIDATING_SYMBOL")
        if mode == "QUICK":
            _set_job(job_id, stage="FETCHING_MARKET_DATA")
            result = _run_quick_analysis(symbol, timeframe)
        elif mode == "STANDARD":
            market_open, _ = is_market_open(symbol)
            if not market_open:
                raise ValueError("MARKET_CLOSED")
            _set_job(job_id, stage="RUNNING_MULTI_TIMEFRAME_ANALYSIS")
            from taikry.agents.consensus_engine import ai_consensus_engine
            timeframes = list(TIMEFRAME_PROFILES[profile])
            if timeframe not in timeframes:
                timeframes.insert(0, timeframe)
            trade_style = "SWING" if profile == "SWING" else "INTRADAY"

            def progress_callback(stage: str, _statuses: Dict[str, Any]) -> None:
                _set_job(job_id, stage=stage)

            result = ai_consensus_engine.analyze_symbol(
                symbol,
                preferred_llm="auto",
                force_refresh=True,
                trade_style=trade_style,
                progress_callback=progress_callback,
                primary_timeframe=timeframe,
                requested_timeframes=timeframes,
            )
            result["mode"] = "STANDARD"
            result["profile"] = profile
            result["requested_timeframe"] = timeframe
            result["analysis_timeframes"] = timeframes
            result["telegram_dispatched"] = False
        else:
            market_open, _ = is_market_open(symbol)
            if not market_open:
                raise ValueError("MARKET_CLOSED")
            _set_job(job_id, stage="RUNNING_DEEP_ANALYSIS")
            from taikry.agents.orchestration_layer import multi_agent_orchestrator
            trace = multi_agent_orchestrator.run_deep_analysis(
                symbol=symbol,
                account_equity=INITIAL_PAPER_BALANCE,
                force_fresh=True,
            )
            result = trace.model_dump()
            result.update({
                "mode": "DEEP",
                "profile": profile,
                "requested_timeframe": timeframe,
                "analysis_timeframes": ["M5", "M15", "H1", "H4"],
                "profile_note_en": "Deep analysis uses the engine's validated M5/M15/H1/H4 workflow.",
                "profile_note_kh": "Deep Analysis ប្រើ workflow ដែលមានស្រាប់លើ M5/M15/H1/H4។",
                "telegram_dispatched": False,
            })
        _set_job(job_id, status_value="COMPLETED", stage="COMPLETED", result=result)
    except ValueError as exc:
        code = str(exc) if str(exc) in {"DATA_STALE", "INSUFFICIENT_DATA", "MARKET_CLOSED"} else "ANALYSIS_FAILED"
        _set_job(job_id, status_value="FAILED", stage=code, error_code=code)
    except Exception:
        logger.exception("Market analysis failed for job %s", job_id)
        _set_job(job_id, status_value="FAILED", stage="FAILED", error_code="ANALYSIS_FAILED")
    finally:
        _analysis_slots.release()


@market_router.post("/api/v1/analysis", status_code=status.HTTP_202_ACCEPTED)
def create_market_analysis_job(
    payload: MarketAnalysisRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    market = _market_row(db, payload.symbol)
    if not market:
        raise HTTPException(status_code=404, detail={"code": "SYMBOL_NOT_FOUND", "message": "Choose a provider-supported symbol from Market Explorer."})
    if payload.timeframe not in _allowed_timeframes(market):
        raise HTTPException(status_code=400, detail={"code": "TIMEFRAME_UNSUPPORTED"})
    now = datetime.datetime.utcnow()
    if not payload.force_fresh:
        recent_job = db.query(MarketAnalysisJob).filter(
            MarketAnalysisJob.user_id == user.id,
            MarketAnalysisJob.symbol == market["symbol"],
            MarketAnalysisJob.timeframe == payload.timeframe,
            MarketAnalysisJob.mode == payload.mode,
            MarketAnalysisJob.profile == payload.profile,
            MarketAnalysisJob.created_at >= now - datetime.timedelta(seconds=45),
            MarketAnalysisJob.status.in_(["QUEUED", "RUNNING", "COMPLETED"]),
        ).order_by(MarketAnalysisJob.created_at.desc()).first()
        if recent_job:
            return {"analysis_id": recent_job.id, "status": recent_job.status, "poll_url": f"/api/v1/analysis/{recent_job.id}", "cached": True}
    if not _analysis_slots.acquire(blocking=False):
        raise HTTPException(status_code=503, detail={"code": "ANALYSIS_QUEUE_BUSY", "message": "Analysis capacity is busy. Try again shortly."})
    quota_type = "deep_analysis" if payload.mode == "DEEP" else "standard_scan"
    from taikry.saas.entitlement_service import check_and_consume_quota
    try:
        allowed, reason, _ = check_and_consume_quota(db, user.id, quota_type, symbol=market["symbol"])
    except Exception:
        _analysis_slots.release()
        raise
    if not allowed:
        _analysis_slots.release()
        raise HTTPException(status_code=403, detail={"code": "RATE_LIMITED", "message": reason})

    job_id = str(uuid.uuid4())
    job = MarketAnalysisJob(
        id=job_id,
        user_id=user.id,
        symbol=market["symbol"],
        timeframe=payload.timeframe,
        mode=payload.mode,
        profile=payload.profile,
        status="QUEUED",
        stage="QUEUED",
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    db.add(UserRecentAnalysis(
        user_id=user.id,
        symbol=market["symbol"],
        timeframe=payload.timeframe,
        mode=payload.mode,
        profile=payload.profile,
        created_at=now,
    ))
    try:
        db.commit()
        _analysis_executor.submit(
            _run_analysis_job, job_id, market["symbol"], payload.timeframe, payload.mode, payload.profile
        )
    except Exception as exc:
        _analysis_slots.release()
        db.rollback()
        failed_job = db.query(MarketAnalysisJob).filter_by(id=job_id, user_id=user.id).first()
        if failed_job:
            failed_job.status = "FAILED"
            failed_job.stage = "ANALYSIS_QUEUE_BUSY"
            failed_job.error_code = "ANALYSIS_QUEUE_BUSY"
            db.commit()
        raise HTTPException(status_code=503, detail={"code": "ANALYSIS_QUEUE_BUSY"}) from exc
    return {"analysis_id": job_id, "status": "QUEUED", "poll_url": f"/api/v1/analysis/{job_id}"}


@market_router.get("/api/v1/analysis/{analysis_id}")
def get_market_analysis_job(
    analysis_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = db.query(MarketAnalysisJob).filter_by(id=analysis_id, user_id=user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Analysis job not found.")
    return {
        "analysis_id": job.id,
        "symbol": job.symbol,
        "timeframe": job.timeframe,
        "mode": job.mode,
        "profile": job.profile,
        "status": job.status,
        "stage": job.stage,
        "error_code": job.error_code,
        "result": job.result,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }
