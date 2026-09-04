# Telegram Replacement Runtime Design

## Goal

Replace the legacy Telegram polling process for the existing bot account while retaining the same token and keeping the legacy report importer separate. The new runtime reads only the shadow SQLite schedule and sends an availability report for recognised replacement messages.

## Boundaries

- The Telegram account and token remain the existing ones. The token is supplied only at runtime with `TELEGRAM_BOT_TOKEN`; it is never read, printed, committed or copied by the project.
- Exactly one process polls Telegram: the old container is stopped before the new Telegram service starts. The shadow importer keeps running because it does not poll Telegram.
- The runtime never creates, accepts or marks lessons. It reads `shadow.sqlite3` and sends an informational reply only when at least one non-struck replacement offer is parsed.
- It ignores non-text updates and unrecognised text without replying.
- Its long-polling offset is stored in the shadow SQLite database, making retries idempotent after restart.

## Components

- `telegram_api.py`: small standard-library Telegram HTTP client and a testable protocol boundary.
- `telegram_runtime.py`: receives updates, parses offer text, calls `analyze_replacement_text`, sends one reply and persists the processed update offset.
- `database.py`: one additive migration for a `runtime_state` key/value table; no existing lesson data changes.
- `__main__.py`: `telegram` CLI mode accepts a database path and reads `TELEGRAM_BOT_TOKEN` only when run.
- `docker-compose.telegram.yml`: isolated replacement service, no public port, state mounted read/write, token passed from a server-only `.env`.

## Failure and rollback

Missing token or unreadable database stops the new service before polling. Temporary Telegram API errors are logged without message content and retried. Before switch, the legacy release is preserved and its container definition remains available. Rollback is: stop the new Telegram service and start the legacy `alfa_sync_bot` container; no schedule data is changed by either step.

## Validation

Synthetic unit tests cover parsing/reply behavior, ignored messages, update-offset persistence, restart idempotency and missing-token failure. Server validation uses only container status, network/port metadata and a deliberately sent test message; no logs, tokens, schedules or SQLite rows are displayed.
