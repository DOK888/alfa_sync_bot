import os
import json
import hashlib
from datetime import datetime, timedelta
from pytz import timezone
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

tz = timezone('Asia/Yekaterinburg')

CALENDARS = {
    "tetrika": "bb10c775e5ffd28df5255f2d6f82a5ccde3f98b38e7950ff696225d6a1eb17b4@group.calendar.google.com",
    "wellkid": "e37c23f1b18c4941418e715caab405fc25f40579a171e9b682c3ed75a80d9ff8@group.calendar.google.com"
}

def get_calendar_service():
    # Если запуск внутри докера, путь будет /workspace/auth/credentials.json или относительный
    creds_path = 'auth/credentials.json'
    if not os.path.exists(creds_path):
        print("Не найден файл credentials.json. Синхронизация с Google отменена.")
        return None
        
    creds = Credentials.from_service_account_file(
        creds_path,
        scopes=['https://www.googleapis.com/auth/calendar']
    )
    return build('calendar', 'v3', credentials=creds)

def generate_uid(school, date_str, start_time, group):
    s = f"{school}_{date_str}_{start_time}_{group}"
    return hashlib.md5(s.encode('utf-8')).hexdigest()

def sync_calendars():
    service = get_calendar_service()
    if not service:
        return

    data_file = "/vault/AlfaCRM/data/alfa_data_parsed.json"
    if not os.path.exists(data_file):
        data_file = "auth/alfa_data_parsed.json"
        
    if not os.path.exists(data_file):
        print("Файл alfa_data_parsed.json не найден. Ждем парсинга...")
        return

    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Определяем окно синхронизации по текущей дате (с 1 числа текущего до конца следующего)
    now = datetime.now(tz)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Для API Google даты нужны в ISO формате (RFC3339)
    time_min = start_of_month.isoformat()
    # Возьмем окно на 3 месяца вперед для верности
    time_max = (start_of_month + timedelta(days=90)).isoformat()

    for school_name, cal_id in CALENDARS.items():
        if school_name not in data:
            continue
            
        print(f"\\n--- Синхронизация {school_name} с Google Календарем ---")
        lessons = data[school_name].get('lessons', [])
        
        # 1. Получаем ВСЕ текущие события из Google Календаря в этом окне
        try:
            events_result = service.events().list(
                calendarId=cal_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
        except Exception as e:
            print(f"Ошибка получения календаря {school_name}: {e}")
            continue

        existing_events = events_result.get('items', [])
        
        # Словарь существующих событий по нашему custom UID
        # (Мы будем хранить наш UID в description, чтобы не усложнять с extendedProperties)
        google_events_by_uid = {}
        for event in existing_events:
            desc = event.get('description', '')
            # Ищем маркер UID: [UID:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx]
            if '[UID:' in desc:
                uid = desc.split('[UID:')[1].split(']')[0]
                google_events_by_uid[uid] = event

        # 2. Обрабатываем уроки из JSON
        processed_uids = set()
        for lesson in lessons:
            try:
                date_str = lesson['date']
                start_time = lesson['start']
                end_time = lesson['end']
                group = lesson['group']
                topic = lesson.get('final_topic', '')
                
                uid = generate_uid(school_name, date_str, start_time, group)
                processed_uids.add(uid)
                
                # Подготавливаем данные события
                start_dt = tz.localize(datetime.strptime(f"{date_str} {start_time}", "%d.%m.%Y %H:%M"))
                end_dt = tz.localize(datetime.strptime(f"{date_str} {end_time}", "%d.%m.%Y %H:%M"))
                
                event_body = {
                    'summary': group,
                    'description': f"{topic}\\n\\n---\\n[UID:{uid}]",
                    'start': {
                        'dateTime': start_dt.isoformat(),
                        'timeZone': 'Asia/Yekaterinburg',
                    },
                    'end': {
                        'dateTime': end_dt.isoformat(),
                        'timeZone': 'Asia/Yekaterinburg',
                    },
                }
                
                if uid in google_events_by_uid:
                    # Проверяем, нужно ли обновить (сравниваем summary и description)
                    existing = google_events_by_uid[uid]
                    if existing.get('summary') != event_body['summary'] or existing.get('description') != event_body['description']:
                        service.events().update(calendarId=cal_id, eventId=existing['id'], body=event_body).execute()
                        print(f"Обновлено: {date_str} {start_time} {group}")
                else:
                    # Создаем новое
                    service.events().insert(calendarId=cal_id, body=event_body).execute()
                    print(f"Добавлено: {date_str} {start_time} {group}")
            except Exception as e:
                print(f"Ошибка обработки урока {lesson.get('group')}: {e}")

        # 3. Удаляем события, которые есть в Google, но пропали из JSON (отменены)
        # Удаляем только те, что относятся к текущему или будущим месяцам, чтобы не удалять историю до запуска скрипта.
        for uid, event in google_events_by_uid.items():
            if uid not in processed_uids:
                # Проверяем дату события перед удалением
                event_start_str = event['start'].get('dateTime', event['start'].get('date'))
                if event_start_str:
                    event_start = datetime.fromisoformat(event_start_str.replace('Z', '+00:00'))
                    # Если событие старше 1 числа текущего месяца, не трогаем (история)
                    if event_start.astimezone(tz) >= start_of_month:
                        service.events().delete(calendarId=cal_id, eventId=event['id']).execute()
                        print(f"Удалено отмененное событие: {event.get('summary')} ({event_start_str})")

if __name__ == "__main__":
    sync_calendars()
