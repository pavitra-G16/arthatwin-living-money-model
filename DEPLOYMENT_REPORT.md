# Deployment Report

Verified 2026-11-21 (Asia/Kolkata), after deploy `4c19a37`.

- Frontend: https://arthatwin-living-money-model-2.onrender.com/
- Backend: https://arthatwin-living-money-model.onrender.com/
- Health: https://arthatwin-living-money-model.onrender.com/api/health
- Health result: `status=ok`, `database=reachable`, `mode=public-demo`.
- Frontend and backend Render deployments both reported successful/live for commit `4c19a37` (`fix: correct UPI categorization and audit demo calculations`). Frontend deploy ID: `dep-dc0rvpbbc2fs738797u0`; backend deploy ID: `dep-dc0rvpbbc2fs7387983g`.
- Frontend build environment is `NEXT_PUBLIC_API_URL=https://arthatwin-living-money-model.onrender.com/api` plus the public-demo flag. The source normalizes the API base to one `/api` segment.
- Backend environment is public-demo mode, synthetic seed on startup, `CORS_ALLOWED_ORIGINS=https://arthatwin-living-money-model-2.onrender.com`, and a generated reset token. No Gemini enablement or key is configured. Secret values are not recorded here.
- Live frontend displays the “Synthetic demo data” label, 14 November transactions, ₹85,000 income, ₹34,006 expenses after refunds, ₹50,994 observed net savings, and ₹44,172 modeled surplus. Recurring evidence shows Netflix ₹649/mo and Cultfit ₹1,499/mo with low confidence and two observations each.
- Direct live `GET /api/dashboard?month=2026-11` returned HTTP JSON data with the same reconciled totals and corrected UPI categories (e.g., Groceries, Dining Out, Housing, Utilities, and Transfers / People). No mock response was used.
- Live backend health returned `status=ok`, `database=reachable`, `mode=public-demo`. Earlier Render logs showed dashboard/report 200 responses and CORS preflight 200.

## Deployment configuration note

The checked-in `render.yaml` is a stale template: it declares `arthatwin-post-submission-api/web` on branch `post-submission`, while the active services above are connected to `main` under their current ArthaTwin names. It was not applied or used to redeploy.

## Hosting limits and safety

Render free services may sleep when idle. The backend database is SQLite on an ephemeral service filesystem. Data durability across restart/redeploy is not guaranteed. The site is a shared synthetic-only demo without login or user isolation. Do not submit actual financial statements or private transactions.

## Follow-up for production use

Provision durable managed PostgreSQL, configure `DATABASE_URL` in Render, migrate and verify data, then add authentication and tenant isolation before accepting private records. Print/PDF output, full hosted import-to-report journeys, and wider responsive-device testing still need verification. Configure Gemini deliberately only if the optional provider is needed; otherwise deterministic coaching remains active.
