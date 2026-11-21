# ArthaTwin

**Intelligence Behind Every Rupee** — a personal finance coach built around a period-aware, deterministic cashflow model.

ArthaTwin imports CSV, text-based PDF and SMS transaction data; previews every import before saving; categorizes transactions with confidence; learns user corrections; detects recurring-payment candidates; models goal scenarios; and produces a period-scoped monthly review. It is an educational planning tool, not a financial adviser.

## Current state

- Next.js 16 / React 19 frontend; FastAPI / SQLAlchemy backend.
- INR amounts use decimal precision; transfers, refunds and credits have separate treatment in monthly calculations.
- The public-demo mode is synthetic-data-only. It disables personal imports and profile/goal writes, and filters reads and exports to demo rows.
- Optional Google Gemini function calling is off by default, requires `EXTERNAL_AI_ENABLED=1`, a server-side API key, and one-question consent. Gemini receives only the question and selected month to choose one of seven bounded read-only tools. The tool runs locally and a deterministic explanation is grounded in its verified result; profile/transaction data and raw narration stay on the server. Errors or invalid tool choices fall back to the deterministic coach.
- Merchant categorization and correction memory are deterministic rules, not an LLM. Goal scenarios are mathematical calculations, not AI predictions.
- Live synthetic demo: [arthatwin-living-money-model-2.onrender.com](https://arthatwin-living-money-model-2.onrender.com/). Backend health: [API health](https://arthatwin-living-money-model.onrender.com/api/health). This is a restricted public demo, not a production financial service.

## Run locally

Backend (from `backend/`):

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Frontend (from `frontend/`, in a second terminal):

```bash
npm ci
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api npm run dev
```

Open `http://localhost:3000`. Use **Load Sample Indian Bank Data** to create clearly fictional records. The reset/seed operation only replaces records marked as synthetic demo rows; it preserves non-demo profile and transaction data. A local `backend/arthatwin.db` file is ignored by Git.

For a synthetic-only public demo, set `ARTHATWIN_PUBLIC_DEMO=1`, `SEED_SYNTHETIC_DEMO_ON_START=1`, and a strong `DEMO_RESET_TOKEN` on the backend; set `NEXT_PUBLIC_ARTHATWIN_PUBLIC_DEMO=1` at frontend build time. Also set `CORS_ALLOWED_ORIGINS` to the exact HTTPS frontend origin. Public demo users share fictional sample data; do not put real financial data there.

## Main workflows

1. Choose a reporting month and inspect imported transactions, profile assumptions and data-quality notes.
2. In the transaction centre, upload CSV/PDF/TXT or paste bank SMS, review parsed rows, deselect duplicates, provide missing dates and confirm the rows to save.
3. Correct a transaction category after seeing the actual unlocked-match count; the correction is persisted as a learned merchant rule. Rules can be disabled.
4. Review recurring-payment candidates and record whether a service is still used. The app does not infer service usage from a debit.
5. Adjust dining, rent, income and subscription assumptions in the deterministic what-if simulator.
6. Ask the coach for a profile, monthly summary, recurring, or scenario explanation. It returns the selected tool and verified result. External model processing remains opt-in.
7. Confirm statement completeness for both comparison months before the app surfaces month-over-month spending drift.
8. Print the selected-month report or export CSV/JSON. Clear-data requires an explicit confirmation.

## Verification

See [TEST_REPORT.md](TEST_REPORT.md) for exact commands, observed results and unrun checks. The latest local acceptance run passed 33 backend tests, frontend ESLint, and a Next.js production build. Live dashboard/API connectivity was verified; the optional Gemini provider was not called live.

## Documentation

- [Product specification](PRODUCT_SPEC.md)
- [Architecture](ARCHITECTURE.md)
- [Security and privacy](SECURITY.md)
- [API reference](API.md)
- [Deployment guide](DEPLOYMENT.md)
- [60–90 second and three-minute demo scripts](DEMO_SCRIPT.md)
- [Changelog](CHANGELOG.md)
- [Hackathon project report](PROJECT_REPORT.md)
- [Requirements and judging map](FEATURES_AND_REQUIREMENTS.md)
- [Live deployment report](DEPLOYMENT_REPORT.md)
- [Submission and launch materials](SUBMISSION_DETAILS.md)
