# TAIKRY AI MARKET INTELLIGENCE PRO — Make.com Integration Guide

This guide details how to import, configure, test, and link all 7 Make.com automation scenarios with your Python backend.

---

## 🏗 Scenario Architecture Overview

| Scenario ID | Name | Trigger | Target Endpoints / Action |
| :--- | :--- | :--- | :--- |
| **S01** | `MARKET_REPORT_15M` | 15-Minute Scheduler | `POST /api/v1/analyze` -> Bilingual Telegram Dispatch |
| **S02** | `CRITICAL_MARKET_ALERTS` | Webhook (`YOUR_MAKE_WEBHOOK_ID`) | Instant High-Priority Alert (`setup_status == APPROVE`) |
| **S03** | `ECONOMIC_NEWS_ALERTS` | 1-Hour Scheduler | Calendar Ingestion -> `POST /api/v1/events/assess` -> Telegram |
| **S04** | `TELEGRAM_COMMANDS` | Telegram `/command` | Interactive Command Dispatcher (`/gold`, `/forex`, `/crypto`, etc.) |
| **S05** | `PAPER_TRADING_ENGINE` | Webhook from Python | `POST /api/v1/paper-trades/evaluate` -> Position Ledger Audit |
| **S06** | `BACKTEST_AND_SCORECARD` | Weekly / Manual | `POST /api/v1/backtests/run` -> Executive Performance Scorecard |
| **S07** | `SYSTEM_HEALTH_AND_DAILY_SUMMARY` | 5m Poller + Daily 22:00 | `GET /health` & `GET /api/v1/reports/daily` |

---

## 🚀 Step-by-Step Setup in Make.com

### 1. Webhook Setup (Scenario S02 & S05)

1. In Make.com, go to **Webhooks > Custom Webhook**.

2. Point your webhook URL:
   `https://hook.us2.make.com/YOUR_MAKE_WEBHOOK_ID`

3. Send a test ping from your terminal:

   ```powershell
   python test_webhook.py
   ```

4. Verify Make displays `Successfully determined data structure`.

### 2. Telegram Bot Connection

1. In Make.com, add the **Telegram Bot** module: `Send a Text Message or Reply`.
2. Enter your Telegram Bot Token from `@BotFather`.
3. Set `Chat ID` to your target channel or user ID.
4. Set `Parse Mode` to **HTML**.

### 3. Connecting to the Python Backend

When running Python locally on your machine or VPS:

- If hosted on a VPS: `http://YOUR_SERVER_IP:8000`
- If running locally behind Ngrok or Cloudflare Tunnel: `https://your-tunnel-url.com`
- Set Header:
  `X-TAIKRY-API-KEY: taikry_admin_access_token_2026`

---

## 📋 JSON Mapping Schema Reference

### Scenario S01 (15-Minute Report Payload)

- `{{3.report_english}}`: Complete institutional multi-timeframe analysis in English.
- `{{3.report_khmer}}`: Natural Khmer translation with exact preserved price levels.
- `{{3.verified_price}}`: Verified asset settlement price.
- `{{3.market_bias}}`: Directional classification (BULLISH, BEARISH, NEUTRAL, etc.).
- `{{3.setup_status}}`: APPROVE, REJECT, WAIT, or NO TRADE.

### Scenario S02 (Critical Alerts Payload)

```json
{
  "event": "VALIDATED_SIGNAL",
  "symbol": "XAUUSD",
  "direction": "BUY",
  "entry_price": 2735.50,
  "stop_loss": 2724.00,
  "take_profit_1": 2758.50,
  "take_profit_2": 2772.00,
  "risk_reward": "1:2.0",
  "timestamp": "2026-10-27T04:00:00Z"
}
```

---

## 🛡 Security Best Practices

- Keep your bot token and API keys in environment variables or Make Vault.
- Never commit active credentials into public version control.
- Live trading is strictly disabled. All executions remain in simulated paper mode.
