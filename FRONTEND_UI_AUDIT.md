# ZYROX AI Frontend UI Audit and Redesign Plan

## Audit

- The dashboard is a vanilla JavaScript SPA served by FastAPI at `/dashboard/`. Its primary files are `taikry/web/index.html`, `app.js`, `chart.js`, and the shared `styles.css`; the chart uses the vendored Lightweight Charts build.
- The main terminal contains overview, AI analysis/registry, markets, charts, signals, history, analytics, economic calendar, watchlist, Telegram, MT5, settings, admin, account, support, debate, training, and auto-fix panes. The public landing/auth experience is `landing.html`; subscription, checkout status, payment history, and admin payment views are in `billing.html`.
- The interface already uses an emerald/charcoal theme and Khmer font support. Styling is shared, but the stylesheet is large and has accumulated page-specific rules. There is no frontend package manager or component framework, so the redesign should stay dependency-free and reuse the existing architecture.
- Current refreshes use existing HTTP APIs, including `/health`, `/api/v1/prices/realtime`, `/api/v1/agents/registry/summary`, chart candles/overlays, `/api/v1/news/live`, and the subscription/payment APIs. The registry summary reports health and execution totals but did not expose in-flight execution state at audit time.
- Most loading feedback is plain placeholder text. Chart fetch failures are logged, several screens have ad hoc error text, and there is no shared full-screen boot experience or accessible loader library.
- Billing already checks provider availability and obtains payment status from the server. The UI must continue to show success only after server verification and must preserve the existing ABA PayWay request/callback contract.

## Implementation Plan

1. Keep the SPA, HTTP routes, chart library, authentication, payment callbacks, and existing trading integrations intact.
2. Add a small shared, dependency-free UI kit for startup, page/section loading, skeletons, chart/table/card states, busy buttons, agent activity, payment verification, progress, empty states, and recoverable errors.
3. Extend the existing agent registry telemetry with truthful queued/running/completed/failed/skipped execution states and expose them through the current read-only registry summary endpoint.
4. Wire startup, market analysis, chart refreshes, dashboard sections, and billing verification to the shared UI kit. Show indeterminate activity unless the backend supplies a real progress value.
5. Refine shared design tokens, surfaces, focus states, responsive layouts, and reduced-motion behavior, then verify representative desktop and mobile screens plus the relevant backend tests.

## Verification Notes

- No new third-party frontend dependencies are planned.
- Real Telegram dispatches, broker orders, payment creation, and provider-side mutations are excluded from UI testing.
- Per-agent activity is available only for this app process; durable history remains represented by the existing server reports and signal ledger.
