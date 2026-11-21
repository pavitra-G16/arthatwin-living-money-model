# Test Report

Updated 2026-11-21 (Asia/Kolkata) after the category precedence, demo-data repair, simulator comparison, and print stylesheet changes.

## Automated checks

| Command | Result | Evidence |
|---|---|---|
| `python3 -m pytest -q` from `backend/` | **31 passed** | Includes realistic synthetic CSV, text-PDF, and SMS UPI preview categorization; corrected merchant mappings; default-vs-learned rule behavior; retroactive correction and later matching; automatic demo-category repair while preserving locked/learned rows; 16 total / 14 selected-period reconciliation; recurring confidence and feedback persistence; profile/goals, simulator, drift gating, monthly report, and financial-safety tests. |
| `npm run lint` from `frontend/` | **Passed** | ESLint exit 0. |
| `npm run build` from `frontend/` | **Passed** | Next.js 16 production build completed. It emitted a non-blocking warning that a parent `/Users/pavitragangwar/package-lock.json` was ignored because it is outside this repository. |

## Live deployment checks (before this audit's code changes)

- Frontend/backend had been verified live earlier. Backend health returned `status=ok`, `database=reachable`, `mode=public-demo`.
- Render backend logs showed `GET /api/dashboard` and `GET /api/reports/monthly` returning `200`, plus an `OPTIONS` CORS preflight returning `200`.
- The app's API base URL has a single `/api` normalization; current Render environment includes `NEXT_PUBLIC_API_URL` (dashboard masks its value). The live request logs confirmed successful requests to the expected routes.

## Not verified

- This audit's latest source changes have **not yet been deployed** or tested against the live Render service.
- Full browser-driven UI workflows, print-to-PDF visual output, mobile/responsive device testing, browser refresh/restart persistence, and full import-to-report end-to-end journeys remain unverified.
- Optional Gemini was tested with a fake SDK response only; no provider request was sent.
- No fresh-install test, vulnerability scan, or dedicated secret scanner was run.
- Render SQLite storage is reachable but ephemeral; durability across restart/redeploy was not verified.

Do not treat an unverified item above as a pass. See [FEATURES_AND_REQUIREMENTS.md](FEATURES_AND_REQUIREMENTS.md) for statuses against every official requirement.
