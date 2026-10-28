"""
TAIKRY AI MARKET INTELLIGENCE PRO - Configuration Module
"""
import os
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

# System Info
APP_NAME = "TAIKRY AI MARKET INTELLIGENCE PRO"
APP_VERSION = "2.0.0"
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
SECRET_KEY = os.getenv("SECRET_KEY", "taikry-super-secret-key-change-in-production")
API_KEY_HEADER = os.getenv("API_KEY_HEADER", "X-TAIKRY-API-KEY")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "taikry_admin_access_token_2026")

# Database & Cache
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./taikry_market.db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Timezone
SYSTEM_TIMEZONE = "UTC"
LOCAL_TIMEZONE = os.getenv("LOCAL_TIMEZONE", "Asia/Phnom_Penh")  # Cambodia Time (UTC+7)

# AI Providers: "auto", "claude", "openai", "gemini", "deepseek", "manus", "ensemble", "hybrid", "quant"
AI_PROVIDER = os.getenv("AI_PROVIDER", "auto").lower()

# Real AI LLM API Keys & Endpoints (Frontier Models: Claude 3.7/3.5, OpenAI o3/o1/GPT-4o, Gemini 2.5, DeepSeek V3/R1)
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", os.getenv("ANTHROPIC_API_KEY", ""))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
MANUS_API_KEY = os.getenv("MANUS_API_KEY", "")
MANUS_API_URL = os.getenv("MANUS_API_URL", "https://api.manus.ai/v1")

