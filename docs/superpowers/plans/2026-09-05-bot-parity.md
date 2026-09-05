# Bot Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the menu, useful schedule/finance views, and deduplicated schedule notifications for the existing Telegram bot account.

**Architecture:** The Telegram poller stays the sole Telegram API client. A persistent reply keyboard routes ordinary message text to read-only SQLite query/render functions. Each shadow import reconciles finance facts; the poller drains change events after a chat registers, which keeps the importer isolated from the token.

**Tech Stack:** Python 3.11+, SQLite, urllib, Docker Compose, unittest.

**Spec:** `docs/superpowers/specs/2026-09-05-bot-parity-design.md`

## Global Constraints

- Never read, print, copy, commit, or upload tokens, secrets, real messages, schedules, or SQLite data.
- Do not accept, create, edit, or mark CRM lessons.
- Keep one Telegram polling process and add no public port.
- Earned income is only a lesson whose CRM status is `conducted`.

---

### Task 1: Persistent menu and routing

**Files:**
- Modify: `src/alfa_sync_bot/telegram_api.py`
- Modify: `src/alfa_sync_bot/telegram_runtime.py`
- Test: `tests/test_telegram_runtime.py`

**Interfaces:** `send_message(chat_id: int, text: str, reply_markup: dict | None = None) -> None`; `process_updates(...) -> int | None`.

- [ ] Write failing tests that `/start` sends a reply keyboard and that `📅 На сегодня` routes to a schedule response without invoking replacement analysis.
- [ ] Run `python -m unittest tests.test_telegram_runtime -v`; confirm the tests fail because the current client lacks `reply_markup` and routing.
- [ ] Implement the smallest reply-keyboard payload and message router; preserve the existing replacement-analysis branch for other text.
- [ ] Run the focused tests and the complete test suite; confirm both pass.

### Task 2: Schedule and finance projections

**Files:**
- Create: `src/alfa_sync_bot/schedule_view.py`
- Create: `src/alfa_sync_bot/finance_projection.py`
- Create: `src/alfa_sync_bot/finance_view.py`
- Modify: `src/alfa_sync_bot/shadow.py`
- Test: `tests/test_schedule_view.py`
- Test: `tests/test_finance_projection.py`
- Test: `tests/test_telegram_runtime.py`

**Interfaces:** `render_schedule(connection, start_day, end_day) -> str`; `reconcile_income_accruals(connection) -> None`; `render_finance(connection, today) -> str`.

- [ ] Write failing schedule tests for active EKB lessons, empty days, and Monday--Sunday bounds.
- [ ] Write failing finance tests for 30/60/90-minute rules, a conducted lesson becoming earned, future planned totals, and cancellation removing a planned accrual.
- [ ] Run each focused module and confirm expected failures.
- [ ] Implement read-only schedule rendering and idempotent accrual reconciliation; call it at the end of each shadow import.
- [ ] Route `🗓 На неделю` and `💰 Мои финансы`; run focused and complete tests.

### Task 3: Registered-chat notifications

**Files:**
- Modify: `src/alfa_sync_bot/database.py`
- Create: `src/alfa_sync_bot/notifications.py`
- Modify: `src/alfa_sync_bot/telegram_runtime.py`
- Test: `tests/test_notifications.py`
- Test: `tests/test_telegram_runtime.py`

**Interfaces:** `register_chat(connection, chat_id) -> None`; `deliver_pending_notifications(connection, send) -> int`.

- [ ] Write failing tests that registration skips historical changes, a new change is delivered once, and a failed send does not create a delivery record.
- [ ] Run `python -m unittest tests.test_notifications -v`; confirm expected failures.
- [ ] Add one additive migration for registered chats and implement selection plus delivery recording inside SQLite transactions.
- [ ] Invoke notification draining after Telegram updates and after a no-update poll.
- [ ] Run the focused module and full suite.

### Task 4: Import request and deployment guidance

**Files:**
- Modify: `src/alfa_sync_bot/shadow.py`
- Modify: `src/alfa_sync_bot/telegram_runtime.py`
- Modify: `README.md`
- Test: `tests/test_shadow.py`
- Test: `tests/test_telegram_runtime.py`

**Interfaces:** `request_import(connection) -> None`; `consume_import_request(connection) -> bool`.

- [ ] Write failing tests that `🔄 Собрать данные сейчас` persists a request and the shadow worker consumes it once without exposing report content.
- [ ] Run focused tests and confirm expected failures.
- [ ] Implement state-based request/consumption and explain that it triggers the next safe legacy-report import, never CRM mutation.
- [ ] Build the Telegram and shadow images, run the full suite, inspect the staged diff for secrets, then commit only source/tests/docs.
