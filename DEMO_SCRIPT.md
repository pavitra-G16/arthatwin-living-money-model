# Three-minute ArthaTwin demo script

**0:00–0:20 — Frame it.** “ArthaTwin turns imported transactions and user-confirmed assumptions into a living monthly cashflow model. It is educational, does not execute payments, and does not recommend securities. This workspace is using synthetic sample data.” Show the synthetic-data label.

**0:20–0:45 — Dashboard.** Pick November 2026. Point out observed income/expenses and modeled surplus are different figures, the savings rate is based on imported credits, and completeness is not inferred from transaction dates. Show fictional goals and the recurring-payment review panel.

**0:45–1:15 — Import review.** In a local demo instance, choose the sample CSV or paste a synthetic bank SMS. Show the preview counts, parsed merchant/category, duplicate flag and row issue. Select rows and confirm. For public-demo mode, explain that statement uploads are blocked to protect the shared dataset.

**1:15–1:35 — Correction loop.** Change one synthetic merchant category. Show the actual unlocked match count confirmation, saved rule and affected rows. Disable and re-enable the rule to show persistent control. Explain user-locked rows remain protected.

**1:35–1:55 — Recurring review.** Show observed payment cadence and amount history. Mark a fictional service “No” only as a user statement. Explain this creates a scenario input; it is not proof of non-use.

**1:55–2:20 — Simulator.** Reduce dining, raise rent, or lower income and point to the computed change in modeled monthly surplus and recalculated goal timing. Read the assumptions below the result; note incomplete statements can make estimates misleading.

**2:20–2:40 — Coach.** Ask “How much did I spend in November?” Show the selected local tool and its verified result. If Gemini has been intentionally configured, obtain per-question consent before the optional call; otherwise show the deterministic response. Ask for a stock recommendation to demonstrate the guardrail.

**2:40–3:00 — Report and close.** Show the November report’s actual period, category breakdown and data-quality notes. Print/download it. Close with: “The coach explains deterministic cashflow calculations; profile assumptions and statement coverage are identified clearly, and the product does not move money.”

Use only fictional statements and data in any public recording. A deployed public URL is pending the provider/database setup documented in `DEPLOYMENT.md`.
