# Features, Requirements, and Judging Evidence

| Requirement | Implemented evidence | Status / caveat |
|---|---|---|
| CSV, text PDF, SMS ingestion | Backend parsers, preview/confirm endpoints, duplicate and invalid-row handling | Implemented; scanned PDF OCR is not supported. Full live upload journeys not E2E tested. |
| Automatic categories and reusable corrections | Merchant/category rules persist and apply to later matching imports | Implemented and covered by backend tests; UI flow needs deployed E2E verification. |
| Recurring detection and feedback | Cadence/amount evidence, price-change notes, Yes/No/Unsure feedback | Implemented; service usage is explicitly unknown. |
| Profile and goals | Monthly income/fixed-cost assumptions and goal model in API/database | Backend supports persistence; public demo blocks personal profile/goal writes. |
| What-if planning | Deterministic changes to income, dining, rent and subscriptions; displays modeled effects | Implemented in app; figures are projections, not bank balances. |
| Spending drift | Period comparison and statement-completeness gating | Implemented; needs suitable data in both periods. |
| Monthly report and exports | Period-scoped review plus print, CSV and JSON export routes/UI | Implemented; live exports not individually smoke-tested. |
| Guardrailed coach | Deterministic app-data tools; optional Gemini function calling with consent | Provider calls disabled/unverified in deployed demo. No investment picks or execution. |
| Public privacy | Synthetic-only mode, read/export filtering, disabled imports/profile-goal changes | Verified in public mode. No authentication or tenant isolation; do not enter private data. |

## Hackathon judging map

| Dimension | Weight | Strongest evidence | Remaining improvement |
|---|---:|---|---|
| Prototype UX | 25% | Live dashboard, seeded synthetic ledger, recurring insights, goals | Complete mobile and primary workflow browser testing. |
| AI integration | 25% | Explainable merchant-rule memory; bounded optional coach tools | Demonstrate consented live provider call only if credentials/policy permit; never label deterministic logic as generative AI. |
| Problem understanding | 20% | UPI narration parsing, refunds/transfers, statement completeness, INR decimal math | Broaden messy-bank fixtures and real-user research. |
| LinkedIn content | 15% | Drafts and demo narrative in submission guide | Owner must publish and collect engagement; no automated posting. |
| Innovation | 15% | Living cashflow model combining rule learning, recurring evidence and goal scenarios | Validate usefulness with judges/users. |

## Requirement gaps

The product is a demo rather than a secure multi-user financial service. Durable managed database, authentication, tenant isolation, full hosted E2E, broader mobile QA, OCR, and a real opt-in Gemini deployment remain future work.
