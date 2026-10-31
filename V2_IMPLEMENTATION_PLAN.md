# ZYROX AI V2 — Phased Implementation Plan

**Plan date:** 2026-10-31
**Implementation status:** Phase 0 audit and inventory prepared. Phase 0.1 security containment is implemented locally and its focused test suite passes (21 passed, 2 warnings). Render has not been updated.
**Operating rule:** preserve existing routes and data; add versioned interfaces; never fabricate market, agent, backtest, or payment state; no live broker orders.

## Phase 0 — Repository audit and safety baseline (current)

**Scope:** map actual entrypoints, modules, routes, database, agents, feeds, integrations, auth, deployment, and tests. Record current features and risks.
**Deliverables:** `ARCHITECTURE_AUDIT.md`, `EXISTING_FEATURES_INVENTORY.md`, `V2_IMPLEMENTATION_PLAN.md`, `PRODUCTION_RISK_REGISTER.md`.
**Baseline:** 301 collected; 269 pass, 32 fail, 35 warnings.
**Acceptance:** no production code changes; P0 security finding documented; all subsequent phases have explicit evidence and rollback criteria.
**Rollback:** documentation only; remove/revise these audit files if the inventory is corrected.
**Exit gate:** fix R-01 before other production deployments; classify baseline test failures.

## Phase 0.1 — Critical Schema Studio containment

**Scope:** authenticate/authorize schema endpoints, enforce server-derived environment, disable public arbitrary SQL and DDL, and record the authenticated administrator on migration history.
**Likely files:** `taikry/api/schema_routes.py`, `taikry/schema/sql_studio.py`, `taikry/schema/migration_engine.py`, tests.
**Implemented locally:** every Schema Studio route now requires admin auth; SQL accepts a single `SELECT`/`EXPLAIN`, has bounded output, and cannot disable read-only mode; SQLite/PostgreSQL execution is placed in read-only mode; environment is taken from server config; Schema Studio migration apply is always blocked in production; migration history records the admin email.
**Tests:** unauthenticated calls rejected; admin access exercised; write queries, CTE mutations, multiple statements, and `read_only=false` rejected; production apply blocked even if payload says `local`; paid subscription plan catalog exercised; checkout rejects unauthenticated requests before invoice creation. Focused result: 21 passed, 2 deprecation warnings.
**Acceptance:** R-01 code mitigation is complete locally without changing production DB. Staging verification, review, and deployment remain required before claiming the live Render exposure is closed.
**Rollback:** revert route/service change; keep public write/apply disabled during rollback.
**Docs:** update security/risk runbook and API docs. Do not push/deploy until code review and staging verification.

## Phase 1 — ZYROX design system and responsive dashboard

**Scope:** reusable design tokens/components, navigation/search/profile/market status/notifications/language/theme, desktop/tablet/mobile layout, truthful loader/skeleton/empty/error/reconnect components. Start with shell and one representative dashboard page, then migrate panels incrementally.
**Likely files:** `taikry/web/index.html`, `styles.css`, `ui-kit.js`, `app.js`; new UI test setup only after dependency review.
**Tests:** asset/syntax checks, keyboard and contrast review, Khmer/English rendering, 320/360/768/1024/1440 px overflow checks, reduced-motion checks, no fake progress.
**Acceptance:** legacy actions still work; no horizontal page overflow; loading state reflects actual work; tested pages meet accessibility criteria.
**Rollback:** revert page/shell components independently; keep existing panels as fallback until migrated.
**Docs:** update feature inventory and screenshots/acceptance record.

## Phase 2 — Market-data integrity, charts, heatmap, scanner

**Scope:** source contract, symbol normalization, candle-gap detection, bid/ask/mid/spread provenance, clear feed disagreement, complete scanner/heatmap fields. Preserve Exness MT5 as preferred XAUUSD execution reference when fresh; keep OANDA/reference values identified separately.
**Likely files:** `taikry/data/providers.py`, `validator.py`, `mt5_receiver.py`, `taikry/api/routes.py`, `taikry/indicators/*`, `taikry/web/chart.js`, tests.
**Tests:** fresh/stale/missing/cross-feed cases, alias mapping, market closed, spread mismatch, missing bars, source/timestamp displayed.
**Acceptance:** never silently substitute or average incompatible feeds; current-price claims always carry source/time/freshness.
**Rollback:** retain existing provider order and endpoints behind additive configuration; revert only new views/adapters.
**Docs:** data-source matrix and supported symbol list.

## Phase 3 — AI Copilot and multi-agent orchestration

**Scope:** map requested 16 roles onto the current 17 adapters; standardize result schema; add durable execution/event records only after schema review; enforce actual timeout/retry/cancellation; stream only if existing hosting can support it; source-aware copilot tools and model fallback.
**Likely files:** `taikry/agents/*`, `taikry/ai/*`, `taikry/api/routes.py`, `models.py` plus reviewed migration, `app.js`.
**Tests:** deterministic snapshot fixtures, call-count/status truth, provider timeouts, conflicting votes, risk veto, stale prices, Khmer/English, output citations and redaction.
**Acceptance:** no reported active agent without a started task; each result includes source/time/evidence/status; risk manager remains independent; model keys remain server-side.
**Rollback:** keep existing `/api/v1` contracts; version new response fields/routes and disable new orchestration through config.
**Docs:** agent capability matrix, tool permissions, model routing/cost policy.

