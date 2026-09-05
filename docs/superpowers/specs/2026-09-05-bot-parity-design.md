# Bot Parity Design

## Goal

Restore the existing bot account as one useful bot: its persistent Telegram menu,
read-only schedule views, finance views derived from CRM facts, and quiet
notifications about schedule changes. Replacement analysis stays informational and
continues to use the same parser and optional Gemini fallback.

## Boundaries

- The bot never accepts, creates, edits, or marks a lesson in CRM.
- A conducted CRM lesson is the only source of an earned amount. Planned lessons
  are future estimates; cancelled and deleted lessons do not create income.
- A Telegram chat is registered when it uses `/start`. Changes that existed before
  registration are not sent as notifications.
- The menu is a Telegram reply keyboard below the input field, not action buttons
  below an individual availability message.
- Secrets, real schedules, message text, and SQLite files remain server-side.

## Components

- `telegram_api.py` sends `reply_markup` and receives ordinary message updates.
- `telegram_runtime.py` routes `/start` and the five Russian menu labels before
  passing other text to replacement analysis. It registers the chat and drains
  pending, deduplicated notifications on each polling pass.
- `schedule_view.py` queries active SQLite lessons for today or Monday--Sunday and
  renders a compact EKB schedule.
- `finance_projection.py` reconciles `income_accruals` after each shadow import:
  a rate is selected by duration and lesson date; conducted becomes earned at the
  lesson end; future planned remains planned; cancelled/deleted planned accruals
  are removed.
- `finance_view.py` formats the existing finance overview: previous-month earned,
  current-week earned, then future planned weeks.
- `notifications.py` selects unnotified lesson changes newer than a chat's
  registration watermark and records delivery only after a successful send.

## Telegram menu

`/start` and `Меню` send a persistent keyboard:

- `📅 На сегодня`
- `🗓 На неделю`
- `💰 Мои финансы`
- `📝 Написать отчет`
- `🔄 Собрать данные сейчас`

The first three are fully local SQLite reads. `Написать отчет` responds with an
honest status because the legacy report-writing logic is not present in the
candidate source. `Собрать данные сейчас` records an import request; the shadow
worker consumes it before its next normal interval and replies through its next
schedule notification if something changed.

## Notification flow

The shadow importer records a `lesson_changes` event only for a real new, changed,
or deleted lesson. The Telegram runtime later sends a compact message per import
batch to each registered chat and inserts `notification_deliveries`; retrying the
runtime does not resend it. Initial registration sets a watermark to the latest
event so historical imports never flood the chat.

## Rollback

Migrations are additive and use the existing SQLite backup/restore workflow.
Production rollback remains stopping `alfa_sync_bot_v2_telegram` and starting the
preserved `alfa_sync_bot`; the shadow database is never modified by menu actions.
