# 24/7 AI Trading Signal & Market Analysis Platform

An institutional-grade, autonomous 24/7 AI Agent pipeline designed to analyze real-time market data across **Commodities (Gold XAUUSD, Silver)**, **Crypto (BTC, ETH, SOL)**, and **Forex (EURUSD, GBPUSD, USDJPY)**, generating actionable high-conviction trading signals directly dispatched to your **Make.com Webhook**.

---

## 🏗 System Architecture

```mermaid
flowchart TD
    subgraph Market Feeds [Real-Time Market Feeds]
        A1[Gold XAUUSD & Silver]
        A2[Crypto: BTC, ETH, SOL]
        A3[Forex: EURUSD, GBPUSD, USDJPY]
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
        D[ai_agent.py]
        D -->|Primary| E1[Google Gemini / OpenAI LLM]
        D -->|Automatic Failover| E2[Algorithmic Quant Strategy]
    end

    subgraph Dispatcher [24/7 Autonomous Engine]
        F[engine_247.py]
        F --> G{Confidence >= 70% & Cooldown Passed?}
        G -->|Yes| H[Make.com Webhook]
    end

    subgraph Make.com Scenario [Make.com 24/7 Workflow]
        H --> I[Filter: Action in BUY/SELL]
        I --> J1[Telegram Channel / Bot Alert]
        I --> J2[Discord Webhook Notification]
        I --> J3[Google Sheets / Notion Trade Journal]
        I --> J4[MT4 / MT5 Webhook Execution]
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
| [`market_data.py`](file:///d:/test%20post%20webhook/market_data.py) | Real-time candle fetcher (Crypto, Commodities, Forex) with zero auth required. |
| [`indicators.py`](file:///d:/test%20post%20webhook/indicators.py) | EMA, RSI, MACD, ATR, Bollinger Bands, and market summary extractor. |
| [`ai_agent.py`](file:///d:/test%20post%20webhook/ai_agent.py) | AI Reasoning engine (Gemini LLM + quantitative algorithmic fallback). |
| [`engine_247.py`](file:///d:/test%20post%20webhook/engine_247.py) | 24/7 continuous autonomous scanner and webhook dispatcher. |
| [`make_scenario_template.json`](file:///d:/test%20post%20webhook/make_scenario_template.json) | Blueprint for building your Make.com scenario modules. |
| [`auto_run_webhook.py`](file:///d:/test%20post%20webhook/auto_run_webhook.py) | Standalone webhook stress tester & auto-runner. |
| [`.vscode/launch.json`](file:///d:/test%20post%20webhook/.vscode/launch.json) | 1-click VS Code run/debug configurations. |

---

## 🚀 Quick Start

### 1. Run a Single Test Scan
Scans all 8 symbols, evaluates with AI, and prints current market status:
```powershell
python engine_247.py --once
```

### 2. Start the Continuous 24/7 Engine
Runs indefinitely, scanning the market on interval and dispatching signals whenever high-confidence setups occur:
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
MIN_CONFIDENCE_THRESHOLD=70
COOLDOWN_MINUTES=15
SCAN_INTERVAL_SECONDS=30
DEFAULT_TIMEFRAME=M15
```

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
