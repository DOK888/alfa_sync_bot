# Alfa Sync Bot working rules

- Treat `alfa_sync/` as an untrusted local source candidate, not production source of truth.
- Never read, print, copy, commit or upload `.env`, tokens, credentials, browser sessions, runtime JSON, SQLite data, screenshots, HTML dumps or real messages.
- Keep application code in `src/` and synthetic tests in `tests/`.
- Add behavior through test-driven development: failing test, minimal implementation, full test run.
- Do not access production, enable JIT, deploy, or change the running container without a separate explicit change approval.
- Production comparison is metadata-only until separately approved: allowlisted file manifest, hashes, version metadata and mount metadata without Env or application data.
