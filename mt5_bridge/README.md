# ZYROX AI — Windows Exness MT5 Bridge Guide

**Tagline:** *Read the Market. Own Your Edge.*  
**Bridge Mode:** READ-ONLY Outbound Market Data Stream  

---

## 📌 Architecture Overview

Because ZYROX AI is hosted 24/7 on Render (Linux containers) while MetaTrader 5 runs on your Windows machine, the bridge uses a **secure outbound HTTPS architecture**:

```
+------------------------------------------+
|  Your Windows PC (Home / Office / VPS)   |
|  1. Exness MetaTrader 5 Terminal Running  |
|  2. exness_mt5_bridge.py (Read-Only)      |
+------------------------------------------+
                    │
                    │ Outbound Authenticated HTTPS POST
                    │ (Header: X-Bridge-Token + HMAC Signature)
                    ▼
+------------------------------------------+
|  ZYROX AI Cloud (Render / FastAPI)        |
|  1. /api/v1/bridge/market-data           |
|  2. Real-Time Price Engine               |
|  3. Multi-Agent Signal Engine            |
|  4. Live Terminal Dashboard              |
+------------------------------------------+
```

> [!NOTE]
> **Strict Read-Only Protection:**
> The bridge client contains **zero trade-execution methods**. It only reads tick prices (Bid, Ask, Spread) and OHLC candles from your MT5 terminal and streams them to your dashboard. Your trading balance is 100% safe.

---

## 🚀 How to Run the Bridge (Windows)

### Step 1: Open Exness MT5
1. Launch your **MetaTrader 5** terminal and log in to your Exness account (Demo or Real).
2. Ensure **Algo Trading / DLL Imports** is enabled in MT5:
   `Tools -> Options -> Expert Advisors -> Allow automated trading`.

### Step 2: Install Dependencies
Open PowerShell or Command Prompt on your Windows machine:
```powershell
pip install MetaTrader5 requests
```

### Step 3: Run the Bridge
Execute the bridge pointing to your live Render application:

```powershell
python mt5_bridge/exness_mt5_bridge.py --backend-url https://taikry-ai-trading.onrender.com --token zyrox_mt5_bridge_secure_token_change_me
```

*(For local development testing)*:
```powershell
python mt5_bridge/exness_mt5_bridge.py --backend-url http://localhost:8000 --token zyrox_mt5_bridge_secure_token_change_me
```

### Step 4: Verify Connection in Dashboard
Once launched, your ZYROX AI dashboard will immediately display:
- **Broker Status:** `● EXNESS MT5 CONNECTED` (Green)
- **Active Symbol:** `XAUUSDm` (or `XAUUSD`)
- **Real-Time Spread:** Live Exness broker spread in points
- **Source Badge:** `FEED: EXNESS_MT5 (VERIFIED BROKER)`
