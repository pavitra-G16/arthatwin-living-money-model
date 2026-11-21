# ArthaTwin — Personal Finance Coach with a Living Money Model

**ArthaTwin** is a deterministic-first, neuro-symbolic personal finance twin built for the **Product Space Agentic AI Hackathon**. Unlike static budgeting apps that stop at pie charts, ArthaTwin maintains a persistent, self-updating model of your cashflow, recurring obligations, learned categorization rules, and goal timelines.

## Architecture & Key Capabilities
1. **Multi-Format Messy Ingestion (`/backend/engine.py`)**: Parses Indian bank PDF statements (`pdfplumber`), arbitrary CSV headers (`pandas`), and raw UPI/bank SMS dumps (filtering out OTPs and promotional noise).
2. **Prompt Injection Quarantine**: Detects and strips adversarial instructions embedded inside UPI narrations before any LLM evaluation.
3. **Neuro-Symbolic Rule-Learning Loop**: User category corrections compile into persistent, user-locked deterministic rules (`LearnedRule`) that retroactively update matching records and execute with 0ms latency on future imports.
4. **Subscription Creep & Review Engine**: Flags stepped price hikes (e.g., `+30%` jump) and surfaces high-cost recurring charges for user confirmation without fabricating app-usage claims.
5. **Deterministic What-If Simulator ("Time-Tax" Engine)**: Pure Python cashflow math translates lifestyle changes (`-30% Dining Out`, `Rent Hike`, `Cancel Unused Subs`) into exact days saved or lost on financial goals.
6. **Hard-Guardrailed AI Coach**: Pre-flight intent checks block specific stock, mutual fund, or crypto recommendations while providing educational cashflow guidance grounded strictly in verified ledger numbers.
