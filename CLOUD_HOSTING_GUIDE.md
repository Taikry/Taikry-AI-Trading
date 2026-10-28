# 🚀 24/7 Free Cloud Hosting & Telegram Automated Setup Guide

## ការណែនាំអំពីការដាក់ឱ្យដំណើរការលើ Cloud ដោយឥតគិតថ្លៃ (100% Free) 24 ម៉ោងលើ 24 ម៉ោង

Follow this comprehensive guide to host your **TAIKRY AI MARKET INTELLIGENCE PRO** platform online in the cloud **100% FREE** without keeping your computer turned on.

Once deployed:

1. 🌐 **Live Web Dashboard:** Access your institutional terminal from anywhere on your smartphone or PC via public HTTPS link (`https://your-app.onrender.com/dashboard/`).
2. 📱 **Telegram Mini App:** Open the live interactive terminal directly inside Telegram.
3. ⚡ **24/7 Autonomous Signals:** Continuous scanning for XAUUSD, Forex, and Crypto with real-time Telegram channel & Make.com webhook dispatching.

---

## 🌟 Top 100% Free Hosting Providers Comparison

| Provider | Free Tier Details | Best For | Sleep Behavior |
| :--- | :--- | :--- | :--- |
| **Render.com** (Recommended) | 750 free hours/month, Free Web Service with HTTPS & custom domain | Web Dashboard + Telegram Mini App + 24/7 Scanner | Sleeps after 15m inactivity *(prevented with free UptimeRobot ping)* |
| **Koyeb.com** | 1 Free Nano Instance (512MB RAM, 24/7) | Continuous background engine + Web Service | **Never sleeps** on free tier |
| **Hugging Face Spaces** | 16 GB RAM, 2 vCPU Docker container (100% Free) | High performance AI & heavy workloads | Never sleeps on public spaces |
| **Oracle Cloud** | 4 Ampere ARM CPUs, 24 GB RAM, 200 GB SSD | Heavy enterprise self-hosted 24/7 VPS | **Always Free Forever** |

---

## 🥇 Method 1: Render.com (Recommended — 100% Free)

> [!IMPORTANT]
> **Key Rule for Free Hosting on Render:** Always select **"Web Service"** (NOT "Background Worker"). Render's Web Service is **100% Free**, whereas Background Workers require a paid tier. Our container runs both the Web Terminal and the 24/7 Scanner together inside the Web Service!

### Step 1: Push Code to GitHub

1. If you haven't already, initialize git and push this project folder to your GitHub account (public or private):

   ```bash
   git init
   git add .
   git commit -m "Deploy Taikry AI Market Intelligence Pro"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
   git push -u origin main
   ```

### Step 2: Create Free Web Service on Render

