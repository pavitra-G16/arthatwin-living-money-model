# Deployment Report

Verified 2026-11-21 (Asia/Kolkata).

- Frontend: https://arthatwin-living-money-model-2.onrender.com/
- Backend: https://arthatwin-living-money-model.onrender.com/
- Health: https://arthatwin-living-money-model.onrender.com/api/health
- Health result: `status=ok`, `database=reachable`, `mode=public-demo`.
- Frontend and backend Render deployments both reported successful/live.
- Frontend configured with the backend `/api` base URL and public-demo flag.
- Backend configured with public-demo mode, synthetic seed on startup, restricted CORS origin, and a generated reset token. Secret values are not recorded here.
- Frontend smoke-check showed the “Synthetic demo data” label and synthetic dashboard content (14 selected-period transactions).
- GitHub UI commit `dd7fc7d` (`style(frontend): elevate ArthaTwin visual system`) contains the UI theme changes and was the latest successfully deployed frontend source at verification.

## Hosting limits and safety

Render free services may sleep when idle. The backend health response confirms that the current database is reachable, but the configured database is SQLite on an ephemeral service filesystem. Data durability across restart/redeploy is not guaranteed. The site is a shared synthetic-only demo without login or user isolation. Do not submit actual financial statements or private transactions.

## Follow-up for production use

Provision durable managed PostgreSQL, configure `DATABASE_URL` in Render, migrate and verify data, then add authentication and tenant isolation before accepting private records. Recheck provider settings and all primary workflows after those changes.
