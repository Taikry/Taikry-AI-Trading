# AI Trading Signal & Market Analysis Platform

An AI-assisted market analysis platform for **Commodities (Gold XAUUSD, Silver)**, **Crypto (BTC, ETH, SOL)**, and **Forex (EURUSD, GBPUSD, USDJPY)**. Background monitoring runs only while the service is active; hosting plan, provider uptime, and data freshness affect availability.

---

## 🏗 System Architecture

```mermaid
flowchart TD
    subgraph Market Feeds [External Market Feeds]
        A1[Gold & Forex: Yahoo Finance fallback or configured MT5 bridge]
        A2[Crypto: Binance public market feed]
        A3[Other symbols: provider availability varies]
    end

    subgraph Indicator Engine [Quantitative Engine]
        B[market_data.py & indicators.py]
        B --> C1[EMA 9 / 21 / 50 / 200]
        B --> C2[RSI 14 Momentum]
        B --> C3[MACD 12/26/9 Expansion]
        B --> C4[ATR Volatility SL/TP]
        B --> C5[Swing High / Low Support & Resistance]
    end

    subgraph AI Analyst [AI Agent Reasoning Engine]
        D[Eight directional analysts plus data, risk & candidate reviewers]
        D --> D1[Technical, SMC, Macro, Order Flow & Fractal]
        D --> D2[Regime, Quantitative & ML Forecast]
        D --> D3[Fresh-data gate, strategy concepts, portfolio & execution checks]
        D -->|Optional synthesis only when explicitly selected and configured| E1[Cloud LLM provider]
        D -->|Default| E2[Deterministic multi-agent consensus]
    end

    subgraph Dispatcher [Background Scanner — runs while the process is available]
        F[engine_247.py / FastAPI monitor]
        F --> G{Approved plan, fresh data, score 80–95, cooldown passed?}
        G -->|Yes| H[Configured Telegram + Make.com]
    end

    subgraph Make.com Scenario [Optional Make.com Workflow]
        H --> I[Filter: Action in BUY/SELL]
        I --> J1[Telegram Channel / Bot Alert]
        I --> J2[Discord Webhook Notification]
        I --> J3[Google Sheets / Notion Trade Journal]
        I --> J4[Manual MT4 / MT5 Ticket — no broker order]
    end

    Market Feeds --> Indicator Engine
    Indicator Engine --> AI Analyst
    AI Analyst --> Dispatcher
```

---

## 📁 File Structure

