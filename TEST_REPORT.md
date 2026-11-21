# Test and acceptance report

Last verified locally and on the Render public demo on 2026-11-21.

| Command | Observed result |
| --- | --- |
| `cd backend && PYTHONDONTWRITEBYTECODE=1 ./venv/bin/pytest -q -p no:cacheprovider tests` | **26 passed**. Covers parsing, Decimal/paise and date handling, transfers/refunds, goal calendar math, import preview/confirmation dedupe, persistence, coverage gating, public-demo write restrictions, synthetic seed preservation, coach tool validation and local fake Gemini function selection. |
| `cd frontend && npm run lint` | **Passed** (ESLint exit 0). |
| `cd frontend && npm run build` | **Passed** (Next.js production build and TypeScript validation). |

The PDF test constructs a small text PDF and verifies extracted transaction fields. Scanned-PDF OCR is not supported and not claimed. The Gemini test uses a fake SDK response; no provider request was sent.

Live checks: frontend loaded and displayed 14 synthetic transactions, modeled balances/goals, and recurring insights; frontend displayed the synthetic-demo label. Backend `/api/health` returned `{"status":"ok","database":"reachable","mode":"public-demo"}`. Render showed both services deployed successfully; CSS commit `dd7fc7d` was live on the frontend at verification.

## Not verified

- No complete browser-driven E2E test suite was run. Import journeys, category correction, subscriptions, goals, reports, coach, privacy controls and mobile behavior still need full interaction testing.
- Live checks confirm the frontend-to-backend dashboard path, but not all hosted workflows or restart-persistence.
- No fresh-install run on a clean machine/container, vulnerability scan, or dedicated secret scanner was run.
- SQLite is reachable, but Render's local filesystem is ephemeral; cross-redeploy persistence is not verified and must not be assumed.

An earlier command invoked frontend lint from `backend/` and returned `ENOENT`; the correct frontend lint and build commands above were run from `frontend/` and passed.
