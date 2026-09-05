# Alfa Sync Bot

## Owner-only access repair

Telegram requires `TELEGRAM_ALLOWED_USER_ID`, a positive owner user ID, in the
server-only `.env.owner`. Missing/invalid configuration stops startup before
polling. Requests require both the sender ID and private chat ID to match the
owner. No user can claim ownership with `/start` or `Меню`. Notification delivery
filters by the configured owner even if other chats were registered previously;
old registration records are retained but cannot receive messages.

On Hermes, stop `alfa_sync_bot_v2_telegram` first. Fetch the fixed branch and run
`python3 scripts/prepare_owner_config.py /home/hermes/alfa_sync/app/tg_bot.py`.
The helper statically extracts only the legacy `ALLOWED_USER_ID` integer without
executing the legacy module or copying credentials. It refuses ambiguous values
and conflicting existing configuration. Then rebuild/recreate the Telegram
service. Do not roll back to the unauthenticated image; leave it stopped if the
repair cannot start. Collector configuration is not changed by this repair.

Tests cover foreign commands, replacement text, AI bypass prevention, group-chat
rejection, missing sender/configuration, and preexisting foreign subscriptions.

Новая проверяемая основа школьного Telegram-бота. Проект развивается отдельно от Homelab documentation repository и пока не подключён к production.

## Что уже заложено

- разбор даты, группы, длительности и времени замены;
- Telegram UTF-16 entities для зачёркнутых предложений и ссылок на группы;
- перевод времени `Europe/Moscow` в `Asia/Yekaterinburg`;
- проверка конфликтов полуоткрытыми интервалами;
- категории: свободно, условная альтернатива, доступно со сдвигом до 30 минут, недоступно и требует проверки;
- постоянное меню Telegram под строкой ввода: сегодня, неделя, финансы, отчёт, настройки ИИ и безопасный запрос импорта;
- текстовый ответ по заменам без кнопок принятия и без записи группы как принятой;
- SQLite migration для уроков, import runs, изменений, notification dedup и финансовых начислений;
- ставки 30/60/90 минут: 400/800/1200 рублей;
- неделя понедельник–воскресенье и корректная граница предыдущего месяца;
- read-only view `finance_events` как интерфейс для будущей системы личных финансов.
- идемпотентное сопоставление полных и неполных снимков CRM с diff `new/changed/deleted`;
- суммы за прошлый месяц, текущую неделю и будущие недели; заработанными становятся только уроки со статусом CRM `conducted`.
- уведомления о новых, изменённых и удалённых уроках после `/start`, с dedup в SQLite; старые изменения не рассылаются при первом запуске.
- файловая SQLite migration с проверенным backup и автоматическим rollback при ошибке.

Бот не создаёт урок из сообщения менеджера. Назначенный урок появляется только после следующего импорта из CRM.

## Shadow запуск

Первый запуск новой версии — только shadow. Он читает старый `alfa_data_parsed.json` и создаёт отдельную SQLite, но не запускает Telegram, Google Calendar или CRM браузер.

```powershell
$env:PYTHONPATH = 'src'
python -m alfa_sync_bot shadow --report C:\path\to\alfa_data_parsed.json --database .\state\shadow.sqlite3
```

На сервере применяется `docker-compose.shadow.yml`. Он не публикует порт, не монтирует `auth` и не использует Telegram token. Перед запуском на сервере создаётся отдельный `.env` из `.env.example` только со значением `SHADOW_STATE_DIR`.

## Telegram запуск

Это обновление того же бота и того же токена, а не второй Telegram-аккаунт. После `/start` бот показывает постоянное меню внизу чата. Он читает расписание только из shadow SQLite, показывает день/неделю/финансы, отвечает на распознанные незачёркнутые предложения замены и присылает только новые изменения расписания. Обычный текст он молча пропускает. Он не принимает и не создаёт уроки.

В серверном `.env` вручную указываются `SHADOW_STATE_DIR` и `TELEGRAM_BOT_TOKEN`; сам файл остаётся вне Git. Перед запуском нового polling-процесса старый `alfa_sync_bot` останавливают. Возврат простой: остановить `alfa_sync_bot_v2_telegram` и снова запустить старый контейнер.

## Структура

- `src/alfa_sync_bot/availability.py` — интервалы, конфликты и сдвиги;
- `src/alfa_sync_bot/replacement_parser.py` — детерминированный parser сообщения;
- `src/alfa_sync_bot/replacement_service.py` — перевод времени и сортировка результата;
- `src/alfa_sync_bot/rendering.py` — информационный Telegram-текст;
- `src/alfa_sync_bot/database.py` — SQLite migrations и сохранённая позиция Telegram updates;
- `src/alfa_sync_bot/lesson_sync.py` — diff и dedup снимков уроков;
- `src/alfa_sync_bot/finance.py` — календарные периоды и финансовые итоги;
- `src/alfa_sync_bot/finance_projection.py` — ставки и начисления, синхронизированные со статусами импортированных уроков;
- `src/alfa_sync_bot/finance_view.py` и `schedule_view.py` — Telegram-представления финансов и расписания;
- `src/alfa_sync_bot/notifications.py` — регистрация чата и доставка deduplicated уведомлений;
- `src/alfa_sync_bot/telegram_runtime.py` — read-only обработка Telegram updates;
- `src/alfa_sync_bot/telegram_api.py` — минимальный Telegram HTTP adapter;
- `tests/` — синтетические unit/integration tests без CRM и сети;
- `alfa_sync/` — локальный недоверенный кандидат, полностью исключённый из Git.

## Проверка

Windows PowerShell:

```powershell
$env:PYTHONPATH = 'src'
python -m unittest discover -s tests -v
```

В Codex используется bundled Python, если системный Python отсутствует.

## Следующие этапы

1. Расширить parser на дополнительные наблюдаемые Telegram-форматы.
2. После отдельного JIT сравнить локальный кандидат и production по безопасному manifest/hashes.
3. Подключить выбранные scraper и Telegram adapters, затем выполнить shadow migration и canary.
