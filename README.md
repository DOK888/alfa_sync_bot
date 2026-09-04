# Alfa Sync Bot

Новая проверяемая основа школьного Telegram-бота. Проект развивается отдельно от Homelab documentation repository и пока не подключён к production.

## Что уже заложено

- разбор даты, группы, длительности и времени замены;
- Telegram entities для зачёркнутых предложений и ссылок на группы;
- перевод времени `Europe/Moscow` в `Asia/Yekaterinburg`;
- проверка конфликтов полуоткрытыми интервалами;
- категории: свободно, условная альтернатива, доступно со сдвигом до 30 минут, недоступно и требует проверки;
- текстовый ответ без кнопок и без записи группы как принятой;
- SQLite migration для уроков, import runs, изменений, notification dedup и финансовых начислений;
- ставки 30/60/90 минут: 400/800/1200 рублей;
- неделя понедельник–воскресенье и корректная граница предыдущего месяца;
- read-only view `finance_events` как интерфейс для будущей системы личных финансов.

Бот не создаёт урок из сообщения менеджера. Назначенный урок появляется только после следующего импорта из CRM.

## Структура

- `src/alfa_sync_bot/availability.py` — интервалы, конфликты и сдвиги;
- `src/alfa_sync_bot/replacement_parser.py` — детерминированный parser сообщения;
- `src/alfa_sync_bot/replacement_service.py` — перевод времени и сортировка результата;
- `src/alfa_sync_bot/rendering.py` — информационный Telegram-текст;
- `src/alfa_sync_bot/database.py` — первая SQLite migration;
- `src/alfa_sync_bot/finance.py` — календарные финансовые периоды;
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

1. Расширить parser на полный набор наблюдаемых Telegram-форматов.
2. Реализовать идемпотентный импорт lesson snapshots и field-level diff.
3. Добавить финансовые запросы за прошлый месяц, текущую и будущие недели.
4. После отдельного JIT сравнить локальный кандидат и production по безопасному manifest/hashes.
5. Подключить выбранные scraper и Telegram adapters, затем выполнить shadow migration и canary.
