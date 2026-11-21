# ArthaTwin — Personal Finance Coach with a Living Money Model

ArthaTwin turns supplied Indian bank statement data into a persistent, editable cashflow model. Categorization can use an optional language model for unknown merchants, while recurring detection, budget drift, financial totals, and goal projections remain deterministic Python calculations.

## Architecture

- `backend/main.py` exposes the FastAPI API and owns ingestion, corrections, profile, goals, subscriptions, dashboard, simulation, and coach routes.
- `backend/engine.py` contains CSV, text-PDF, and SMS parsing; injection detection; deterministic merchant rules; recurring payment checks; goal math; and coaching guardrails.
- `backend/database.py` defines the SQLite-backed SQLAlchemy model. Set `DATABASE_URL` to place the database on persistent storage.
- `frontend/app/page.tsx` is the Next.js dashboard. Its API base is `NEXT_PUBLIC_API_URL`, defaulting to `http://127.0.0.1:8000/api`.

The app does not connect to banks. The user imports files or pastes SMS text. PDF support is limited to text-based statements whose transaction rows expose a date, narration, amount, and optional DR/CR marker; scanned PDFs and OCR are not supported. CSV supports common Indian bank date, narration/description, debit/withdrawal, and credit/deposit column names. SMS parsing skips OTP, promotion, and balance-only messages and returns parsed and ignored counts.

The ingestion pipeline flags and quarantines common prompt-injection phrases in narration before categorization. The UI displays the security flag on each affected transaction. Corrections create persistent merchant rules, update matching unlocked transactions, and lock the corrected row against future rule updates. Person-to-person transfers are categorized as `Transfers / People` and excluded from discretionary totals.

Recurring alerts are based on repeated merchant transactions and observed amounts. The app cannot observe whether a user opened or used an app; recurring services therefore show a persistent Yes / No / Unsure confirmation. What-If projections use verified profile values, ledger entries, user-confirmed unused subscriptions, and the selected scenario levers. They are simple constant-monthly-surplus estimates, not predictions. Where the modeled surplus is not positive, the goal completion date is shown as unavailable.

Gemini (`google-genai`) is optional. Without `GEMINI_API_KEY`, unknown merchants remain reviewable and the coach uses a deterministic response. With a key, Gemini may suggest an unknown merchant category or phrase coaching text; it is not used to compute financial values. Requests for specific stock, mutual fund, crypto, or securities picks are blocked before an AI call.

## Run locally

Backend (Python 3.11+):

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Frontend (Node.js 20+):

```bash
cd frontend
npm ci
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api npm run dev
```

Open `http://localhost:3000` and choose **Load Sample Indian Bank Data** to populate the demo. Set `GEMINI_API_KEY` in the backend environment only if you want the optional Gemini fallback. Do not put that key in the frontend.

Run the deterministic and API tests from the repository root:

```bash
backend/venv/bin/pytest -q backend/tests
```

Build the frontend:

```bash
cd frontend
npm run build
```

## Deploy

### Render API

Create a Python web service rooted at `backend/`. Use build command `pip install -r requirements.txt` and start command `uvicorn main:app --host 0.0.0.0 --port $PORT`. Add a persistent disk mounted at `/var/data` and set `DATABASE_URL=sqlite:////var/data/arthatwin.db`. For an optional model fallback, add `GEMINI_API_KEY` as a secret environment variable. Set `CORS_ALLOWED_ORIGINS` to the deployed Vercel origin (comma-separated if needed).

SQLite requires persistent storage to retain user data across Render restarts. Without the disk and `DATABASE_URL`, the default local database is ephemeral on most hosted instances.

### Vercel frontend

Import the repository and set the project root to `frontend`. Set `NEXT_PUBLIC_API_URL` to the deployed Render API base including `/api` (for example, `https://your-service.onrender.com/api`), then deploy. Confirm the Render origin is present in `CORS_ALLOWED_ORIGINS`.

## Demo and submission

1. Seed the sample data and point out the PDF/CSV/SMS source labels, the Netflix price increase, the P2P transfer exclusion, and the quarantined hostile narration.
2. Change a transaction category and show the learned rule, retroactive updates, and user lock.
3. Mark a subscription as No, then show the deterministic What-If result and edit profile/goal inputs.
4. Ask the coach for a mid-cap mutual fund pick to show the guardrail, then print the monthly review.

The monthly review uses the current stored profile and ledger. It is an educational cashflow summary, not regulated financial advice.