def get_configured_llms() -> List[str]:
    """Returns a list of LLM providers that currently have active API keys."""
    active: List[str] = []
    if GROQ_API_KEY:
        active.append("groq")
    if OPENROUTER_API_KEY:
        active.append("openrouter")
    if CLAUDE_API_KEY:
        active.append("claude")
    if OPENAI_API_KEY:
        active.append("openai")
    if GEMINI_API_KEY:
        active.append("gemini")
    if DEEPSEEK_API_KEY:
        active.append("deepseek")
    if MANUS_API_KEY:
        active.append("manus")
    return active

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1004341134868")
TELEGRAM_ADMIN_IDS: List[int] = [
    int(x.strip()) for x in os.getenv("TELEGRAM_ADMIN_IDS", "-1004341134868").split(",") if x.strip()
]
TELEGRAM_WEBAPP_URL = os.getenv("TELEGRAM_WEBAPP_URL", "")
VIP_TELEGRAM_CHAT_ID = os.getenv("VIP_TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID or "-1004341134868")
BAKONG_KHQR_ACCOUNT = os.getenv("BAKONG_KHQR_ACCOUNT", "taikry_financial@aclb")
USDT_TRC20_WALLET = os.getenv("USDT_TRC20_WALLET", "TYD6xNf3bQeXG8sWpZ29jL4v1k8mR7q9Aa")
TELEGRAM_ADMIN_USERNAME = os.getenv("TELEGRAM_ADMIN_USERNAME", "taikry_admin")

# Make.com Webhooks (Configured via environment variables only)
MAKE_WEBHOOK_URL = os.getenv("MAKE_WEBHOOK_URL", "")
MAKE_CRITICAL_ALERT_WEBHOOK = os.getenv("MAKE_CRITICAL_ALERT_WEBHOOK", MAKE_WEBHOOK_URL)
MAKE_PAPER_TRADE_WEBHOOK = os.getenv("MAKE_PAPER_TRADE_WEBHOOK", MAKE_WEBHOOK_URL)

# Windows MT5 Bridge Configuration
MT5_BRIDGE_TOKEN = os.getenv("MT5_BRIDGE_TOKEN", "")
MT5_BRIDGE_ENABLED = os.getenv("MT5_BRIDGE_ENABLED", "true").lower() in ("true", "1", "yes")
MT5_BRIDGE_STALE_SECONDS = int(os.getenv("MT5_BRIDGE_STALE_SECONDS", "30"))
MAX_DAILY_XAUUSD_SIGNALS = int(os.getenv("MAX_DAILY_XAUUSD_SIGNALS", "4"))
DEFAULT_STRATEGY_VERSION = os.getenv("DEFAULT_STRATEGY_VERSION", "ZYROX-SMC-V2.1")

# 24/7 Monitoring Engine Parameters
MONITORING_INTERVAL_MINUTES = int(os.getenv("MONITORING_INTERVAL_MINUTES", "15"))
COOLDOWN_MINUTES = int(os.getenv("COOLDOWN_MINUTES", "15"))
MIN_CONFIDENCE_THRESHOLD = int(os.getenv("MIN_CONFIDENCE_THRESHOLD", "80"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
BACKOFF_BASE_SECONDS = float(os.getenv("BACKOFF_BASE_SECONDS", "2.0"))

# Research & Paper Trading Risk Limits (Configurable limits, no guarantees)
INITIAL_PAPER_BALANCE = float(os.getenv("INITIAL_PAPER_BALANCE", "100000.0"))
RISK_PER_TRADE_PERCENT = float(os.getenv("RISK_PER_TRADE_PERCENT", "0.5"))  # 0.5% equity
MIN_RISK_REWARD_RATIO = float(os.getenv("MIN_RISK_REWARD_RATIO", "2.0"))   # 1:2.0 minimum
MAX_DAILY_LOSS_PERCENT = float(os.getenv("MAX_DAILY_LOSS_PERCENT", "2.5")) # 2.5% daily drawdown stop
MAX_SIMULTANEOUS_POSITIONS = int(os.getenv("MAX_SIMULTANEOUS_POSITIONS", "3"))
SLIPPAGE_PIPS = float(os.getenv("SLIPPAGE_PIPS", "1.0"))
COMMISSION_PER_LOT = float(os.getenv("COMMISSION_PER_LOT", "7.0")) # $7 per standard round-turn lot

# Market Watchlist Specification
# Priority 1: XAUUSD (Gold)
PRIMARY_SYMBOL = "XAUUSD"

# TradingView Reference Instrument Alignment Mode for Gold:
# "SPOT" (Default): References TradingView Spot Gold (OANDA:XAUUSD / TVC:GOLD).
#   Ingests physical LBMA-backed gold troy ounce spot feed (PAXG-USD / XAUT-USD).
# "FUTURES": References TradingView CME COMEX Gold Futures (COMEX:GC1!).
#   Ingests CME COMEX Gold Futures (GC=F).
XAUUSD_PRICE_REFERENCE = os.getenv("XAUUSD_PRICE_REFERENCE", "SPOT").upper()

WATCHLIST: List[Dict[str, Any]] = [
    # --- Priority 1: Gold / Precious Metals ---
    {
        "symbol": "XAUUSD",
        "ticker_yahoo": "PAXG-USD" if XAUUSD_PRICE_REFERENCE == "SPOT" else "GC=F",
        "ticker_yahoo_spot": "PAXG-USD",
        "ticker_yahoo_futures": "GC=F",
        "tv_reference_symbol": "OANDA:XAUUSD" if XAUUSD_PRICE_REFERENCE == "SPOT" else "COMEX:GC1!",
        "tv_symbol_spot": "OANDA:XAUUSD",
        "tv_symbol_futures": "COMEX:GC1!",
        "quote_type": "SPOT_MID" if XAUUSD_PRICE_REFERENCE == "SPOT" else "FUTURES_LAST",
        "provider_display": "OANDA (Spot)" if XAUUSD_PRICE_REFERENCE == "SPOT" else "CME COMEX (GC=F)",
        "binance_symbol": "PAXGUSDT",
        "name": "Gold / US Dollar",
        "category": "Commodities",
        "priority": 1,
        "decimals": 2,
        "pip_value": 0.10,
        "lot_size": 100,  # 1 lot = 100 oz Gold
        "spread_estimate": 0.25
    },
    {
        "symbol": "XAGUSD",
        "ticker_yahoo": "SI=F",
        "binance_symbol": None,
        "name": "Silver / US Dollar",
        "category": "Commodities",
        "priority": 1,
        "decimals": 3,
        "pip_value": 0.01,
        "lot_size": 5000,
        "spread_estimate": 0.03
    },
    # --- Priority 2: Major & Cross Forex Pairs ---
    {
        "symbol": "EURUSD",
        "ticker_yahoo": "EURUSD=X",
        "binance_symbol": "EURUSDT",
        "name": "Euro / US Dollar",
        "category": "Forex",
        "priority": 2,
        "decimals": 5,
        "pip_value": 0.0001,
        "lot_size": 100000,
        "spread_estimate": 0.00015
    },
    {
        "symbol": "GBPUSD",
        "ticker_yahoo": "GBPUSD=X",
        "binance_symbol": "GBPUSDT",
        "name": "British Pound / US Dollar",
        "category": "Forex",
        "priority": 2,
        "decimals": 5,
        "pip_value": 0.0001,
        "lot_size": 100000,
        "spread_estimate": 0.0002
    },
    {
        "symbol": "USDJPY",
        "ticker_yahoo": "USDJPY=X",
        "binance_symbol": None,
        "name": "US Dollar / Japanese Yen",
        "category": "Forex",
        "priority": 2,
        "decimals": 3,
        "pip_value": 0.01,
        "lot_size": 100000,
        "spread_estimate": 0.015
    },
    {
        "symbol": "AUDUSD",
        "ticker_yahoo": "AUDUSD=X",
        "binance_symbol": "AUDUSDT",
        "name": "Australian Dollar / US Dollar",
        "category": "Forex",
        "priority": 2,
        "decimals": 5,
        "pip_value": 0.0001,
        "lot_size": 100000,
        "spread_estimate": 0.00018
    },
    {
        "symbol": "NZDUSD",
        "ticker_yahoo": "NZDUSD=X",
        "binance_symbol": None,
        "name": "New Zealand Dollar / US Dollar",
        "category": "Forex",
        "priority": 2,
        "decimals": 5,
        "pip_value": 0.0001,
        "lot_size": 100000,
        "spread_estimate": 0.0002
    },
    {
        "symbol": "USDCAD",
        "ticker_yahoo": "CAD=X",
        "binance_symbol": None,
        "name": "US Dollar / Canadian Dollar",
        "category": "Forex",
        "priority": 2,
        "decimals": 5,
        "pip_value": 0.0001,
        "lot_size": 100000,
        "spread_estimate": 0.0002
    },
    {
        "symbol": "USDCHF",
        "ticker_yahoo": "CHF=X",
        "binance_symbol": None,
        "name": "US Dollar / Swiss Franc",
        "category": "Forex",
        "priority": 2,
        "decimals": 5,
        "pip_value": 0.0001,
        "lot_size": 100000,
        "spread_estimate": 0.0002
    },
    {
        "symbol": "EURJPY",
        "ticker_yahoo": "EURJPY=X",
        "binance_symbol": None,
        "name": "Euro / Japanese Yen",
        "category": "Forex",
        "priority": 2,
        "decimals": 3,
        "pip_value": 0.01,
        "lot_size": 100000,
        "spread_estimate": 0.02
    },
    {
        "symbol": "GBPJPY",
        "ticker_yahoo": "GBPJPY=X",
        "binance_symbol": None,
        "name": "British Pound / Japanese Yen",
        "category": "Forex",
        "priority": 2,
        "decimals": 3,
        "pip_value": 0.01,
        "lot_size": 100000,
        "spread_estimate": 0.025
    },
    # --- Priority 3: Major Liquid Cryptocurrencies ---
    {
        "symbol": "BTCUSDT",
        "ticker_yahoo": "BTC-USD",
        "binance_symbol": "BTCUSDT",
        "name": "Bitcoin / Tether",
        "category": "Crypto",
        "priority": 3,
        "decimals": 2,
        "pip_value": 1.0,
        "lot_size": 1,
        "spread_estimate": 1.5
    },
    {
        "symbol": "ETHUSDT",
        "ticker_yahoo": "ETH-USD",
        "binance_symbol": "ETHUSDT",
        "name": "Ethereum / Tether",
        "category": "Crypto",
        "priority": 3,
        "decimals": 2,
        "pip_value": 0.1,
        "lot_size": 1,
        "spread_estimate": 0.2
    },
    {
        "symbol": "BNBUSDT",
        "ticker_yahoo": "BNB-USD",
        "binance_symbol": "BNBUSDT",
        "name": "BNB / Tether",
        "category": "Crypto",
        "priority": 3,
        "decimals": 2,
        "pip_value": 0.1,
        "lot_size": 1,
        "spread_estimate": 0.1
    },
    {
        "symbol": "SOLUSDT",
        "ticker_yahoo": "SOL-USD",
        "binance_symbol": "SOLUSDT",
        "name": "Solana / Tether",
        "category": "Crypto",
        "priority": 3,
        "decimals": 2,
        "pip_value": 0.01,
        "lot_size": 1,
        "spread_estimate": 0.05
    },
    {
        "symbol": "XRPUSDT",
        "ticker_yahoo": "XRP-USD",
        "binance_symbol": "XRPUSDT",
        "name": "Ripple / Tether",
        "category": "Crypto",
        "priority": 3,
        "decimals": 4,
        "pip_value": 0.0001,
        "lot_size": 1,
        "spread_estimate": 0.0005
    },
    {
        "symbol": "DOGEUSDT",
        "ticker_yahoo": "DOGE-USD",
        "binance_symbol": "DOGEUSDT",
        "name": "Dogecoin / Tether",
        "category": "Crypto",
        "priority": 3,
        "decimals": 4,
        "pip_value": 0.0001,
        "lot_size": 100,
        "spread_estimate": 0.0002
    },
    {
        "symbol": "ADAUSDT",
        "ticker_yahoo": "ADA-USD",
        "binance_symbol": "ADAUSDT",
        "name": "Cardano / Tether",
        "category": "Crypto",
        "priority": 3,
        "decimals": 4,
        "pip_value": 0.0001,
        "lot_size": 10,
        "spread_estimate": 0.0003
    },
    {
        "symbol": "AVAXUSDT",
        "ticker_yahoo": "AVAX-USD",
        "binance_symbol": "AVAXUSDT",
        "name": "Avalanche / Tether",
        "category": "Crypto",
        "priority": 3,
        "decimals": 2,
        "pip_value": 0.01,
        "lot_size": 1,
        "spread_estimate": 0.02
    },
    {
        "symbol": "LINKUSDT",
        "ticker_yahoo": "LINK-USD",
        "binance_symbol": "LINKUSDT",
        "name": "Chainlink / Tether",
        "category": "Crypto",
        "priority": 3,
        "decimals": 2,
        "pip_value": 0.01,
        "lot_size": 1,
        "spread_estimate": 0.02
    },
    {
        "symbol": "SUIUSDT",
        "ticker_yahoo": "SUI20947-USD",
        "binance_symbol": "SUIUSDT",
        "name": "Sui / Tether",
        "category": "Crypto",
        "priority": 3,
        "decimals": 4,
        "pip_value": 0.0001,
        "lot_size": 10,
        "spread_estimate": 0.0005
    }
]

# Enrich all WATCHLIST entries with normalized TradingView and provider metadata
for _w in WATCHLIST:
    if "tv_reference_symbol" not in _w:
        if _w["symbol"] == "XAGUSD":
            _w["tv_reference_symbol"] = "OANDA:XAGUSD"
            _w["quote_type"] = "SPOT_MID"
            _w["provider_display"] = "OANDA (Silver)"
        elif _w.get("category") == "Crypto" or "USDT" in _w["symbol"]:
            _w["tv_reference_symbol"] = f"BINANCE:{_w['symbol']}"
            _w["quote_type"] = "CRYPTO_SPOT"
            _w["provider_display"] = "Binance"
        elif _w.get("category") == "Forex":
            _w["tv_reference_symbol"] = f"FX:{_w['symbol']}"
            _w["quote_type"] = "SPOT_MID"
            _w["provider_display"] = f"FX ({_w['symbol']})"
        else:
            _w["tv_reference_symbol"] = f"OANDA:{_w['symbol']}"
            _w["quote_type"] = "SPOT_MID"
            _w["provider_display"] = "OANDA"

TIMEFRAMES = ["D1", "H4", "H1", "M30", "M15", "M5"]
PRIMARY_ANALYSIS_TIMEFRAMES = ["D1", "H4", "H1", "M15", "M5"]

def get_symbol_config(symbol: str) -> Dict[str, Any]:
    norm = symbol.upper().replace("/", "").replace("-", "")
    for item in WATCHLIST:
        if item["symbol"] == norm:
            return item
    # Fallback default
    return {
        "symbol": norm,
        "ticker_yahoo": f"{norm}=X",
        "binance_symbol": norm if "USDT" in norm else None,
        "tv_reference_symbol": f"BINANCE:{norm}" if "USDT" in norm else f"FX:{norm}",
        "quote_type": "CRYPTO_SPOT" if "USDT" in norm else "SPOT_MID",
        "provider_display": "Binance" if "USDT" in norm else "FX",
        "name": norm,
        "category": "Forex",
        "priority": 2,
        "decimals": 4,
        "pip_value": 0.0001,
        "lot_size": 100000,
        "spread_estimate": 0.0002
    }
