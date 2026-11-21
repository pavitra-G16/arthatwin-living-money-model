# Hackathon Submission Details

## Product summary

ArthaTwin builds a transparent “living money model” from messy Indian bank exports. It previews and normalizes statement data, learns reusable merchant-category rules from corrections, highlights recurring payment evidence, and lets people explore how cashflow changes could affect goals.

## Links

- Live demo: https://arthatwin-living-money-model-2.onrender.com/
- Repository: https://github.com/pavitra-G16/arthatwin-living-money-model
- Backend health: https://arthatwin-living-money-model.onrender.com/api/health

## Demo video (60–90 seconds)

1. (0–10s) “ArthaTwin turns a noisy Indian bank statement into a model you can inspect—not a black-box score.” Show the synthetic-data label.
2. (10–25s) Load fictional sample data; point out INR cashflow, refunds/transfers, goals, and statement period.
3. (25–40s) Open a transaction and correct its merchant category. Explain that the correction becomes a reusable merchant rule.
4. (40–55s) Show recurring payment evidence and clarify that the app asks whether a service is used; it cannot observe app usage.
5. (55–75s) Change a what-if assumption and compare projected surplus/goal timing.
6. (75–90s) Open the monthly review and close: “These are modeled estimates from imported rows, not bank balances or financial advice.”

## Judge presentation (3 minutes)

- **0:00–0:25 — Problem:** “People get transaction exports in fragmented formats and noisy UPI descriptions; raw rows don’t explain what their month means.”
- **0:25–0:55 — Product:** Introduce ArthaTwin’s period-based cashflow model. Show the sample-data badge and one-click synthetic dataset.
- **0:55–1:25 — Data and learning:** Explain preview-before-save and correction-to-rule memory. Show evidence for a recurring payment rather than claiming to know usage.
- **1:25–1:55 — Planning:** Adjust income, rent, dining, or subscription assumptions and explain the deterministic projected change in surplus/goal timeline.
- **1:55–2:20 — Review and coach:** Show report/print view and deterministic coach explanation. State that Gemini is optional, consent-gated, and not used in this demo.
- **2:20–2:45 — Architecture and safeguards:** Next.js + FastAPI/SQLAlchemy; public mode shows synthetic records only. Acknowledge no authentication and ephemeral SQLite on this host.
- **2:45–3:00 — Close:** “ArthaTwin makes the logic inspectable: the user can review the source rows, assumptions, rules, and projected output.”

## Architecture summary

Next.js 16 / React 19 frontend → FastAPI API → SQLAlchemy persistence. CSV, SMS, and text-PDF importers normalize transaction records. A deterministic finance engine calculates period totals, recurring evidence, goal scenarios, and reports using INR decimal amounts. Optional Gemini tool calling is configured separately, bounded to read-only context, and requires user consent.

## LinkedIn launch post (draft)

Meet **ArthaTwin — Your Living Money Model**, our hackathon prototype for making everyday cashflow easier to understand.

It turns fictional or user-provided transaction exports into a transparent monthly picture, learns reusable merchant-category rules from corrections, spots recurring-payment evidence, and lets you test “what if?” changes against your goals.

The important part: every number is a model based on visible transactions and assumptions—not a claimed bank balance. Our public demo uses synthetic data only.

Try it: https://arthatwin-living-money-model-2.onrender.com/

#FinTech #PersonalFinance #AI #Hackathon

## Short LinkedIn alternative (draft)

We built ArthaTwin: a transparent living cashflow model for messy Indian transaction exports. Correct a merchant once, reuse that rule, inspect recurring-payment evidence, and test goal scenarios. Public demo uses synthetic data only: https://arthatwin-living-money-model-2.onrender.com/ #FinTech #AI

## Limitations and next steps

- No login, tenant isolation, or production-grade security.
- Public demo is synthetic-only; Render SQLite storage is ephemeral.
- No live bank connectivity, scanned-PDF OCR, or money movement.
- Gemini provider requests were not part of verification; deterministic fallback is available.
- Next steps: managed persistent database, authentication/tenant isolation, broader import fixtures, mobile/browser E2E, and judge feedback.

Posts above are drafts only and have not been published.
