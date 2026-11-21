# Test Report

Updated 2026-11-21 (Asia/Kolkata) after the UI/consent updates and live deployment of `cef9480`.

## Automated checks

| Command | Result | Evidence |
|---|---|---|
| `python3 -m pytest -q` from `backend/` | **33 passed** | Includes realistic CSV, text-PDF, and SMS UPI preview categorization; merchant mappings; correction and later matching; file-backed rule persistence after closing/reopening the database engine; automatic demo-category repair preserving locked/learned rows; 16 total / 14 selected-period reconciliation; recurring feedback; profile/goals, simulator, drift gating, reports, CSV/JSON export, confirmed deletion, public-demo filtering, AI request opt-in, prompt minimization, fake-Gemini tool selection, and financial guardrails. |
| `npm run lint` from `frontend/` | **Passed** | ESLint exit 0. |
| `npm run build` from `frontend/` | **Passed** | Next.js 16 production build completed. It emitted a non-blocking warning that a parent `/Users/pavitragangwar/package-lock.json` was ignored because it is outside this repository. |

## Live deployment checks (commit `cef9480`)

- Both Render services reported commit `cef9480` Live. Frontend deploy `dep-dc0shf95efls73eg1b50`; backend deploy `dep-dc0shf95efls73eg1b80`.
- Opened the live frontend and confirmed it loaded the dashboard with 14 November transactions, ₹85,000 observed income, ₹34,006 expenses after refunds, and ₹44,172 modeled surplus. Recurring payment evidence appeared with cadence, confidence, and observation count.
- Direct live `GET /api/dashboard?month=2026-11` returned real transaction and summary JSON. It reconciled with the UI: ₹50,994 observed net savings, and categories included Groceries, Dining Out, Housing, Utilities, Subscriptions, Transport, and Review Required. A ₹1,500 Rahul Sharma debit was classified as Transfers / People and excluded from spending totals.
- Live backend health returned `status=ok`, `database=reachable`, `mode=public-demo`. Fresh Render logs showed GET health, dashboard, monthly report, simulation POST, and simulation CORS preflight returning 200. `HEAD /api/health` returned 405 because the route supports GET; this did not affect the app.
- Render frontend build environment was inspected: `NEXT_PUBLIC_API_URL=https://arthatwin-living-money-model.onrender.com/api`. Backend `CORS_ALLOWED_ORIGINS` exactly matches `https://arthatwin-living-money-model-2.onrender.com`. The app normalizes the API base to one `/api` path.
- Live monthly report JSON reconciled with the dashboard: ₹85,000 income; ₹34,006 expenses after refunds; ₹0 refunds; ₹50,994 observed savings; ₹44,172 modeled surplus; 14 November rows. Categories, goals, recurring evidence, and data-quality note matched.
- Post-deploy recheck confirmed live `GET /api/health` returns `status=ok`, `database=reachable`, `mode=public-demo`, and live monthly report JSON still returns the reconciled November figures.
- Render backend has public-demo, CORS, demo-seed, and reset-token variables; no Gemini enablement/key is configured. The live coach uses deterministic fallback.

## Manual browser checks

- Local isolated synthetic-data browser session verified the dashboard hero and values, a 30% dining cut (+₹534), and a ₹5,000 rent increase combined with that cut (net −₹4,466), plus monthly report figures and one-question AI consent resetting to off after send.
- In disposable local SQLite, a category edit created a visible rule, reclassified two unlocked matching rows, preserved the corrected row lock, and a future SMS preview used the learned category. A 390 px mobile viewport was visually inspected; the tab strip scrolls horizontally and content remains usable.
- Print was triggered from the report, but the browser did not yield a verifiable print preview. Do not count print/PDF as passed.

## Not verified

- Full hosted UI workflows beyond the live dashboard/report response, print-to-PDF output, broader responsive/device matrix, browser refresh/restart in Render, and complete hosted import-to-report journeys remain unverified.
- Optional Gemini was tested with a fake SDK response only; no provider request was sent.
- No fresh-install test, vulnerability scan, or dedicated secret scanner was run.
- A live Gemini provider call, live profile mutation, delete-data action, CSV/JSON download, and real PDF print export were not executed; those could affect or disclose live demo data. Endpoint behaviors are covered by automated tests where applicable.
- Render SQLite storage is reachable but ephemeral; durability across restart/redeploy is not guaranteed.

Do not treat an unverified item above as a pass. See [FEATURES_AND_REQUIREMENTS.md](FEATURES_AND_REQUIREMENTS.md) for statuses against every official requirement.
