# ArthaTwin product specification

## Purpose

Help a person understand cashflow and model practical savings choices from imported financial records and user-entered assumptions. The product does not initiate payments or make investment recommendations.

## Supported workflows

- **Import:** CSV, text-based PDF and pasted/uploaded UTF-8 SMS text. CSV supports flexible common headers, row-level errors, a 10,000-row cap, and duplicate fingerprints. PDF parsing is text extraction only, limited to 150 pages; scanned image OCR is unsupported. SMS filtering excludes OTP, promotion and balance-only messages. Users review rows and resolve missing dates before saving.
- **Categorize and learn:** deterministic merchant/category rules with confidence/source, untrusted narration quarantine, correction preview and persistent exact-merchant learned rules. Corrected rows are user-locked; rules can be revised or disabled.
- **Recurring payments:** dated repeat candidates for supported weekly, monthly, quarterly and annual intervals. Price changes and amount variations are review signals. Usage status is user-confirmed.
- **Profile and goals:** persistent single profile and multiple goals with target, saved amount, target date and priority. The public synthetic demo makes profile/goal editing read-only.
- **Planning:** deterministic monthly cashflow scenarios for dining reduction, rent changes, income increases/decreases and user-marked unused recurring charges. Estimates use calendar-month imported values and explicit assumptions.
- **Nudges/reports:** category change nudges require the selected and previous months to be user-confirmed complete. Monthly report uses a selected calendar month, states data-quality caveats, and can be printed.
- **Coach:** local deterministic tool selection is always available. Optional Gemini function calling is server-side and requires environment enablement, a server secret, and per-question consent. Tools are read-only and calculations stay local.

## Metrics and provenance

- Observed income: non-transfer, non-refund credits in the selected month.
- Observed expenses: debit transactions excluding transfer/cash-withdrawal categories, less identified credits categorized as refunds.
- Observed savings: observed income minus observed expenses; unavailable when the month contains no observed income.
- Modeled monthly surplus: profile monthly income minus the greater of profile fixed costs or observed fixed-category debits, minus observed variable debits. This is not bank-verified savings and is not inherently a statement-period total.
- Goal completion date: remaining target divided by modeled monthly surplus, rounded up to whole months and added using calendar-month arithmetic. It is a scenario estimate.

## Public demo boundary

The public demo is one shared, fictional dataset with no user authentication. In `ARTHATWIN_PUBLIC_DEMO=1`, imports, personal profile/goal edits and delete-all are blocked; dashboard, report, coach, transactions and exports filter to records marked synthetic. Correction and subscription feedback can change synthetic demo state and therefore are visible to other demo visitors. Never enter real bank data in this mode.

## Limitations

- No account authentication or multi-tenant personal-data service.
- Single-user local mode; deploy personal mode only behind an appropriate access boundary.
- No scanned-PDF OCR, bank connectivity, automatic statement completeness detection, or receipt-level merchant verification.
- Recurrence requires enough dated observations and only covers supported cadences.
- Gemini API use was not live-tested; it remains disabled unless separately configured.
- The current UI is a dashboard with workflow tabs, not separate authenticated routes for every product area.
- Public production URL and deployed end-to-end journey remain pending hosting/database setup.
