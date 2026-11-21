# Test and acceptance report

Last verified locally on 2026-11-21 from the current `post-submission` worktree.

| Command | Observed result |
| --- | --- |
| `cd backend && PYTHONDONTWRITEBYTECODE=1 ./venv/bin/pytest -q -p no:cacheprovider tests` | **26 passed**. Covers parsing, Decimal/paise and date handling, transfers/refunds, goal calendar math, import preview/confirmation dedupe, persistence, coverage gating, public-demo write restrictions, synthetic seed preservation, coach tool validation and local fake Gemini function selection. |
| `cd frontend && npm run lint` | **Passed** (ESLint exit 0). |
| `cd frontend && npm run build` | **Passed** (Next.js production build and TypeScript validation). |

The PDF test constructs a small text PDF and verifies extracted transaction fields. Scanned-PDF OCR is not supported and not claimed. The Gemini test uses a fake SDK response; no provider request was sent.

## Not verified

- No deployment or live URL exists. Hosting login, project connection and database provisioning are unavailable in this environment.
- No browser-driven E2E interaction test was run. Import UI, dashboard, category correction, subscriptions, goals, reports, coach, privacy controls and mobile behavior have not been verified in a browser.
- No live backend/database restart-persistence test or hosted frontend-to-backend communication test was possible.
- No fresh-install run on a clean machine/container, vulnerability scan, or dedicated secret scanner was run.
- Production CORS, secrets, health endpoint response and synthetic seed behavior are unverified on a host.

An earlier command invoked frontend lint from `backend/` and returned `ENOENT`; the correct frontend lint and build commands above were run from `frontend/` and passed.
