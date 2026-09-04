# Telegram Replacement Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the legacy long-polling handler for the same Telegram bot account with a read-only availability responder backed by shadow SQLite.

**Architecture:** A minimal standard-library Telegram API adapter supplies updates to a runtime that relies on existing parser and message-service behavior. A persisted update offset in SQLite prevents duplicate replies after restarts. Deployment runs the new poller only after legacy polling is stopped.

**Tech Stack:** Python 3.11+, SQLite, urllib, Docker Compose, unittest.

**Spec:** `docs/superpowers/specs/2026-09-04-telegram-replacement-runtime-design.md`

## Global Constraints

- Never read, print, copy, commit or upload Telegram tokens, secrets, real messages or schedule data.
- Do not create, accept or modify lessons.
- No new public port or network exposure.
- Only one Telegram long-polling process may run for the token.

---

### Task 1: Persisted runtime state

**Files:**
- Modify: `src/alfa_sync_bot/database.py`
- Test: `tests/test_database.py`

**Interfaces:**
- Produces: `get_runtime_state(connection: sqlite3.Connection, key: str) -> str | None` and `set_runtime_state(connection: sqlite3.Connection, key: str, value: str) -> None`.

- [ ] Write a failing test that migration creates state storage and an inserted offset is returned after reopening the database.
- [ ] Run `python -m unittest tests.test_database -v` and confirm the new test fails because state access is missing.
- [ ] Add one additive migration and minimal state helpers.
- [ ] Re-run the focused test and confirm it passes.
- [ ] Commit the focused database change.

### Task 2: Telegram update runtime

**Files:**
- Create: `src/alfa_sync_bot/telegram_api.py`
- Create: `src/alfa_sync_bot/telegram_runtime.py`
- Test: `tests/test_telegram_runtime.py`

**Interfaces:**
- Consumes: `analyze_replacement_text(text, connection) -> str`, `get_runtime_state`, `set_runtime_state`.
- Produces: `process_updates(client, connection) -> int`, where the return value is the next Telegram offset.

- [ ] Write a failing test with a complete fake update that asserts one informational reply and durable offset `update_id + 1`.
- [ ] Run `python -m unittest tests.test_telegram_runtime -v` and confirm it fails because the runtime is missing.
- [ ] Implement the smallest API protocol and runtime; skip unrecognised/non-text updates and update the offset without replying.
- [ ] Add a failing restart test proving an already-stored offset is not replied to again, then implement the minimal poll boundary.
- [ ] Run the focused test module and confirm it passes.
- [ ] Commit the runtime change.

### Task 3: CLI and Compose service

**Files:**
- Modify: `src/alfa_sync_bot/__main__.py`
- Create: `docker-compose.telegram.yml`
- Modify: `.env.example`
- Modify: `README.md`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `TELEGRAM_BOT_TOKEN` from environment and `--database PATH`.
- Produces: `python -m alfa_sync_bot telegram --database PATH` long-polls without printing message text.

- [ ] Write a failing CLI test for a missing `TELEGRAM_BOT_TOKEN` returning a nonzero status without echoing environment content.
- [ ] Run `python -m unittest tests.test_cli -v` and confirm it fails for the missing command.
- [ ] Implement the CLI mode and compose service with no `ports`, state mount, `restart: unless-stopped`, and no legacy report write mount.
- [ ] Run focused and full test suites.
- [ ] Commit the runnable service.

### Task 4: Controlled production cutover

**Files:**
- Modify: `docs/superpowers/plans/2026-09-04-telegram-replacement-runtime.md`

- [ ] Build and verify the service locally without a token.
- [ ] With separate JIT approval, back up the old container configuration, stop the legacy poller, start the new service with the same server-only token, and check only metadata.
- [ ] Send one user test message and confirm a reply in Telegram; no logs or database content are collected.
- [ ] On failure, stop the new service and start the old container.
- [ ] Revoke JIT and confirm privileged access is denied.
