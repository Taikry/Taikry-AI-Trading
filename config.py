import os

# Make.com Webhook URL (Configured via environment variables only)
MAKE_WEBHOOK_URL = os.getenv("MAKE_WEBHOOK_URL", "")

# Telegram Direct Alerts Configuration (Optional: send directly to Telegram without 3rd party limits)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1004341134868")
TELEGRAM_WEBAPP_URL = os.getenv("TELEGRAM_WEBAPP_URL", "")

# AI Engine Provider: "auto", "claude", "openai", "gemini", "deepseek", "manus", "ensemble", or "rule_based"
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

def get_configured_llms() -> list:
    """Returns a list of LLM providers that currently have active API keys."""
    active = []
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

# Signal Quality Controls
MIN_CONFIDENCE_THRESHOLD = int(os.getenv("MIN_CONFIDENCE_THRESHOLD", "80"))
COOLDOWN_MINUTES = int(os.getenv("COOLDOWN_MINUTES", "15"))
SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "30"))

# Comprehensive Multi-Asset Watchlist (Crypto, Commodities, Forex)
WATCHLIST = [
    # Commodities / Metals
    {
        "symbol": "XAUUSD",
        "ticker": "GC=F",
        "name": "Gold / US Dollar",
        "category": "Commodities",
        "decimals": 2
    },
    {
        "symbol": "XAGUSD",
        "ticker": "SI=F",
        "name": "Silver / US Dollar",
        "category": "Commodities",
        "decimals": 3
    },
    # Crypto
    {
        "symbol": "BTCUSD",
        "ticker": "BTC-USD",
        "name": "Bitcoin",
        "category": "Crypto",
        "decimals": 2
    },
    {
        "symbol": "ETHUSD",
        "ticker": "ETH-USD",
        "name": "Ethereum",
        "category": "Crypto",
        "decimals": 2
    },
    {
        "symbol": "SOLUSD",
        "ticker": "SOL-USD",
        "name": "Solana",
        "category": "Crypto",
        "decimals": 2
    },
    # Major Forex Pairs
    {
        "symbol": "EURUSD",
        "ticker": "EURUSD=X",
        "name": "Euro / US Dollar",
        "category": "Forex",
        "decimals": 5
    },
    {
        "symbol": "GBPUSD",
        "ticker": "GBPUSD=X",
        "name": "British Pound / US Dollar",
        "category": "Forex",
        "decimals": 5
    },
    {
        "symbol": "USDJPY",
        "ticker": "USDJPY=X",
        "name": "US Dollar / Japanese Yen",
        "category": "Forex",
        "decimals": 3
    }
]

# Timeframes to monitor
DEFAULT_TIMEFRAME = os.getenv("DEFAULT_TIMEFRAME", "M15")
AVAILABLE_TIMEFRAMES = ["M5", "M15", "H1", "D1"]