## Phase 4 — News Intelligence Center

**Scope:** verified calendar/news source records, publication/scheduled timestamps, actual/forecast/previous provenance, pre/post event scenarios, uncertainty and stale/unavailable states.
**Likely files:** `taikry/data/economic_calendar.py`, news modules, API routes, UI, fixtures.
**Tests:** source failures, empty success, timezone normalization, duplicate events, forecast vs actual, news citation/link and no invented fields.
**Acceptance:** unknown data stays unknown; no certain-outcome language.
**Rollback:** preserve current calendar/news API; remove new view behind a feature flag.
**Docs:** source/reliability policy.

## Phase 5 — Backtesting and Strategy Lab

**Scope:** experiment IDs, immutable strategy/dataset versions, realistic spread/commission/slippage, out-of-sample and walk-forward runs, drawdown/expectancy metrics, parameter sensitivity, multiple-testing caution.
**Likely files:** `taikry/trading/backtester.py`, `taikry/api/routes.py`, reviewed experiment models/migration, dashboard.
**Tests:** look-ahead/leakage, transaction costs, partial fills, missing data, reproducibility, time split boundaries and failure states.
**Acceptance:** every result is reproducible from recorded inputs; in-sample performance cannot promote a strategy.
**Rollback:** keep legacy backtest endpoint; gate experiment UI/API until results match independent fixtures.
**Docs:** metric definitions and experiment protocol.

## Phase 6 — Journal, consensus, signals, Telegram

**Scope:** isolated personal journal records/attachments; import support only through verified sources; outcome labels; signal consensus audit; durable notification dedup and explicit manual/shadow/paper promotion gates.
**Likely files:** `taikry/database/models.py`, `taikry/trading/*`, `taikry/notifications/telegram_service.py`, SaaS auth routes, UI, additive migrations.
**Tests:** cross-user isolation, idempotency across workers/restarts, exact daily cap, entry/SL/TP ambiguity, notification-off config and verified P/L.
**Acceptance:** ordinary app never sends live broker orders; no rewritten historical signals; no performance metric without recorded outcomes.
**Rollback:** leave existing signal tables and legacy views readable; roll back UI/API separately from additive schema.
**Docs:** signal rules and outcome calculation definitions.

## Phase 7 — ABA PayWay subscription lifecycle

**Scope:** retain provider adapter; confirm official live/sandbox merchant requirements, plan configuration, signed callback, server verification, idempotent payment/entitlement, history and expiration. Do not implement stored cards/automatic recurring charge without ABA approval and explicit user consent.
**Likely files:** `app/payments/*`, plan/admin services, models/migrations, `billing.html`, environment docs.
**Tests:** sandbox signature vectors, wrong amount/currency/merchant, duplicate/replayed callback, expired invoice, verify outage, user isolation and exactly-once activation.
**Acceptance:** server-side verified paid transaction only; dashboard redirect alone cannot grant access; no real charge in tests.
**Rollback:** disable checkout via configuration and preserve invoice history; never drop payment tables/data.
**Docs:** official provider references, environment separation, refund/cancel limitations.

## Phase 8 — Mobile PWA, notifications, accessibility, performance

**Scope:** only if existing browser/backend/deployment support is suitable: install manifest, service worker/cache policy, touch navigation, responsive charts, notification settings, accessibility and measured performance.
**Likely files:** frontend shell/assets and tests.
**Tests:** secure context, installability, offline-safe read-only routes, stale data labels, screen readers, keyboard, reduced motion, mobile viewport matrix.
**Acceptance:** no cached private pages/data exposed between accounts; no offline signal represented as live.
**Rollback:** remove registration and retain ordinary web dashboard.
**Docs:** PWA/browser support matrix and cache policy.

## Phase 9 — Security, integration, staging and production readiness

**Scope:** auth/CSRF/session, permissions, rate limits, secret redaction, uploads, dependency review, backup/restore, metrics/alerts, load and operational runbooks.
**Tests:** full suite green or documented accepted exceptions, security negative tests, cross-user tests, staging PayWay/Telegram/MT5/provider failure drills, restore and rollback rehearsal.
**Acceptance:** all 20 V2 criteria satisfied; no P0/P1 open; no unapproved live execution or recurring charge; verified rollback.
**Rollback:** tested application revision rollback, additive DB rollback plan, and disablement flags; avoid destructive DB rollback with retained data.
**Docs:** update `DEPLOYMENT.md`, `ROLLBACK.md`, `DATABASE_MIGRATIONS.md`, `SECURITY.md`, `API_DOCUMENTATION.md`, `OPERATIONS_RUNBOOK.md`, and release checklist.

## Phase gates and release policy

1. Keep the GitHub project and current production contracts as source of truth.
2. Phase 0.1 must close R-01 before production changes are deployed.
3. Work on a local/staging branch first; do not apply new production migrations automatically at web startup.
4. Require tests and a concrete diff for each phase; report passed, failed, unimplemented and blocked items honestly.
5. Deploy phase-by-phase only after the relevant checks pass; retain a revision and rollback instructions.
6. Never enable live trading, real payment credentials, automatic charging, or paid infrastructure without separate explicit authorization.
