# API reference

Base URL locally: `http://127.0.0.1:8000/api`. The service exposes FastAPI's OpenAPI schema at `/openapi.json` and interactive docs at `/docs` when running.

| Method and route | Purpose |
| --- | --- |
| `GET /health` | Health/status and deployment mode. |
| `POST /seed-demo`, `POST /demo/reset` | Seed or clear only synthetic demo records; protected by `X-Demo-Reset-Token` when configured. |
| `GET /profile`, `POST /profile`, `PATCH /profile` | Read or update one financial profile. Public demo blocks profile writes. |
| `POST /goals`, `DELETE /goals/{goal_id}` | Create/update or delete a goal. Public demo blocks goal writes. |
| `POST /subscriptions/feedback` | Save `yes`, `no` or `unsure` usage feedback for a recurring candidate. |
| `POST /ingest/file/preview` | Upload CSV, text PDF or UTF-8 `.txt` SMS; returns parsed rows and issues. |
| `POST /ingest/sms/preview` | Preview pasted SMS text. |
| `POST /ingest/confirm` | Save selected preview rows; body includes `preview_id`, optional `accepted_rows`, optional `date_overrides`. |
| `GET /transactions?month=YYYY-MM` | Read transactions, optionally month-scoped. |
| `GET /transactions/{id}/matches?category=...` | Preview actual unlocked merchant match count before correction. |
| `POST /transactions/{id}/correct` | Correct category and persist a merchant rule. |
| `GET /rules`, `PATCH /rules/{id}` | List rules; revise category or enable/disable rule. |
| `GET /dashboard?month=YYYY-MM` | Selected-month summary, goals, ledger rows, recurring alerts, nudges and quality warnings. |
| `POST /simulate` | Deterministic scenario. Supports `dining_cut_pct`, `rent_change`, `extra_income` (positive or negative), `cancel_unused_subs`, and `month`. |
| `POST /months/{month}/coverage` | Record user's statement completeness confirmation. |
| `GET /reports/monthly?month=YYYY-MM` | Period-scoped report data. |
| `POST /coach` | Coach request with `message`, optional `month`, and `allow_external_ai` defaulting false. |
| `GET /transactions/export.csv`, `GET /data/export.json` | Export current accessible dataset. |
| `DELETE /data` | Requires `X-Confirm-Delete: DELETE ARTHATWIN DATA`; disabled in public demo. |

FastAPI validation errors use standard `422` responses. Oversized upload: `413`; unsupported type: `415`; expired import preview: `410`; blocked public-demo writes: `403`. Import preview responses include `parsed_count`, `ignored_count`, `rejected_count`, `duplicate_count`, rows, row issues and an expiry period. Confirm responses report imported, duplicates, rejected rows and errors.
