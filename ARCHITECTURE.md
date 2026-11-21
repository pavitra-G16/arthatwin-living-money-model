# Architecture

## Components

- `frontend/`: Next.js App Router, React, TypeScript and Tailwind. The dashboard hosts the selected period, imports, learned categories, recurring review, simulator, coach and report workflows.
- `backend/main.py`: FastAPI routes, Pydantic input validation, upload bounds, preview staging, user-confirmed import and demo-mode isolation.
- `backend/importers.py`: CSV, PDF text and SMS parsing, Decimal normalization, date validation, duplicate fingerprints and untrusted narration handling.
- `backend/finance.py`: period filtering, monthly aggregates, category comparisons and goal projection.
- `backend/engine.py`: deterministic categorization, recurrence, simulations and coach tool routing; optional Gemini function calling is gated separately.
- `backend/database.py`: SQLAlchemy models and additive SQLite schema migrations. `DATABASE_URL` selects the database; the default is a local SQLite file.

## Data flow

1. A client sends a file or SMS body to a preview endpoint. File size and type are checked; parsed rows and issues are staged for 24 hours.
2. The UI displays duplicate flags, category suggestions, errors and date overrides. The user selects rows and confirms.
3. The API computes a stable fingerprint, rejects duplicates, categorizes locally and writes the selected rows in a savepoint-protected transaction.
4. Dashboard, report, nudges and simulations select an explicit `YYYY-MM` period and calculate from stored records and profile assumptions.
5. Category corrections write a persistent merchant rule and update unlocked matching rows. Subscription feedback is a separate explicit user statement.
6. The coach selects bounded read-only tools deterministically by default. If the user opts in and the backend enables external AI, Gemini receives the question text and chooses one allowlisted zero-argument function. The server validates and executes that function locally; stored financial data and calculated results are not sent to Gemini. The numerical response is composed locally from verified tool output.

## Calculation notes

New transaction/profile/goals monetary columns use `Numeric(14,2)` in SQLAlchemy, and importer amounts use `Decimal` with half-up paise rounding. Internal input validation limits values. Transfers and cash withdrawals are separated from observed expenses. Identified refunds offset both observed expenses and modeled surplus. Incomplete month data is explicitly marked unknown; dashboard and coach nudges require user confirmation for both periods. A legacy SQLite database created before the Numeric migration still has its original declared SQLite column affinities; it is read through SQLAlchemy Numeric scale conversion but has not been rebuilt in place.

## Runtime configuration

- `DATABASE_URL`: SQLAlchemy database connection; local default is `sqlite:///./arthatwin.db`. Standard `postgres://` and `postgresql://` inputs are normalized to the installed psycopg 3 driver.
- `CORS_ALLOWED_ORIGINS`: comma-separated browser origins. Configure exact deployed frontend origin.
- `ARTHATWIN_PUBLIC_DEMO=1`: enable synthetic-only read filters and block personal-data writes/imports.
- `SEED_SYNTHETIC_DEMO_ON_START=1`: initialize missing demo rows at backend startup.
- `DEMO_RESET_TOKEN`: protects seed/reset endpoints; keep server-side only.
- `NEXT_PUBLIC_API_URL`: full API base ending in `/api`, compiled into frontend.
- `NEXT_PUBLIC_ARTHATWIN_PUBLIC_DEMO=1`: shows public synthetic-data label and hides local seed button.
- `EXTERNAL_AI_ENABLED=1` and `GEMINI_API_KEY` (or `GOOGLE_API_KEY`): optional server-side AI; both are required in addition to per-request consent. `GEMINI_MODEL` overrides the default model name.

## Deployment shape

The safe unauthenticated deployment shape is a synthetic-only demo. Personal data requires authentication and user isolation before public use. It also requires durable database storage; ephemeral SQLite is not an acceptable production datastore. See [DEPLOYMENT.md](DEPLOYMENT.md).
