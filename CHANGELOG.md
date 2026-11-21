# Changelog

## Post-submission production readiness work

- Switched financial amounts to decimal database columns and added deduplication fingerprints and demo-data ownership markers.
- Added row-level CSV, text-PDF and SMS parsing with import staging, review, confirmation, missing-date corrections and duplicate prevention.
- Reworked period calculations for credits, transfers, refunds, fixed/variable costs, statement-coverage gating, and calendar-based goal dates.
- Added persistent correction rules, user locks, rule enable/disable, recurrence feedback, deterministic simulator and structured coach traces.
- Added an optional, disabled-by-default Gemini function-calling flow with per-question consent and read-only tools.
- Isolated unauthenticated public demo reads to synthetic records; restricted personal writes/imports and clear-data action.
- Reworked dashboard and selected-month report to remove fabricated health scores, hardcoded report dates, subscription savings and seed agent trace.
- Added backend parsing/API/financial tests and product/security/API/deployment/demo documentation.

## Prior baseline

The work began at baseline commit `a0a435e` on a separate `post-submission` branch. User-edited `sample_data/ground_truth.json` and `sample_data/transactions_synthetic.csv` were present before this work and remain uncommitted and preserved.
