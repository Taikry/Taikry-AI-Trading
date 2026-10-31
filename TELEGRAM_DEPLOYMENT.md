# ZYROX AI Telegram delivery — setup and rollout

This guide covers the existing FastAPI/Render app. Keep bot and broker credentials in environment secrets; never paste them into source files, screenshots, or logs.

## Local setup

1. Create/activate the project's Python environment and install `requirements.txt`.
2. Copy `.env.example` to `.env` and set `TELEGRAM_ENABLED=true`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and the Telegram admin IDs. Do not commit `.env`.
3. For a quiet development start, set `TELEGRAM_SEND_LIFECYCLE_EVENTS=false`; enable it after checking the private test chat.
4. Keep `AUTO_START_MONITORING=true` on only one local app instance. The local database initializes through `taikry.database.session.init_db()`.

## Subscription-to-signal flow

The website plans (`free_trial`, `pro`, `premium`) control SaaS signal access. When payment is verified, the user has an active entitlement, links a private Telegram chat, and leaves **Real-time Trading Signals** enabled, each newly approved signal is sent to the shared configured chat and to that user's linked Telegram chat. Lifecycle updates follow the same eligibility check; stop, expiry, cancellation, and close notices also honor the **Risk Cap & Invalidation Warnings** preference. Delivery is recorded in the Telegram outbox per chat, so a retry does not duplicate an already delivered message. XAUUSD signal production remains capped at four signals globally per Cambodia day, and a valid setup may not occur each day.

The `FREE`/`PRO`/`VIP`/`LIFETIME` entries in the Telegram VIP manager are a separate legacy channel-membership catalog. Do not use those tiers to decide website ABA plan entitlements. Current website plans all set `telegram_alerts_enabled=true`; the active plan, Telegram link, and preferences are checked again on the server at send time.

## Database schema

On application startup, `Base.metadata.create_all()` creates the notification outbox, analysis-run, media registry, and daily quota tables. The idempotent Telegram migration adds quote provenance columns to existing XAUUSD signal rows and the third target to existing lifecycle rows. Existing rows are left unchanged; the new nullable fields remain empty for historical data.

Before the first production restart, back up PostgreSQL and verify the Render service is using the intended database. After startup, inspect `telegram_notifications`, `telegram_analysis_runs`, `telegram_media_assets`, `xauusd_daily_quota_reservations`, `xauusd_telegram_signals`, and `signal_lifecycles`.

## Telegram media

The checked-in media catalog is under `taikry/web/static/telegram/`. It contains 512×512 WEBP status stickers and a 3-second 512×512 MP4 scanner. Local registration checks the file extension, path, size, dimensions, and checksum; the media registry caches the returned Telegram `file_id`.

```powershell
python -m taikry.notifications.telegram_media_catalog
```

That command only registers assets. To send a single selected asset to the configured chat, choose one ID printed by the command:

```powershell
python -m taikry.notifications.telegram_media_catalog --send BUY_SIGNAL:sticker:1
```

The Docker image includes `ffmpeg`/`ffprobe` for video dimension validation. Asset sending is explicit; analysis does not post one sticker per agent. A Telegram network timeout is treated as uncertain and is not blindly retried.

## Test and preview

Run the focused suite locally before using a bot connected to a group:

```powershell
python -m pytest tests/test_telegram_media_assets.py tests/test_telegram_notification_outbox.py tests/test_subscription_signal_delivery.py tests/test_saas_platform.py tests/test_telegram_best_setup_score.py tests/test_xauusd_telegram_engine.py tests/test_telegram_duplicate_prevention.py
```

Use the admin-only `POST /api/v1/telegram/test-notification` endpoint to send one plain diagnostic message. It reports only the Telegram relay result and does not claim market, AI, or risk systems passed. `POST /api/v1/telegram/send-test-signal` is different: it performs a live analysis and may send a validated signal, so use it only in the test chat when that is intended.

## Render configuration

The Blueprint declares these keys without embedding secret values: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_ADMIN_IDS`, `TELEGRAM_WEBHOOK_SECRET`. Set them in the Render service environment after onboarding the bot. `TELEGRAM_ENABLED=true`, `TELEGRAM_SEND_LIFECYCLE_EVENTS=true`, and `MAX_DAILY_XAUUSD_SIGNALS=4` are non-secret settings. `TELEGRAM_MEDIA_MAX_BYTES` defaults to 10 MiB.

The current manifest runs one web instance with `AUTO_START_MONITORING=true`. Keep that topology at one instance; do not add a second monitoring worker unless in-web monitoring is disabled and a single worker owner is configured. Confirm `/ping`, Telegram test notification, database migration, and a private-chat scan before inviting users.

## Rollback

To stop all Telegram sends while leaving analysis and web APIs running, set `TELEGRAM_ENABLED=false` and restart the service. To pause lifecycle-only updates, set `TELEGRAM_SEND_LIFECYCLE_EVENTS=false`. For a code rollback, redeploy the previous Render deployment; the added database fields are nullable and can remain in place. Do not drop the new tables or columns during rollback because they may already contain delivery audit records.