| File | Purpose |
| :--- | :--- |
| [`config.py`](file:///d:/test%20post%20webhook/config.py) | Asset watchlist, webhook target, timeframe, and confidence thresholds. |
| `taikry/data/providers.py` | Binance public crypto feed, Yahoo Finance fallback, and authenticated MT5 bridge for broker quotes/candles. Availability and freshness vary by symbol and provider. |
| [`indicators.py`](file:///d:/test%20post%20webhook/indicators.py) | EMA, RSI, MACD, ATR, Bollinger Bands, and market summary extractor. |
| [`ai_agent.py`](file:///d:/test%20post%20webhook/ai_agent.py) | AI Reasoning engine (Gemini LLM + quantitative algorithmic fallback). |
| [`engine_247.py`](file:///d:/test%20post%20webhook/engine_247.py) | Continuous scanner while the process and host are running; uptime depends on deployment. |
| [`make_scenario_template.json`](file:///d:/test%20post%20webhook/make_scenario_template.json) | Blueprint for building your Make.com scenario modules. |
| [`auto_run_webhook.py`](file:///d:/test%20post%20webhook/auto_run_webhook.py) | Standalone webhook stress tester & auto-runner. |
| [`.vscode/launch.json`](file:///d:/test%20post%20webhook/.vscode/launch.json) | 1-click VS Code run/debug configurations. |

---

## 🚀 Quick Start

The supported web application is the FastAPI service under `taikry/`. Without an available and fresh market-data feed, analysis returns **NO TRADE**; demo candles are never substituted. Crypto uses Binance public market data where supported. Gold/forex Yahoo data is a fallback and may be delayed; broker-grade XAUUSD data requires the authenticated Windows MT5 bridge. Eight local signal analysts vote on the same scan snapshot: technical, ICT/SMC, macro, order flow, fractal MTF, regime, quantitative research, and ML forecast. Data quality, independent risk, concept, portfolio, execution, and counter-analysis agents run at their relevant stages. Debate and self-training run on demand or after outcomes resolve. Cloud LLM synthesis remains optional and must be selected and configured separately.

### 1. Run a Single Test Scan
Scans the configured watchlist, evaluates each open market, and sends the single best approved plan to configured destinations:
```powershell
python engine_247.py --once
```

### 2. Start the Continuous Scanner
Runs until stopped, scanning at the selected interval while the process and host remain available:
```powershell
python engine_247.py --interval 30
```

---

## 🤖 Make.com Scenario Configuration

Your Make.com Webhook URL (configured in .env):
`https://hook.us2.make.com/YOUR_MAKE_WEBHOOK_ID`

### Modules to Connect in Make.com:

1. **Module 1: Custom Webhook**
   - Receives JSON payload from `engine_247.py`.

2. **Module 2: Filter**
   - Condition: `action` In `["BUY", "SELL"]` AND `confidence` >= `70`.

3. **Module 3: Router**
   - **Branch A (Telegram Bot):** `Send a Text Message or Reply`
   - **Branch B (Discord):** `Create a Message`
   - **Branch C (Google Sheets):** `Add a Row` (for automated PnL logging)

### Telegram Alert Format Template (HTML Mode):
```html
🚨 <b>AI TRADING SIGNAL: {{1.action}} {{1.symbol}}</b>

📊 <b>Asset:</b> {{1.name}} ({{1.category}})
⏱ <b>Timeframe:</b> {{1.timeframe}}
🎯 <b>Confidence:</b> {{1.confidence}}%

💵 <b>Entry Price:</b> {{1.entry_price}}
🛑 <b>Stop Loss:</b> {{1.stop_loss}}
🎯 <b>Take Profit 1:</b> {{1.take_profit_1}}
🚀 <b>Take Profit 2:</b> {{1.take_profit_2}}
⚖️ <b>Risk/Reward:</b> {{1.risk_reward_ratio}}

📈 <b>Metrics:</b> RSI: {{1.metrics.rsi}} | Trend: {{1.metrics.trend}} | ATR: {{1.metrics.atr}}
💡 <b>AI Rationale:</b>
<i>{{1.rationale}}</i>

⏰ <code>{{1.timestamp}}</code>
```

---

## ⚙️ Environment Variables (Optional)

Create a `.env` file in the root folder to customize settings:

```env
# Optional LLM Key (if omitted, the high-precision quant engine runs automatically)
GEMINI_API_KEY=your_gemini_api_key_here

# Make.com Webhook URL
MAKE_WEBHOOK_URL=https://hook.us2.make.com/YOUR_MAKE_WEBHOOK_ID

# Engine Parameters
MIN_CONFIDENCE_THRESHOLD=80
COOLDOWN_MINUTES=15
MONITORING_INTERVAL_MINUTES=15
DEFAULT_TIMEFRAME=M15
```

The FastAPI service starts this monitor when `AUTO_START_MONITORING=true`. Each cycle uses fresh, non-synthetic data and the validated entry, stop, and target levels from consensus. Non-gold setups use the validated multi-asset Telegram report; XAUUSD Telegram delivery also requires a fresh MT5 quote and an available daily quota. Approved plans are sent to the configured critical Make webhook. The monitor sends at most one best setup per cycle and never places broker orders.

---

## 🔄 Running 24/7 in Background / Production

### Option A: PM2 Process Manager (Node.js)
```bash
npm install -g pm2
pm2 start engine_247.py --name "ai-trading-signals" --interpreter python
pm2 save
pm2 startup
```

### Option B: Windows Background Task / PowerShell
```powershell
Start-Process -NoNewWindow python -ArgumentList "engine_247.py --interval 30"
```

### Option C: Linux / VPS Systemd Service
```ini
[Unit]
Description=24/7 AI Trading Signal Engine
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/project
ExecStart=/usr/bin/python3 engine_247.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```
---

## 🔬 ZYROX AI — 11-Agent Deep Research & Pre-News Engine

Production-grade multi-agent research and pre-news quantitative analysis system for **Gold (XAUUSD)**, **Forex (EURUSD, GBPUSD, USDJPY)**, and **Crypto (BTCUSDT, ETHUSDT, SOLUSDT)** with bilingual English & Khmer (`ភាសាខ្មែរ`) reporting.

### 🤖 11 Specialized Logical Research Agents

| Agent | Responsibility | Guarantee / Rule |
| :--- | :--- | :--- |
| **1. News & Source Verification** | Real-time RSS feeds (Investing.com, MarketWatch) | Preserves publication timestamps & direct URLs |
| **2. Economic Calendar** | FairEconomy/ForexFactory feed parsing | Event time, forecast, previous, and actual metrics |
| **3. Macro & Central Bank** | DXY index strength & Fed/ECB monetary stance | Correlates macro bias with target asset |
| **4. Forex & USD Impact** | Currency sensitivities across majors | USD correlation matrix & yield divergence |
| **5. Gold/XAUUSD Specialist** | Bullion safe-haven & real yield analysis | Yahoo PAXG-USD/Gold verified spot pricing |
| **6. Crypto Specialist** | Spot trends on BTC/ETH/SOL | Derivs (funding/OI/liq) marked unverified if feed absent |
| **7. Technical & ICT/SMC** | EMA (20/50/200), RSI, ATR, Order Blocks, FVGs | **Strictly deterministic code** — zero LLM hallucination |
| **8. Quantitative Scenarios** | Bullish, Bearish, and Base Case setups | Enforces strict Risk/Reward floor (min 1:2.0) |
| **9. Independent Critic** | Trapped retail, late-buyer squeeze, sentiment extremes | Contrarian safety checks against FOMO |
| **10. Risk Guardian** | Capital preservation, pre-news lockout, spread check | Mandatory no-trade lockout inside high-impact events |
| **11. Final Synthesizer** | Dual-language report generation (Sections A–K) | Native Khmer (`ភាសាខ្មែរ`) & institutional English |

### ⏱ Pre-News Research Windows

Automated contextual analysis aligned to Cambodia Local Time (`UTC+7`):
- `60_30_MIN`: Background research, macro regime, institutional sentiment.
- `15_5_MIN`: Quantitative scenario planning and spread risk preparation.
- `1_2_MIN`: Pre-release lockout verification and spread blowout warning.
- `AT_RELEASE`: Captures verified official actual figures once published.
- `1_5_MIN_POST`: Initial impulse reaction and deviation vs. consensus analysis.

### 📑 Structured Output Format (Sections A–K)

Every pre-news intelligence brief returns:
- **Section A:** Executive Summary (Bilingual English / Khmer)
- **Section B:** Verified Current Price & Data Timestamp
- **Section C:** Upcoming News Event, Source, Forecast, Previous, Actual
- **Section D:** Macro Impact & Affected Asset Classes
- **Section E:** Technical Structure & ICT/SMC Levels (OB, FVG, Swing H/L)
- **Section F:** Bullish Scenario (Trigger, TP1/TP2, SL, Invalidation)
- **Section G:** Bearish Scenario (Trigger, TP1/TP2, SL, Invalidation)
- **Section H:** Base Case / No-Trade Condition (Capital Protection)
- **Section I:** Volatility & Spread Blowout Warning
- **Section J:** Verified Sources & Data Freshness Status
- **Section K:** Uncertainties & Missing Inputs (Integrity Transparency)

### 🔌 REST API Endpoints

```bash
# 1. Trigger Deep Pre-News Research Brief
POST /api/v1/research/pre-news
Content-Type: application/json
{
  "symbol": "XAUUSD",
  "timeframe": "M15",
  "force_refresh": false
}

# 2. Inspect Authenticated Model Catalog & Routing Health
GET /api/v1/router/catalog
```

### 💰 Cost Controls & Multi-Gateway Failover

- **Budget Cap:** Hard $15.00/month maximum spend with request token accounting.
- **Failover Routing:** Automatic sub-1.4s failover between AnyRouter, Groq Cloud (`openai/gpt-oss-120b`, `qwen/qwen3.8-27b`), and OpenRouter Free Tier (`nvidia/nemotron-3.5-lightning:free`).
- **Data Protection:** Numerical calculations are strictly deterministic. LLMs never invent prices, calendar figures, technical indicators, or sources.
