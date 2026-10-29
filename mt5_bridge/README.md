# ZYROX AI — Windows Exness MT5 Bridge Guide

**Tagline:** *Read the Market. Own Your Edge.*  
**Bridge Mode:** READ-ONLY Outbound Market Data Stream  

---

## 📌 Architecture Overview

Because the backend runs in a cloud service while MetaTrader 5 runs on your Windows machine, the bridge uses a **secure outbound HTTPS architecture**. Free hosting plans may sleep or pause, so they may not provide continuous monitoring:

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
> **Read-Only:**
> The bridge client contains no trade-execution methods. It reads tick prices (Bid, Ask, Spread) and OHLC candles and streams them to the backend. This bridge does not need MT5's Algo Trading permission; keep automated trading disabled unless another tool you use requires it.

---

## 🚀 How to Run the Bridge (Windows)

### Step 1: Open Exness MT5
1. Launch your **MetaTrader 5** terminal and log in to your Exness account (Demo or Real).
2. Keep **Algo Trading** disabled for this bridge. It only reads prices and candles; automated trading permissions are not required.

### Step 2: Install Dependencies
Open PowerShell or Command Prompt on your Windows machine:
```powershell
pip install MetaTrader5 requests
```

### Step 3: Run the Bridge
Set the same unique secret (at least 32 characters) as `MT5_BRIDGE_TOKEN` on the server and in your local environment. Replace the example host with your public HTTPS API host. The client rejects missing/default secrets and requires HTTPS for remote backends.

```powershell
$env:MT5_BRIDGE_TOKEN = "<your-unique-32-character-or-longer-secret>"
python mt5_bridge/exness_mt5_bridge.py --backend-url https://your-domain.example
```

*(For local development testing)*:
```powershell
$env:MT5_BRIDGE_TOKEN = "<your-unique-32-character-or-longer-secret>"
python mt5_bridge/exness_mt5_bridge.py --backend-url http://localhost:8000
```

### Step 4: Verify Connection in Dashboard
After the bridge has delivered a fresh bid/ask tick and the API accepts it, the dashboard reports the actual broker/server values, tick age, and feed source. A heartbeat alone shows the bridge as connected but does not count as a fresh quote. The bridge client and MT5 terminal must remain running on the Windows PC or VPS that has access to the broker account.
