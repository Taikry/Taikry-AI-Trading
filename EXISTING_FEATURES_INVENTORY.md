# ZYROX AI V2 — Existing Features Inventory

**Inventory date:** 2026-10-31
**Method:** verified repository code/routes/models/configuration; descriptive claims in README files are treated as claims until implemented behavior/tests corroborate them.

## Backend product capabilities

| Area | Present in repository | Current limits / verification needed |
|---|---|---|
| Dashboard/API | FastAPI app, health/ping, versioned REST routers, static dashboard | No v2 API namespace; no WebSocket transport found. |
| Market prices | MT5 receiver, OANDA v20, Binance, Yahoo/reference fallbacks, freshness/source metadata | Actual source depends on symbol and configured feed. TradingView iframe is not a source of execution prices. |
| Technical analysis | EMA/SMA, RSI, MACD, ATR, Bollinger, Stochastic, VWAP/session levels, pivots and chart endpoints | Confirm all catalog options have safe parameter validation and reliable UI access. |
| ICT/SMC and price structure | BOS/CHoCH, FVG, OB, liquidity sweeps, premium/discount, causal chart-engine tests | Some live data/volume capabilities are source-dependent; do not imply order-flow data without a verified feed. |
| Multi-timeframe and signals | M1–W1 chart/analysis paths, XAUUSD signal engine, candidate plans, signal lifecycle/outcomes | Agent quorum, source freshness, broker spread, and risk vetoes can result in WAIT/NO TRADE. |
| AI copilot | `/api/v1/ai/chat`, image input, conversation history, provider/model metadata, market scan context | Request/response JSON, not a server-streamed response. Model calls are configured/fallback-dependent; registered agents are not all independent LLMs. |
| Agent center | 17 runtime registry entries, fleet/registry/status, debate, learning metrics, deep analysis, counter/risk/portfolio/execution checks | Most are local deterministic analyses. A runtime registry entry does not prove a task ran; persisted per-execution event history is incomplete. |
| Economic news | Calendar normalization/fallback, high-impact/blackout status, macro news, pre-news research API | Provider/feed outages must remain visible as unavailable; verify source, publication time, and actual values per item. |
| Scanner/heatmap | Market matrix, best-setup universe, real-time price endpoint, filters in dashboard | Audit supports market matrix/scanning paths; a complete independently calibrated heatmap/relative-strength product is not established. |
| Charts | Vendored Lightweight Charts, TradingView Cloud iframe option, indicators, overlays, drawings, data-provenance metadata | Separate actual price source from chart display symbol; no silent feed substitution. |
| Backtesting | Backtest job API, historical simulation engine, results persisted in `backtest_jobs` | Full experiment/dataset versioning, walk-forward gate, Monte Carlo, cost calibration, and reproducibility workflow remain incomplete or need explicit verification. |
| Paper trading | Paper account, trades, risk calculations and lifecycle logic | Current tests include failures; reconcile expected behavior before adding new features. Live broker execution remains disabled. |
| Training/concepts | Self-training/weight adjustment from outcomes, learning scorecards, concept recommender | This is not a complete ML dataset/model registry or reproducible model-training lab. Do not call prompt/config changes model training. |
| Journal | Paper trade ledger/history and outcome records | No complete standalone user journal with attachments, notes, mistakes, emotional notes, or full analytics model found. |
| Telegram | Bot commands/keyboards/webhook, user linking, signal reports, event deduplication, VIP subscription management | Lifecycle alerts are off by default; several tests fail. Strict cross-worker idempotency requires DB-backed atomic claims. |
| SaaS accounts | Signup/login/logout, password reset/verification paths, user profiles, trial/plan/entitlements, support, admin functions | Raw session token is also returned in JSON; rate limiter is in process memory. |
| Payments | Paid subscription plans, invoice checkout, ABA PayWay hosted adapter, callback verification, server-side status check and payment history; `/dashboard/billing.html` displays the plan catalog and current provider readiness | Checkout depends on ABA settings in server secrets; Render is declared sandbox. No live merchant checkout was verified; no automatic recurring debit is established. Billing UI now labels environment/readiness and keeps checkout disabled when settings are absent. |
| Schema Studio | Introspection, DDL export, layout persistence, AI proposal, read-only SQL query, migration diff/apply/history | Local code now requires admin auth, restricts SQL to one read-only query, derives environment server-side, and blocks production apply. Staging and deployment verification remain pending. |
| System health | `/ping`, `/health`, system info, bridge/provider status, notification/system audit tables | No external tracing/metrics stack or complete health service aggregation established. |

## Registered agent inventory

The registry contains 17 adapters (see `taikry/agents/registry.py`):

1. Data Quality
2. Technical Analyst
3. ICT/SMC Analyst
4. Macro Analyst
5. Risk Validator
6. Consensus Engine
7. Debate Engine
8. Self Trainer
9. Orderflow/Sentiment Analyst
10. Fractal/MTF Analyst
11. Regime Detection
12. Quantitative Research
13. ML Forecast
14. Concept Recommender
15. Counter Analysis
16. Portfolio Analysis
17. Execution Simulation

The V2 prompt's 16 logical roles must be mapped onto these existing modules before building anything duplicate. Agent evidence must record which callable executed, on which snapshot, with which source/time and result. Several current runtime statuses are metadata in a singleton registry rather than a durable execution ledger.

## Current UI surfaces

The main dashboard contains a cockpit/trading workspace and panel/overlay surfaces for:

- Overview, markets, signals, history, analytics
- AI sidebar: Chat, Trade, Ledger
- Debate, training/learning, auto-fix alerts
- Macro/news and portfolio drawers
- Telegram, MT5 bridge, settings, admin, account, support
- Chart workspace with native Lightweight Charts and a TradingView Cloud embed option
- Dedicated landing and billing HTML pages

This does not establish a full separate page for every requested V2 destination. In particular, a complete standalone AI Research Center, market heatmap/scanner suite, Strategy Lab, AI Training Lab/model registry, smart journal, payment portal, system health center, and account settings redesign need phase-by-phase implementation and acceptance checks.

## Infrastructure and development files

- Python requirements are in `requirements.txt`; versions use lower bounds rather than a dependency lock.
- Dockerfile, Docker Compose, Render Blueprint, `Procfile`, deployment guides, `.env.example`, Make.com scenario templates, and MT5 bridge docs exist.
- Compose starts Redis, but application code does not show an active Redis client integration.
- Backend tests cover payment, agents, live-data guards, chat, charts, lifecycle, Telegram, SaaS and schema services. No frontend component/UI test harness was found.
- Existing custom migration scripts are not a single versioned Alembic history.

## V2 requested features not yet established as complete

- Complete 16-role orchestrated fleet with durable task/event history and truthful active/completed/failed/skipped status.
- AI streaming transport, persistent per-user chat history, source citations and tool-controlled market/news/backtest access in all copilot responses.
- Dedicated V2 REST/WS contract, reusable route/page component system, PWA and offline/install behavior.
- Unified live-data heatmap/scanner with validated relative strength/volume semantics.
- Reproducible experiment and data/model registry, out-of-sample validation and multiple-testing controls.
- Full journal model with attachments, notes, tagged mistakes, and verified performance analytics.
- Production PayWay checkout with ABA-approved credentials and verified callback/transaction flow; automatic recurring payment is excluded unless explicitly approved.
- Full staging, security integration, accessibility, responsive-browser, load, backup/restore, and production rollback evidence.
