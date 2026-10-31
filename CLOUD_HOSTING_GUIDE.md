# ☁️ Cloud Hosting & Telegram Setup Guide

## ការណែនាំអំពីការដាក់ឱ្យដំណើរការលើ Cloud

Use this guide to deploy **TAIKRY AI MARKET INTELLIGENCE PRO** as a free Render preview. The current Blueprint selects a Free web service and Free PostgreSQL database in Singapore. This is suitable for evaluation; the web service sleeps when idle and the database expires after 30 days. Do not rely on this configuration for continuous monitoring or durable production data.

Once deployed:

1. 🌐 **Live Web Dashboard:** Access your institutional terminal from anywhere on your smartphone or PC via public HTTPS link (`https://your-app.onrender.com/dashboard/`).
2. 📱 **Telegram Mini App:** Open the live interactive terminal directly inside Telegram.
3. ⚡ **Background Signals:** The monitor runs inside the single web instance. Keep it at one instance to avoid duplicate scans and alerts. Host restarts still interrupt a scan until the service starts again.

---

## Hosting Options

| Provider | Free Tier Details | Best For | Sleep / Storage |
| :--- | :--- | :--- | :--- |
| **Render.com** | Free web service and managed Postgres defined in `render.yaml` | Public preview and initial evaluation | Service sleeps after 15 idle minutes; free Postgres expires after 30 days |
| **Koyeb.com** | One free web instance | Small previews | Scales to zero after 1 hour; no persistent volume or worker on free instances |
| **Hugging Face Spaces** | Free CPU Space for demos | Model demos and prototypes | Sleeps after inactivity |
| **Paid VPS / always-on host** | Depends on provider and region | Continuous scanning with persistent storage | Configure uptime, backups, and database separately |

