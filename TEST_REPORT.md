# Test Report

Updated 2026-11-21 (Asia/Kolkata) after the category precedence, demo-data repair, simulator comparison, and print stylesheet changes.

## Automated checks

| Command | Result | Evidence |
|---|---|---|
| `python3 -m pytest -q` from `backend/` | **31 passed** | Includes realistic synthetic CSV, text-PDF, and SMS UPI preview categorization; corrected merchant mappings; default-vs-learned rule behavior; retroactive correction and later matching; automatic demo-category repair while preserving locked/learned rows; 16 total / 14 selected-period reconciliation; recurring confidence and feedback persistence; profile/goals, simulator, drift gating, monthly report, and financial-safety tests. |
| `npm run lint` from `frontend/` | **Passed** | ESLint exit 0. |
| `npm run build` from `frontend/` | **Passed** | Next.js 16 production build completed. It emitted a non-blocking warning that a parent `/Users/pavitragangwar/package-lock.json` was ignored because it is outside this repository. |

## Live deployment checks (commit `4c19a37`)

- Both Render services reported commit `4c19a37` Live. Frontend deploy `dep-dc0rvpbbc2fs738797u0`; backend deploy `dep-dc0rvpbbc2fs7387983g`.
- Opened the live frontend and confirmed it loaded the dashboard with 14 November transactions, ₹85,000 observed income, ₹34,006 expenses after refunds, and ₹44,172 modeled surplus. Recurring payment evidence appeared with cadence, confidence, and observation count.
- Direct live `GET /api/dashboard?month=2026-11` returned real transaction and summary JSON. It reconciled with the UI: ₹50,994 observed net savings, and categories included Groceries, Dining Out, Housing, Utilities, Subscriptions, Transport, and Review Required. A ₹1,500 Rahul Sharma debit was classified as Transfers / People and excluded from spending totals.
- Live backend health returned `status=ok`, `database=reachable`, `mode=public-demo`. Previously inspected logs showed dashboard/report requests and CORS preflight succeeding with 200 responses.
- Render exposes `NEXT_PUBLIC_API_URL` in the frontend build environment (value masked in dashboard); the app normalizes the base to a single `/api` path. Successful live frontend API results verify effective connectivity.

## Not verified

- Full browser-driven UI workflows beyond the live dashboard, print-to-PDF visual output, mobile/responsive device testing, browser refresh/restart persistence, and full import-to-report end-to-end journeys remain unverified.
- Optional Gemini was tested with a fake SDK response only; no provider request was sent.
- No fresh-install test, vulnerability scan, or dedicated secret scanner was run.
- Render SQLite storage is reachable but ephemeral; durability across restart/redeploy is not guaranteed.

Do not treat an unverified item above as a pass. See [FEATURES_AND_REQUIREMENTS.md](FEATURES_AND_REQUIREMENTS.md) for statuses against every official requirement.
