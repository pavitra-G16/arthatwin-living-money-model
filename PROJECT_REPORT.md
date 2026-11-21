# ArthaTwin — Project Report

**ArthaTwin — Your Living Money Model** turns imported transaction history into a transparent, period-aware personal cashflow model. It is an educational planning prototype, not a financial adviser or bank connection.

## Problem and approach

Indian bank data arrives as CSV rows, statement PDFs, and SMS text with noisy UPI narrations and inconsistent merchant labels. ArthaTwin previews parsed rows before saving, keeps transfers/refunds distinct in calculations, and makes assumptions visible. Users can correct merchant categories; corrections are stored as reusable rules. The model supports recurring-payment evidence, goal scenarios, monthly reviews, and a deterministic coach grounded in app data.

## Architecture

- Next.js 16 and React 19 user interface.
- FastAPI and SQLAlchemy service with Decimal-based INR arithmetic.
- SQLite in the current Render setup; optional PostgreSQL support exists in configuration.
- Optional Gemini function calling is off unless configured and explicitly consented to; deterministic responses remain available.

## Current demo

- Frontend: https://arthatwin-living-money-model-2.onrender.com/
- Backend health: https://arthatwin-living-money-model.onrender.com/api/health
- The public demo mode filters to synthetic rows and disables personal imports and profile/goal writes. Never enter real financial information.

## Audit fixes

- UPI merchant phrases now take priority over generic transfer-narration detection. The synthetic examples map Instamart to Groceries, Starbucks/Zomato to Dining Out, NoBroker rent to Housing, Airtel Fiber to Utilities, and Rahul Sharma to Transfers / People.
- On startup with synthetic seeding enabled, the backend re-evaluates only unlocked, non-learned synthetic categories. It preserves manually locked and user-learned labels and does not touch non-demo records.
- The what-if view now shows baseline surplus, simulated surplus, and monthly delta side by side. Recurring candidates show inferred cadence, observation count, and qualitative confidence. Print styling scopes output to the monthly report.
- The sample has 16 rows total across two months; 14 belong to November. Exact totals and the dining/rent scenarios are documented in [FEATURES_AND_REQUIREMENTS.md](FEATURES_AND_REQUIREMENTS.md).
- Commit `4c19a37` is live on both Render services. The live frontend dashboard and direct backend dashboard API agree on November totals: ₹85,000 income, ₹34,006 expenses after refunds, ₹50,994 observed net savings, and ₹44,172 modeled surplus.

## Known limitations

- No login or tenant isolation; public users share the synthetic demo state.
- Current Render backend uses SQLite on an ephemeral filesystem; durable persistence across redeploys is not guaranteed. Do not use for real records until a managed persistent database and access control are in place.
- Text-based PDF parsing is supported; scanned PDF OCR is not.
- No live bank integrations or transaction execution.
- Gemini is optional and was not called during verification.
- Browser print/PDF output, responsive layouts, and full hosted import-to-report journeys have not been verified. Cross-redeploy persistence is not guaranteed on ephemeral SQLite.

See [FEATURES_AND_REQUIREMENTS.md](FEATURES_AND_REQUIREMENTS.md), [TEST_REPORT.md](TEST_REPORT.md), [DEPLOYMENT_REPORT.md](DEPLOYMENT_REPORT.md), and [SECURITY.md](SECURITY.md) for evidence and caveats.
