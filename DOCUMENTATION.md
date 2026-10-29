# TAIKRY AI MARKET INTELLIGENCE PRO — System Manual & Deployment Guide

Welcome to the institutional operational manual for **TAIKRY AI MARKET INTELLIGENCE PRO**.

---

## 🏗 High-Level System Architecture

```mermaid
flowchart TD
    subgraph Data Feeds [External Market Data Providers]
        D1[Gold XAUUSD & Silver]
        D2[Forex: EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD]
        D3[Crypto: BTC, ETH, SOL, XRP]
        D4[Configured Economic Calendar Feed (when available)]
    end

    subgraph Validator [Data Freshness & Integrity]
        V1[Weekend Closure Filter]
        V2[Monotonic Timestamp & Gap Detection]
    end

    subgraph Four Agents [Specialized AI Reasoning Agents]
        A1[Agent 1: Quantitative Technical Analyst]
        A2[Agent 2: ICT / SMC Price Action Analyst]
        A3[Agent 3: Macroeconomic & USD Analyst]
        A4[Agent 4: Independent Risk Validator - CRO]
    end

    subgraph Consensus [Deterministic Consensus Engine]
        C1[Independent Synthesis & Dissent Preservation]
        C2[Configured R:R and Risk Gate]
        C3[Bilingual Translator: English & Khmer]
    end

    subgraph Execution & Monitoring [API, Paper Trading & Monitoring]
        E1[FastAPI REST API]
        E2[Simulated Paper Trading Ledger]
        E3[Walk-Forward Backtesting Engine]
        E4[Make.com Automation - Scenarios S01 to S07]
        E5[Telegram Bot Alerts & Commands]
        E6[Black & Gold Trading Dashboard]
    end

    Data Feeds --> Validator
    Validator --> Four Agents
    Four Agents --> Consensus
    Consensus --> Execution & Monitoring
```

---

## 🚀 Quick Start Guide

### 1. Local Run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run unit & integration test suite
python -m pytest tests/ -v

# 3. Launch FastAPI backend & Trading Dashboard
uvicorn taikry.api.app:app --host 0.0.0.0 --port 8000 --reload
```

Navigate to `http://localhost:8000/dashboard` to view the Black-and-Gold Trading Dashboard.

### 2. Docker & Docker Compose

```bash
# Copy template and fill secrets
cp .env.example .env

# Build and start all services (FastAPI, PostgreSQL, Redis)
docker-compose up -d --build

# View logs
docker-compose logs -f taikry-app
```

---

## 🤖 Telegram Bot Configuration