Free-plan limits change. Check the current [Render limits](https://render.com/docs/free), [Koyeb instance limits](https://www.koyeb.com/docs/reference/instances), and [Hugging Face Spaces behavior](https://huggingface.co/docs/hub/spaces-overview) before deployment.

Render free instances block outbound SMTP on ports 25, 465, and 587. Account verification and reset emails need a mail service reachable over HTTPS or an SMTP provider/port that your host permits.

---

## 🥇 Method 1: Render.com (free preview)

> [!IMPORTANT]
> The included Blueprint creates free services. The web app sleeps after 15 minutes without incoming traffic, and the free Postgres database expires after 30 days. The Free web filesystem is ephemeral. Check the current [Render Free limits](https://render.com/docs/free) before applying. Upgrade the web and database plans and configure backups before using it for production.

### Step 1: Publish the reviewed repository revision

1. Commit and push the reviewed project revision to the connected GitHub repository. Keep `.env` out of Git; only enter credentials in the Render dashboard.

### Step 2: Create a Web Service on Render

1. Sign in at [Render.com](https://render.com/) and choose **New → Blueprint**.
2. Connect the repository containing this `render.yaml` and select the reviewed branch. Confirm both resources show the Free plan before applying.
3. The Blueprint provisions one Singapore web service and a private managed PostgreSQL database. Render generates `SECRET_KEY` and connects `DATABASE_URL` to the database automatically.
4. Enter a unique `MT5_BRIDGE_TOKEN` (at least 32 characters), `SAAS_ADMIN_EMAIL`, and a strong `SAAS_ADMIN_PASSWORD` when prompted. Save the bridge token securely; configure the Windows bridge with the same value.

### Step 3: Configure real providers and integrations

Add only credentials for services you actually use. Never commit them to Git. The web app and API can start without optional integrations, but a working provider requires valid credentials and connectivity.

| Key | Example Value | Description |
| :--- | :--- | :--- |
| `MT5_BRIDGE_TOKEN` | Unique random value, 32+ characters | Shared secret between the cloud API and Windows MT5 bridge. The bridge is read-only; keep broker order execution disabled. |
| `SAAS_ADMIN_EMAIL` | Admin email | Creates the initial administrator if the managed database is new. |
| `SAAS_ADMIN_PASSWORD` | Strong unique password | Password for that initial administrator. |
| `GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, etc. | Provider-issued keys | Optional cloud LLM synthesis. These incur provider limits or charges and do not turn the Python analysts into separate LLM calls. |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | BotFather token and destination | Optional Telegram notification integration. |
| `MAKE_WEBHOOK_URL` | Private Make.com webhook URL | Optional automation integration. |

### Step 4: Click "Deploy Web Service"

1. Apply the Blueprint after reviewing the free-tier limits and required secrets.
2. Render builds the Docker image, provisions PostgreSQL, and deploys the service. Check build and runtime logs for startup or provider errors.
3. When healthy, open the assigned HTTPS link and append `/dashboard/`:

   ```text
   https://your-assigned-service.onrender.com/dashboard/
   ```

4. Open `/dashboard/` to view the dashboard. The root URL shows the landing page.

### Step 5: Connect real XAUUSD data

Crypto candles use the public Binance feed when available. Gold/forex can use Yahoo Finance fallback data; broker-grade XAUUSD candles and bid/ask quotes require the Windows MT5 bridge. Configure the bridge to post to the deployed HTTPS endpoint with the exact shared token, then confirm `/health` and `/api/v1/bridge/status` report the expected source and fresh timestamp. While the Free service sleeps, its in-process monitor pauses; it resumes when Render starts the app for a request. Without fresh required data, the signal engine returns **NO TRADE**. The four core agents are deterministic Python analysts; the optional LLM provider adds synthesis only when configured and selected.

---

## 🥈 Method 2: Koyeb.com (Free preview)

Koyeb's free instance is for previews. It scales to zero after one hour without traffic and cannot run as a worker or attach a persistent volume:

1. Sign up at [Koyeb.com](https://www.koyeb.com/) using GitHub.
2. Click **"Create Service"** &rarr; Select **"GitHub"**.
3. Choose your repository.
4. Select **"Dockerfile"** as the builder.
5. In **Environment Variables**, add:
   * `PORT` = `8000`
   * `AUTO_START_MONITORING` = `true`
   * `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GROQ_API_KEY`, etc.
6. Click **"Deploy"**. Use the service URL for a preview; do not rely on it for continuous background scanning.

---

## 🥉 Method 3: Hugging Face Spaces (Demo deployment)

1. Sign up at [HuggingFace.co](https://huggingface.co/).
2. Click **"New Space"** &rarr; Set Space SDK to **"Docker"** &rarr; choose available free CPU hardware.
3. In **Settings** &rarr; **Variables and secrets**, add your API keys (`GROQ_API_KEY`, `TELEGRAM_BOT_TOKEN`, etc.).
4. Push this repository to your Space git repository:

   ```bash
   git remote add space https://huggingface.co/spaces/YOUR_USERNAME/SPACE_NAME
   git push space main
   ```

5. Hugging Face builds the Docker container. Free Spaces can sleep after inactivity; use them for demos rather than continuous scanning.

---

## 📱 Connecting Your Cloud URL to Telegram Bot & Mini App

Once your cloud service is live with an HTTPS link (e.g. `https://zyroxaitrading.onrender.com`):

### 1. Add Telegram Mini App Menu Button

1. Open Telegram and search for [`@BotFather`](https://t.me/BotFather).
2. Send `/setmenubutton` &rarr; Select your bot.
3. Enter the Web App URL:

   ```text
   https://zyroxaitrading.onrender.com/dashboard/
   ```

4. Enter the button title: `📈 Trade Cockpit`
5. Now, any user who opens your bot will see a button at the bottom left that opens the live interactive dashboard right inside Telegram!

### 2. Verify Telegram Channel Broadcasts

1. Ensure your bot is an **Admin** in your Telegram Channel or VIP Group.
2. In your cloud environment variables, make sure `TELEGRAM_CHAT_ID` matches your channel username (e.g. `@taikry_vip_signals`) or numeric ID (e.g. `-1001987654321`).
3. Check your Render or Koyeb logs; you will see:

   ```text
   [MONITOR] Completed cycle: XAUUSD, BTCUSDT, EURUSD...
   [TELEGRAM] Broadcasted signal with R:R and Khmer institutional breakdown
   ```

---

## 🛠️ Verification & Troubleshooting Checklist

* [ ] **Port Binding:** Our [Dockerfile](file:///d:/test%20post%20webhook/Dockerfile) uses `uvicorn taikry.api.app:app --host 0.0.0.0 --port ${PORT:-8000}`, automatically adapting to any port assigned by Render, Koyeb, or Cloud Run.
* [ ] **Root Domain:** Visiting `https://your-domain.com/` shows the landing page; open `/dashboard/` for the dashboard.
* [ ] **Health & Ping Endpoints:**
  * Health check: `GET /health`
  * Ping: `GET /ping` (does not make a free host an always-on service)
* [ ] **Zero Inline Styles & Full Linter Compliance:** All HTML and CSS strictly adhere to modern web validation standards.
