# ArthaTwin — Project Report

**ArthaTwin — Your Living Money Model** turns imported transaction history into a transparent, period-aware personal cashflow model. It is an educational planning prototype, not a financial adviser or bank connection.

## Problem and approach

Indian bank data arrives as CSV rows, statement PDFs, and SMS text with noisy UPI narrations and inconsistent merchant labels. ArthaTwin previews parsed rows before saving, keeps transfers/refunds distinct in calculations, and makes assumptions visible. Users can correct merchant categories; corrections are stored as reusable rules. The model supports recurring-payment evidence, goal scenarios, monthly reviews, and a deterministic coach grounded in app data.

## Architecture

- Next.js 16 and React 19 user interface.
- FastAPI and SQLAlchemy service with Decimal-based INR arithmetic.
- SQLite in the current Render setup; optional PostgreSQL support exists in configuration.
- Optional Google Gemini tool selection defaults off and requires server-side `EXTERNAL_AI_ENABLED=1`, a provider API key, and one-question consent. The provider sees the question and selected month only; selected read-only tools execute locally and local deterministic code writes the answer from verified outputs. Disabled, unavailable, or invalid tool selection falls back to deterministic coaching. Merchant learning and financial simulations are rules/math, not LLM features.

## Current demo

- Frontend: https://arthatwin-living-money-model-2.onrender.com/
- Backend health: https://arthatwin-living-money-model.onrender.com/api/health
- The public demo mode filters to synthetic rows and disables personal imports and profile/goal writes. Never enter real financial information.

## Audit fixes

- UPI merchant phrases now take priority over generic transfer-narration detection. The synthetic examples map Instamart to Groceries, Starbucks/Zomato to Dining Out, NoBroker rent to Housing, Airtel Fiber to Utilities, and Rahul Sharma to Transfers / People.
- On startup with synthetic seeding enabled, the backend re-evaluates only unlocked, non-learned synthetic categories. It preserves manually locked and user-learned labels and does not touch non-demo records.
- The what-if view now shows baseline surplus, simulated surplus, and monthly delta side by side. Recurring candidates show inferred cadence, observation count, and qualitative confidence. Print styling scopes output to the monthly report.
- The overview now features an animated, reduced-motion-aware outflow ring computed from observed income and expenses, plus actual imported/modelled figures. No decorative sample amounts are used in the visualization.
- External AI consent now resets after each coach question; navigation and rule-memory labels distinguish deterministic rules from an LLM.
- The sample has 16 rows total across two months; 14 belong to November. Exact totals and the dining/rent scenarios are documented in [FEATURES_AND_REQUIREMENTS.md](FEATURES_AND_REQUIREMENTS.md).
- Commit `4c19a37` is live on both Render services. The live frontend dashboard and direct backend dashboard API agree on November totals: ₹85,000 income, ₹34,006 expenses after refunds, ₹50,994 observed net savings, and ₹44,172 modeled surplus.

## Known limitations

- No login or tenant isolation; public users share the synthetic demo state.
- Current Render backend uses SQLite on an ephemeral filesystem; durable persistence across redeploys is not guaranteed. Do not use for real records until a managed persistent database and access control are in place.
- Text-based PDF parsing is supported; scanned PDF OCR is not.
- No live bank integrations or transaction execution.
- Gemini is optional and was not called during verification.
- Tests exercise a simulated Gemini SDK tool-selection response, validate that prompt inputs exclude account data and narration, enforce request opt-in, and cover deterministic fallback when external AI is off. No real provider request was sent.
- Browser print/PDF output and full hosted import-to-report journeys have not been verified. One 390 px viewport was visually checked; broader device coverage remains outstanding. Cross-redeploy persistence is not guaranteed on ephemeral SQLite.

See [FEATURES_AND_REQUIREMENTS.md](FEATURES_AND_REQUIREMENTS.md), [TEST_REPORT.md](TEST_REPORT.md), [DEPLOYMENT_REPORT.md](DEPLOYMENT_REPORT.md), and [SECURITY.md](SECURITY.md) for evidence and caveats.
