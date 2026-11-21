# Security and privacy

## Deployment boundary

The app does not implement authentication or tenant isolation. Local mode is intended for one trusted local user. For a public, unauthenticated URL, configure `ARTHATWIN_PUBLIC_DEMO=1` and use synthetic records only. The application filters reads/exports to `is_demo` records and blocks statement imports, profile/goal writes and data deletion. Category correction and subscription feedback remain available against fictional demo records and are shared among visitors.

Do not deploy personal mode to the public internet. A personal multi-user service needs authentication, ownership keys on every model/query, authorization tests, account recovery and a tenant-isolated database migration.

## Data handling controls

- File upload capped at 8 MiB; PDF capped at 150 pages; CSV capped at 10,000 rows; SMS capped at 50,000 characters.
- CSV/PDF/TXT file types are selected by suffix, with PDF signature validation and UTF-8 validation for SMS text files.
- Imports are staged, previewed and explicitly confirmed; previews expire after 24 hours.
- Duplicate fingerprints and a unique DB index prevent repeat imports.
- Destructive clear-data endpoint requires a confirmation header and is disabled in public demo mode.
- Demo seeding/reset only affects `is_demo` rows and requires a configured reset token in public demo mode.
- CORS credentials are disabled. Set the exact frontend origin in `CORS_ALLOWED_ORIGINS` for deployment.
- Secrets belong in backend environment configuration only. Never prefix secrets with `NEXT_PUBLIC_` or commit them.
- Imported descriptions are untrusted. Injection-like text is quarantined for classification and is not included in optional external AI tool results.
- External Google Gemini tool selection is disabled by default. It requires `EXTERNAL_AI_ENABLED=1`, a server-side API key, and one-question UI consent. The selected reporting month and the question (up to 2,000 characters) are sent to Google; stored profile, transaction rows, raw narration and calculated tool results remain on this server. The returned tool name and empty arguments are validated, the read-only tool executes locally, and the answer is composed locally from verified results. Errors or invalid calls fall back to the deterministic coach. The app does not intentionally log coach prompts.
- The finance coach blocks requests for specific securities and guaranteed investment returns, and performs no financial transactions.

## Known risks / unverified items

- Shared demo writes to synthetic classifications and subscription feedback are visible to all visitors.
- There is no rate limiting or account layer. Hosting should add request-rate controls for public traffic.
- No automated dependency vulnerability or secret scanner is configured in this repository. A source scan and credential audit were not run as part of the local build.
- Render was provisioned and the live frontend/API handshake was verified. The public `NEXT_PUBLIC_API_URL` and exact CORS origin were inspected; secret values remain masked and are not recorded in [DEPLOYMENT_REPORT.md](DEPLOYMENT_REPORT.md). CORS preflight returned 200 in current logs.
- Free compute platforms may have ephemeral storage, cold starts or database expiry. Do not use ephemeral SQLite for a product that promises durable profile/goal data.
- Optional Gemini calls were not sent during local tests.
- Gemini tool selection is tested with a local fake SDK response, not a live Gemini credential. Provider availability and model behavior remain unverified.