1. Create a bot using [@BotFather](https://t.me/BotFather) on Telegram and copy your API Token.

2. Obtain your Chat ID by messaging [@userinfobot](https://t.me/userinfobot).

3. Set your environment variables in `.env`:

   ```env
   TELEGRAM_BOT_TOKEN=<your-token-from-BotFather>
   TELEGRAM_CHAT_ID=<your-target-chat-or-channel-id>
   TELEGRAM_ADMIN_IDS=<your-admin-user-ids>
   ```

4. Test delivery directly via Python:

   ```bash
   python -c "from taikry.notifications.telegram_service import telegram_service; print(telegram_service.send_message('Test from TAIKRY PRO'))"
   ```

---

## ⚡ Make.com Integration (Scenarios S01–S07)

See [the Make integration guide](make_scenarios/MAKE_INTEGRATION_GUIDE.md) for scenario templates. Configure your public HTTPS host and credentials before activating them:

- **S01:** 15-Minute Market Report Dispatcher
- **S02:** Critical Validated Alert Dispatcher
- **S03:** Economic News & Event Relevance Engine
- **S04:** Interactive Telegram Commands
- **S05:** Paper Trading Execution Engine
- **S06:** Backtest Scorecard Runner
- **S07:** System Health Poller & Daily Summary

---

## 🌐 Sample Bilingual Intelligence Reports

> **Illustration only:** The prices, indicator values, provider names, event descriptions, scores, and trade levels below are fictional formatting examples. They are not current market data and do not show that a live feed produced an approved trade. When required inputs are unavailable or stale, the application should report that state and avoid an actionable approval.

### English Report Sample

```text
TAIKRY AI MARKET INTELLIGENCE PRO

Time: 2026-10-27 04:10:00 UTC | 2026-10-27 11:10:00 +07 (Cambodia Time)
Symbol: XAUUSD
Verified Price: 2738.50 (yahoo_finance)
Market Bias: BULLISH
Setup Status: APPROVE

D1 / H4 / H1:
D1: BULLISH | H4: BULLISH | H1: BULLISH

M15 / M5:
M15: BULLISH | RSI: 54.20 | ATR: 4.80

Agent 1 (Technical Analyst):
Bias: BULLISH (85%) | Confluence of bullish HTF alignment with active M15 momentum. Score: 85/100.
Evidence: H4 Macro Trend is BULLISH; M15 Execution Trend is BULLISH; RSI 14 at 54.2 demonstrates healthy momentum.

Agent 2 (ICT/SMC Analyst):
Bias: BULLISH | Zone: DISCOUNT (38.5%)
Structure: ICT Bullish structure confirmed via liquidity sweep/FVG confluence.

Agent 3 (Macro Analyst):
Bias: BULLISH | USD Index: 104.10 (BEARISH_USD)
Events: Federal Reserve Policy Stance; US CPI Inflation Tracking

Agent 4 (Independent Risk Validator):
Decision: APPROVE
Reasons: Setup validated: Direction LONG, verified R:R 1:2.2 >= 1:2.0, Risk capped at 0.5% equity ($500.0).

Dissenting Opinions:
None. Confluence achieved across active models.

Entry:
2738.50

Stop Loss:
2731.30

Take Profit:
TP1: 2754.34 | TP2: 2762.26

Risk-to-Reward:
1:2.2

Invalidation:
Drop below M15 support / EMA50 (2732.10) or SL 2731.30

Final Decision:
BUY BIAS
```

### Khmer Report Sample

```text
📊 TAIKRY AI MARKET INTELLIGENCE PRO (របាយការណ៍ទីផ្សារ)

⏱ ពេលវេលា: 2026-10-27 04:10:00 UTC (UTC) | 2026-10-27 11:10:00 +07 (ម៉ោងនៅកម្ពុជា)
🪙 គូរូបិយវត្ថុ/ទ្រព្យសកម្ម: XAUUSD
💵 តម្លៃផ្ទៀងផ្ទាត់ជាក់ស្តែង: 2738.50 (ប្រភព: yahoo_finance)
📈 ទំនោរទិសដៅទីផ្សារ: ទំនោរឡើង (BULLISH)
🚦 ស្ថានភាពរៀបចំការជួញដូរ: បានអនុម័ត (APPROVED)

━━━━━━━━━━━━━━━━━━━━
🔭 ការវិភាគក្របខ័ណ្ឌពេលវេលាធំ (D1 / H4 / H1):
D1: BULLISH | H4: BULLISH | H1: BULLISH

⚡ ការវិភាគរៀបចំចំណុចចូល (M15 / M5):
M15 Trend: BULLISH | RSI 14: 54.20 | ATR: 4.80

━━━━━━━━━━━━━━━━━━━━
🤖 ភ្នាក់ងារទី ១ (បច្ចេកទេស Quantitative):
ទំនោរ: BULLISH (85%) | កម្លាំងសន្ទុះមានតុល្យភាពល្អ និងមានការគាំទ្រពី EMA 20/50

🏛 ភ្នាក់ងារទី ២ (រចនាសម្ព័ន្ធស្ថាប័ន ICT / SMC):
ទំនោរ: BULLISH | តំបន់: DISCOUNT (38.5%) | តម្លៃបាន Sweep Sell-Side Liquidity និងបង្កើត Bullish FVG

🌐 ភ្នាក់ងារទី ៣ (ម៉ាក្រូសេដ្ឋកិច្ច និងមូលដ្ឋានគ្រឹះ):
ទំនោរ: BULLISH | DXY: 104.10 (BEARISH_USD) | សម្ពាធធ្លាក់ចុះនៃប្រាក់ដុល្លារផ្តល់អំណោយផលដល់មាស

🛡 ភ្នាក់ងារទី ៤ (ការវាយតម្លៃ និងគ្រប់គ្រងហានិភ័យ):
ការសម្រេច: APPROVE | ហេតុផល: អនុបាត R:R 1:2.2 ឆ្លើយតបតាមស្តង់ដារយ៉ាងហោចណាស់ 1:2.0, ហានិភ័យកំណត់ត្រឹម 0.5% ($500.0)

━━━━━━━━━━━━━━━━━━━━
🎯 កម្រិតតម្លៃចូល (Entry): 2738.50
🛑 កម្រិតកាត់ខាត (Stop Loss): 2731.30
🎯 កម្រិតយកប្រាក់ចំណេញទី ១ (TP 1): 2754.34
🚀 កម្រិតយកប្រាក់ចំណេញទី ២ (TP 2): 2762.26
⚖️ អនុបាតហានិភ័យធៀបផលចំណេញ: 1:2.2

⚠️ លក្ខខណ្ឌលុបចោលសុពលភាព (Invalidation):
តម្លៃធ្លាក់ចុះបំបែកកម្រិតគាំទ្រ M15 / EMA50 (2732.10) ឬប៉ះ SL 2731.30

🏁 សេចក្តីសម្រេចចុងក្រោយ: ទំនោរទិញ (BUY BIAS)
```

---

## 🛠 Troubleshooting Guide

| Issue | Root Cause | Solution |
| :--- | :--- | :--- |
| `Market data is stale` | Provider feed is delayed, disconnected, or the market is closed | Check the configured provider and its market calendar. Stale quotes must not be treated as current. |
| `Insufficient Risk-to-Reward` | Calculated setup does not meet the configured minimum | Check `MIN_RISK_REWARD_RATIO`; the default minimum is 2.0. A setup below the configured floor is rejected. |
| `Make Webhook timeout` | Make scenario inactive | Verify the Make scenario switch is turned **ON** in your dashboard. |
| `Port 8000 already in use` | Another process is bound to port 8000 | Specify a different port: `uvicorn taikry.api.app:app --port 8080`. |