1. Sign up or log in at [Render.com](https://render.com/) using your GitHub account.
2. On your dashboard, click **"New +"** in the top right &rarr; Select **"Web Service"**.
3. Select **"Build and deploy from a Git repository"** &rarr; Click **"Next"**.
4. Connect and choose your repository `YOUR_REPO_NAME`.
5. Fill in the deployment details:
   * **Name:** `taikry-ai-market` (or any name you prefer)
   * **Region:** Singapore (or Frankfurt / Oregon — Singapore is lowest latency for Asia)
   * **Branch:** `main`
   * **Runtime:** `Docker` (Render will automatically detect the [Dockerfile](file:///d:/test%20post%20webhook/Dockerfile))
   * **Instance Type:** `Free` ($0/month)

### Step 3: Add Your Environment Variables

Scroll down to the **"Environment Variables"** section and click **"Add Environment Variable"** for each:

| Key | Example Value | Description |
| :--- | :--- | :--- |
| `AUTO_START_MONITORING` | `true` | Starts 24/7 autonomous scanning engine upon container boot |
| `TELEGRAM_BOT_TOKEN` | `7123456789:AAH...` | Your Telegram Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | `@your_channel` or `-10012345678` | Your Telegram Channel ID or Group ID |
| `MAKE_WEBHOOK_URL` | `https://hook.us2.make.com/...` | Your Make.com webhook URL |
| `GROQ_API_KEY` | `gsk_...` | Groq LPU API key for ultra-fast Khmer AI analysis |
| `GEMINI_API_KEY` | `AIzaSy...` | Google Gemini 3 Flash multimodal vision key |
| `OPENROUTER_API_KEY` | `sk-or-...` | OpenRouter institutional fallback LLM key |

### Step 4: Click "Deploy Web Service"

1. Click the blue **"Create Web Service"** button.
2. Render will build the Docker container and deploy in ~2 minutes.
3. Once finished, you will see a green **"Live"** badge and your live public HTTPS link:

   ```text
   https://taikry-ai-market.onrender.com
   ```

4. Clicking this link immediately opens the **Institutional Web Dashboard**!

### Step 5: Keep It Awake 24/7 (Prevent Render Sleep — 100% Free)

Render's free tier spins down if no web requests are received for 15 minutes. To keep your market scanner running **24 hours a day, 7 days a week for $0**:

1. Go to [UptimeRobot.com](https://uptimerobot.com/) (or [Cron-job.org](https://cron-job.org/)) and create a free account.
2. Click **"Add New Monitor"**:
   * **Monitor Type:** `HTTP(s)`
   * **Friendly Name:** `Taikry AI Keep-Alive`
   * **URL (or IP):** `https://taikry-ai-market.onrender.com/ping`
   * **Monitoring Interval:** `Every 5 minutes` (or 10 minutes)
3. Click **"Create Monitor"**.
4. Now UptimeRobot automatically pings your service every 5 minutes, keeping your 24/7 market intelligence engine awake and running continuously without ever sleeping!

---

## 🥈 Method 2: Koyeb.com (100% Free Nano — Never Sleeps)

Koyeb offers a free nano container that **does not sleep**, making it an outstanding free choice:

1. Sign up at [Koyeb.com](https://www.koyeb.com/) using GitHub.
2. Click **"Create Service"** &rarr; Select **"GitHub"**.
3. Choose your repository.
4. Select **"Dockerfile"** as the builder.
5. In **Environment Variables**, add:
   * `PORT` = `8000`
   * `AUTO_START_MONITORING` = `true`
   * `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GROQ_API_KEY`, etc.
6. Click **"Deploy"**. Koyeb gives you an active public domain (e.g. `https://your-app.koyeb.app/dashboard/`) that stays online 24/7.

---

## 🥉 Method 3: Hugging Face Spaces (16GB RAM Docker — 100% Free)

1. Sign up at [HuggingFace.co](https://huggingface.co/).
2. Click **"New Space"** &rarr; Set Space SDK to **"Docker"** &rarr; Space Hardware to **"CPU Basic · 2 vCPU · 16 GB RAM · Free"**.
3. In **Settings** &rarr; **Variables and secrets**, add your API keys (`GROQ_API_KEY`, `TELEGRAM_BOT_TOKEN`, etc.).
4. Push this repository to your Space git repository:

   ```bash
   git remote add space https://huggingface.co/spaces/YOUR_USERNAME/SPACE_NAME
   git push space main
   ```

5. Hugging Face builds the Docker container and runs it 24/7 with zero sleeping.

---

## 📱 Connecting Your Cloud URL to Telegram Bot & Mini App

Once your cloud service is live with an HTTPS link (e.g. `https://taikry-ai-market.onrender.com`):

### 1. Add Telegram Mini App Menu Button

1. Open Telegram and search for [`@BotFather`](https://t.me/BotFather).
2. Send `/setmenubutton` &rarr; Select your bot.
3. Enter the Web App URL:

   ```text
   https://taikry-ai-market.onrender.com/dashboard/
   ```

4. Enter the button title: `📈 Trade Cockpit`
5. Now, any user who opens your bot will see a button at the bottom left that opens the live interactive dashboard right inside Telegram!

### 2. Verify 24/7 Channel Broadcasts

1. Ensure your bot is an **Admin** in your Telegram Channel or VIP Group.
2. In your cloud environment variables, make sure `TELEGRAM_CHAT_ID` matches your channel username (e.g. `@taikry_vip_signals`) or numeric ID (e.g. `-1001987654321`).
3. Check your Render or Koyeb logs; you will see:

   ```text
   [24/7 MONITOR] Completed cycle: XAUUSD, BTCUSDT, EURUSD...
   [TELEGRAM] Broadcasted signal with R:R and Khmer institutional breakdown
   ```

---

## 🛠️ Verification & Troubleshooting Checklist

* [ ] **Port Binding:** Our [Dockerfile](file:///d:/test%20post%20webhook/Dockerfile) uses `uvicorn taikry.api.app:app --host 0.0.0.0 --port ${PORT:-8000}`, automatically adapting to any port assigned by Render, Koyeb, or Cloud Run.
* [ ] **Root Domain Redirect:** Visiting `https://your-domain.com/` automatically redirects to `/dashboard/`.
* [ ] **Health & Ping Endpoints:**
  * Health check: `GET /health`
  * Keep-alive ping: `GET /ping`
* [ ] **Zero Inline Styles & Full Linter Compliance:** All HTML and CSS strictly adhere to modern web validation standards.
