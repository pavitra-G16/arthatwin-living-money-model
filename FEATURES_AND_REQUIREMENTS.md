# Official Requirements Compliance Audit

Statuses mean **PASS** = tested successfully for the stated scope; **PARTIAL** = implementation exists but a required part is untested or limited; **FAIL** = tested and broken/missing; **NOT VERIFIED** = insufficient evidence.

## Official problem requirements

| Ref | Status | Evidence and limits |
|---|---|---|
| A. Messy data ingestion | **PASS** | Backend preview flows tested with synthetic Indian UPI CSV, text-PDF, and SMS examples. Date/amount/direction/merchant extraction and suggested category assertions pass; invalid rows, missing SMS dates, dedupe, and quarantine have tests. Public shared demo correctly blocks personal imports. Scanned PDF OCR is unsupported and not required by this implementation. |
| B. Correction loop and learning | **PARTIAL** | Tests correct a category, persist a reusable rule across API requests, update unlocked matches, preserve user-locked rows, apply the rule to a later SMS preview, and repair old automatic synthetic categories. UI displays `MERCHANT_RULE`, `TRANSFER_RULE`, `LEARNED_RULE`, or `USER_LOCKED`. A process-restart/redeploy persistence test is outstanding; Render's SQLite is ephemeral. |
| C. Recurring payments | **PASS** | Dated cadence and price-change behavior are tested; Yes/No/Unsure feedback survives separate API requests. UI labels inferred cadence, evidence count, and qualitative confidence. Usage is never inferred from a payment. |
| D. Persistent financial profile | **PASS** | Existing API tests verify profile and goals survive subsequent requests. Values are labeled as user assumptions; transaction aggregates are separate. Persistence across Render redeploys is limited by the current ephemeral SQLite filesystem. |
| E. What-if goal planner | **PASS** | API tests reconcile a 30% dining reduction and rent increase against the baseline and goal timeline calculations. UI shows baseline, scenario, delta, and calculation assumptions. Values are estimates, not verified balances. |
| F. Spending drift nudges | **PASS** | Tests confirm meaningful category changes are suppressed unless both periods are user-confirmed complete; qualifying change text explains category, amount, percentage, and periods. |
| G. Monthly review report | **PARTIAL** | Report API values are tested against dashboard totals, including income, net expenses, observed savings, and modeled surplus. A print-only stylesheet was added, but a browser print/PDF output was not visually verified. |
| H. Financial safety | **PASS** | Tests cover investment recommendation guardrails, deterministic fallback/tool selection, narration-injection quarantine, and quarantine flagging. Optional Gemini is consent-gated and was not called in tests or live verification. No banking, securities, or money movement integration is claimed. |

## Synthetic November 2026 reconciliation

- `DEMO_ROWS` contains **16 rows total**: 2 in October and 14 in November. The dashboard's selected November count of 14 is therefore period-scoped, not a missing-row count.
- With merchant-first categories, November observed income is ₹85,000; refunds are ₹0; expenses after refunds are ₹34,006; observed net savings are ₹50,994.
- Modeled surplus is ₹44,172: ₹85,000 profile income − ₹32,000 profile fixed-cost assumption − ₹8,828 observed variable costs. The model excludes the ₹1,500 P2P debit and uses the larger profile fixed-cost assumption rather than double-counting ₹25,178 observed Housing + Utilities.
- A 30% dining reduction saves ₹534 (30% of ₹1,780), producing modeled surplus ₹44,706. A ₹5,000 rent increase produces ₹39,172. The simulator and report use the same baseline calculation.
- Netflix's observed ₹499→₹649 change is approximately +30.1%, displayed as +30%; latest monthly equivalent is ₹649 and annualized amount is ₹7,788. Cultfit is ₹1,499 monthly / ₹17,988 annualized. Both are low-confidence two-payment inferred patterns, not usage claims.

No totals are hardcoded into calculations; these figures are test expectations derived from the synthetic ledger and the current demo profile assumptions.

## Hackathon judging evidence

| Criterion | Weight | Evidence | Honest caveat |
|---|---:|---|---|
| Prototype and UX | 25% | Live dashboard, seeded fictional transactions, correction UI, simulator, report, mobile-first utility classes | No full browser E2E or device-matrix audit was completed. |
| AI integration | 25% | Optional consented Gemini function calling with bounded tools; deterministic merchant rules and local coach fallback are distinct | No live Gemini request was made; rule learning is deterministic, not generative AI. |
| Problem understanding | 20% | UPI narration, statement preview, refunds/transfers separation, INR decimals, completeness gating | Real-bank format coverage remains limited to synthetic fixtures. |
| LinkedIn content and engagement | 15% | Draft launch posts/scripts exist in submission details | No post was published and engagement cannot be claimed. |
| Innovation and creativity | 15% | Correctable living cashflow model, reusable merchant memory, recurring evidence, goal scenario comparison | User validation and judge feedback remain outstanding. |

## Not verified / limitations

- Browser-driven PDF printing, responsive mobile layout, and all hosted UI journeys are not fully verified.
- Current public demo is synthetic-only but shared; no login or tenant isolation exists.
- Render's current SQLite database is on ephemeral storage. Cross-redeploy persistence is not guaranteed.
- The external Gemini provider call was not exercised; scanned PDF OCR and live bank integration are absent.
