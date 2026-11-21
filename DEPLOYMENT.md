# Deployment guide and release gate

## Current status

No deployment has been made and there is no live URL. This environment has no authenticated GitHub, Vercel, Render or database-provider session, and no Vercel/Render CLI. Deployment is blocked until the owner connects the repository and creates provider projects. Do not claim local checks are a live deployment.

## Free synthetic-demo architecture

Subject to owner account/project setup, use Vercel Hobby for the frontend, a Render Free web service for the FastAPI backend, and Neon Free PostgreSQL for persistent data. Vercel Hobby is intended for personal, non-commercial use; confirm that use fits the hackathon. Neon Free provides persistent PostgreSQL within its published quota (including 1 GB storage and 100 CU-hours per project/month); compute can scale to zero and quota exhaustion can suspend compute. Render Free web services spin down when idle and have ephemeral local filesystems, so SQLite on Render is not durable. Render's free Postgres is time-limited and is not the selected database. Review current limits: [Vercel Hobby](https://vercel.com/docs/plans/hobby), [Neon plans](https://neon.com/docs/introduction/plans), [Neon free limits](https://github.com/neondatabase/website/blob/main/content/faqs/free-plan-limits-and-quotas.md), [Render free services](https://render.com/docs/free).

This is suitable only for a synthetic shared demo. The app has no authentication or tenant isolation. Public mode blocks imports, profile/goal writes and clear-data, but category corrections and subscription feedback modify shared synthetic state. Never load real financial information.

## Owner action required

1. Sign into Vercel, Render and Neon; connect the existing GitHub repo `pavitra-G16/arthatwin-living-money-model` to Vercel and Render, and create a Neon Free PostgreSQL project.
2. Add the Neon connection string directly as a Render secret (`DATABASE_URL`); do not paste it into chat or commit it.
3. Provide/enable the deployment authorization or connected accounts so deployment can continue. No paid option is required for the proposed setup; do not upgrade plans without explicit approval.

The current worktree has two pre-existing user edits in `sample_data/ground_truth.json` and `sample_data/transactions_synthetic.csv`. Keep them out of any deployment commit unless separately requested. The original baseline is available at `post-submission-baseline` and commit `a0a435e95f45ebc76e2e`.

## Service configuration

Backend (Render, root directory `backend/`):

- Build: `pip install -r requirements.txt`
- Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Set `DATABASE_URL` to the Neon PostgreSQL URL in Render's secret environment settings. The app normalizes `postgres://`/`postgresql://` URLs to the installed psycopg 3 driver; startup initializes the schema.
- Set `ARTHATWIN_PUBLIC_DEMO=1`, `SEED_SYNTHETIC_DEMO_ON_START=1`, `DEMO_RESET_TOKEN` to a strong random secret, and `CORS_ALLOWED_ORIGINS=https://<vercel-domain>`.
- Keep external AI disabled unless deliberately configured. If enabled later, store the Gemini key only in backend secrets and retain per-request user consent.
- Health check path: `/api/health`.

Frontend (Vercel, root directory `frontend/`):

- Install: `npm ci`
- Build: `npm run build`
- Build environment: `NEXT_PUBLIC_API_URL=https://<render-service>.onrender.com/api`, `NEXT_PUBLIC_ARTHATWIN_PUBLIC_DEMO=1`.

After obtaining both service origins, set the exact Vercel origin in backend CORS and redeploy the backend. No secret belongs in a `NEXT_PUBLIC_` variable. Confirm the API URL is HTTPS and not localhost.

## Verification after authorization

Open the public frontend and confirm the synthetic dashboard loads; call `https://<backend>/api/health`; check imports are disabled, and manually exercise correction, recurring feedback, goal simulation, report and deterministic AI fallback. Inspect browser console/network errors and a narrow mobile viewport. Restart the backend and confirm synthetic state remains in Neon. Record exact observed results in `TEST_REPORT.md`; do not report unperformed browser checks as passed.
