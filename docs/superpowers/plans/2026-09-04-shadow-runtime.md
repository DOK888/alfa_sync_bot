# Shadow Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a runnable, non-notifying shadow service that imports legacy JSON into a separate SQLite database.

**Architecture:** A pure legacy-report adapter normalizes only recognised schedule fields and calls the existing SQLite reconciliation code. A small CLI owns paths and output. Docker runs this CLI periodically with a read-only legacy-data mount and an independent state mount.

**Tech Stack:** Python 3.11+, SQLite, standard library `json`/`argparse`, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-09-04-shadow-runtime-design.md`

## Global Constraints

- Do not read, commit, copy or log `.env.txt`, auth files, Telegram tokens, cookies, runtime JSON content from production, or personal data.
- Shadow mode performs no Telegram, Google Calendar, CRM or legacy-data writes.
- Use deterministic fallback lesson identities only until a direct CRM ID adapter exists.
- All new behavior follows TDD and passes the full unit suite.

---

### Task 1: Legacy report normalization

**Files:**
- Create: `src/alfa_sync_bot/legacy_report.py`
- Test: `tests/test_legacy_report.py`

**Interfaces:**
- Produces: `parse_legacy_report(payload: dict[str, object]) -> dict[str, list[LessonSnapshot]]`
- Produces: `is_complete_source(payload: dict[str, object], school: str) -> bool`

- [ ] Write a failing test with synthetic `tetrika` and `wellkid` lessons and assert timezone-aware EKB snapshots.
- [ ] Run the test and confirm the missing module failure.
- [ ] Implement date/time/status normalization and deterministic fallback IDs.
- [ ] Run the focused and full test suites.
- [ ] Commit the task.

### Task 2: Shadow import service

**Files:**
- Create: `src/alfa_sync_bot/shadow.py`
- Test: `tests/test_shadow.py`

**Interfaces:**
- Produces: `run_shadow_import(report_path: Path, database_path: Path) -> ShadowResult`
- Consumes: `parse_legacy_report`, `is_complete_source`, `apply_migrations`, `reconcile_snapshot`.

- [ ] Write failing tests that prove malformed reports make no deletion and repeated imports make no changes.
- [ ] Run the tests and confirm the missing module failure.
- [ ] Implement separate-source reconciliation and aggregate-only result data.
- [ ] Run focused and full suites.
- [ ] Commit the task.

### Task 3: CLI and shadow Docker configuration

**Files:**
- Create: `src/alfa_sync_bot/__main__.py`, `Dockerfile`, `docker-compose.shadow.yml`, `.env.example`
- Modify: `README.md`, `pyproject.toml`
- Test: `tests/test_cli.py`

**Interfaces:**
- Command: `python -m alfa_sync_bot shadow --report PATH --database PATH`
- The command exits nonzero for a missing report and never imports Telegram.

- [ ] Write a failing CLI test for a synthetic report and an independent state path.
- [ ] Run it and confirm the command entrypoint failure.
- [ ] Implement the CLI, minimal image and non-notifying Compose service.
- [ ] Document the server-side `.env` placement and one-shot shadow command without exposing values.
- [ ] Run all tests and static Docker/Compose validation.
- [ ] Commit the task.

### Task 4: Server shadow rollout

**Files:**
- No production-source modifications.

- [ ] Use a separate approved JIT to copy the new release archive beside the current release.
- [ ] Verify the legacy report path exists without reading its content.
- [ ] Create an independent state directory and a read-only report mount.
- [ ] Run one shadow import, compare aggregate counts only, then start the periodic shadow service with no Telegram token.
- [ ] Verify no port `8123` or Telegram polling conflict, then revoke JIT.
