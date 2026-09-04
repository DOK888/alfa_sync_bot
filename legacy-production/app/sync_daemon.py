import asyncio
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer
import schedule
import time
from playwright.async_api import async_playwright
from ics import Calendar, Event
import os
import json
import re
from datetime import datetime, timedelta
from pytz import timezone
import google_sync

tz = timezone('Asia/Yekaterinburg')

def log_error(msg):
    save_dir = "/vault/AlfaCRM/data" if os.path.exists("/vault") else "auth"
    err_path = f"{save_dir}/errors.json"
    errors = []
    if os.path.exists(err_path):
        try:
            with open(err_path, "r", encoding="utf-8") as f:
                errors = json.load(f)
        except: pass
    errors.append({"time": datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S'), "msg": msg})
    with open(err_path, "w", encoding="utf-8") as f:
        json.dump(errors, f, ensure_ascii=False, indent=2)

class ICSHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Content-type', 'text/calendar; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        super().end_headers()

def run_server():
    port = 8123
    server = HTTPServer(('0.0.0.0', port), ICSHandler)
    server.serve_forever()


async def fetch_lessons_via_new_api(page, base_url, school_name, start_date, end_date):
    """
    Новый API (июль 2026+): /calendar/events
    Возвращает уроки для указанного диапазона дат.
    Новый API поддерживает view=week/day/month, но мы будем разбивать на недели.
    """
    lessons_all = []
    
    # Определяем base_path из URL профиля (teacher/1 или company/1)
    calendar_base = await page.evaluate('''() => {
        let links = Array.from(document.querySelectorAll('a[href*="/calendar"]'));
        for (let el of links) {
            let href = el.getAttribute('href');
            if (href.includes('/teacher/') || href.includes('/company/')) {
                return href.replace('/index', '').split('?')[0];
            }
        }
        return null;
    }''')
    
    if not calendar_base:
        print(f"[{school_name}] Не найдена ссылка на календарь, используем /teacher/1/calendar")
        calendar_base = "/teacher/1/calendar"
    
    # Запрашиваем данные за весь диапазон (API поддерживает произвольные даты)
    events_url = f"{base_url.rstrip('/')}{calendar_base}/events?start={start_date}&end={end_date}&group_by=room&view=week"
    print(f"[{school_name}] NEW API URL: {events_url}")
    
    try:
        await page.goto(events_url, timeout=15000)
        await page.wait_for_timeout(2000)
        
        json_text = await page.evaluate('() => document.body.innerText')
        data = json.loads(json_text)
        lessons_all = data.get('collection', [])
        total = data.get('total', len(lessons_all))
        print(f"[{school_name}] NEW API: получено {len(lessons_all)} уроков (total={total})")
        return lessons_all, "new"
    except Exception as e:
        print(f"[{school_name}] NEW API ошибка: {e}")
        return [], None


async def fetch_lessons_via_old_api(page, base_url, school_name, start_date, end_date):
    """
    Старый API (до июля 2026): /calendar/fetch
    Может быть выпилен в любой момент — используется как fallback.
    """
    calendar_base = await page.evaluate('''() => {
        let links = Array.from(document.querySelectorAll('a[href*="/calendar"]'));
        for (let el of links) {
            let href = el.getAttribute('href');
            if (href.includes('/teacher/') || href.includes('/company/')) {
                return href.replace('/index', '').split('?')[0];
            }
        }
        return null;
    }''')
    
    if not calendar_base:
        calendar_base = "/teacher/1/calendar"
    
    lessons_all = []
    page_num = 1
    
    while True:
        fetch_url = f"{base_url.rstrip('/')}{calendar_base}/fetch?start={start_date}&end={end_date}&page={page_num}"
        print(f"[{school_name}] OLD API (fallback) URL: {fetch_url}")
        
        try:
            await page.goto(fetch_url, timeout=15000)
            await page.wait_for_timeout(2000)
            
            json_text = await page.evaluate('() => document.body.innerText')
            data = json.loads(json_text)
            lessons = data.get('collection', [])
            
            if not lessons:
                break
                
            lessons_all.extend(lessons)
            
            total = data.get('total', 0)
            if len(lessons_all) >= total or len(lessons) == 0:
                break
                
            page_num += 1
        except Exception as e:
            print(f"[{school_name}] OLD API ошибка на странице {page_num}: {e}")
            break
            
    print(f"[{school_name}] OLD API: получено {len(lessons_all)} уроков")
    return lessons_all, "old"


def parse_customers(customers_raw):
    """
    Парсит учеников из JSON. Поддерживает оба формата:
    - Старый API: dict {"id": "Имя_uuid"}
    - Новый API: list ["Имя_uuid", ...]
    """
    students = []
    
    if isinstance(customers_raw, dict):
        names_list = list(customers_raw.values())
    elif isinstance(customers_raw, list):
        # Новый формат: список строк или словарей
        names_list = []
        for c in customers_raw:
            if isinstance(c, str):
                names_list.append(c)
            elif isinstance(c, dict) and 'name' in c:
                names_list.append(c['name'])
    else:
        return students
    
    for raw_name in names_list:
        # Имя обычно идет до подчеркивания: "Кира_d21ddb7b..."
        clean_name = raw_name.split('_')[0].strip()
        # Убираем цифры и дефисы в начале (напр. "28614-Марина")
        clean_name = re.sub(r'^\d+-', '', clean_name)
        # Убираем HTML если есть
        clean_name = re.sub(r'<[^>]+>', '', clean_name)
        if clean_name:
            students.append(clean_name)
    
    return students


def get_status(lesson, api_version):
    """
    Определяет статус урока. Поддерживает оба формата:
    - Старый API: status = "1"/"2"/"3"
    - Новый API: status_label = "Запланирован"/"Отменен"/"Проведен" + classNames
    """
    # Пробуем числовой статус (работает для обоих API)
    status_num = str(lesson.get('status', ''))
    if status_num == '2':
        return 'cancelled'
    if status_num == '3':
        return 'conducted'
    if status_num == '1':
        return 'planned'
    
    # Для нового API — по classNames или status_label
    class_names = lesson.get('classNames', [])
    if 'status3' in class_names:
        return 'conducted'
    if 'status2' in class_names:
        return 'cancelled'
    if 'status1' in class_names:
        return 'planned'
    
    label = lesson.get('status_label', '').lower()
    if 'проведен' in label:
        return 'conducted'
    if 'отменен' in label:
        return 'cancelled'
    if 'запланирован' in label:
        return 'planned'
    
    return 'planned'  # По умолчанию


async def scrape_school(url, state_file, school_name):
    lessons_raw = []
    salary_text = ""
    api_version = None
    
    if not os.path.exists(state_file):
        print(f"[{school_name}] Файл сессии не найден: {state_file}")
        return [], 0, 0, 0, 0, 0, 0, salary_text
        
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=state_file)
        page = await context.new_page()
        
        try:
            # Шаг 0: Заходим на главную
            print(f"[{school_name}] Заходим на {url}")
            await page.goto(url)
            await page.wait_for_timeout(3000)
            
            current_url = page.url
            print(f"[{school_name}] Текущий URL: {current_url}")
            
            # Проверяем, не перекинуло ли на логин или не открылась ли форма логина
            is_login_form = await page.locator('input[type="password"]').count() > 0
            if 'login' in current_url.lower() or 'auth' in current_url.lower() or is_login_form:
                err_msg = f"[{school_name}] ОШИБКА: Сессия протухла! Требуется авторизация. Текущий URL: {current_url}"
                print(err_msg)
                log_error(err_msg)
                await browser.close()
                return [], 0, 0, 0, salary_text
            
            # Даты: с 1 числа текущего месяца до конца следующего
            now = datetime.now(tz)
            start_date = now.replace(day=1).strftime("%Y-%m-%d")
            next_month = now.replace(day=28) + timedelta(days=35)
            end_date = next_month.replace(day=28).strftime("%Y-%m-%d")
            print(f"[{school_name}] Диапазон дат: {start_date} — {end_date}")
            
            # Стратегия: сначала новый API, потом fallback на старый
            lessons_raw, api_version = await fetch_lessons_via_new_api(page, url, school_name, start_date, end_date)
            
            if not lessons_raw:
                print(f"[{school_name}] Новый API пуст или недоступен, пробуем старый...")
                # Возвращаемся на главную (чтобы подобрать ссылку на календарь)
                await page.goto(url)
                await page.wait_for_timeout(2000)
                lessons_raw, api_version = await fetch_lessons_via_old_api(page, url, school_name, start_date, end_date)
            
            if not lessons_raw:
                print(f"[{school_name}] ВНИМАНИЕ: Ни один API не вернул уроков!")
            else:
                print(f"[{school_name}] Успешно получено {len(lessons_raw)} уроков через {api_version} API")
            
            # Для Wellkid - вытаскиваем плавающую зарплату через реестр
            if school_name == "wellkid":
                try:
                    await page.goto(url) # Возврат на главную в профиль
                    await page.wait_for_timeout(3000)
                    
                    reg_btn = page.locator('a:has-text("Реестр проведенных")')
                    if await reg_btn.count() > 0:
                        await reg_btn.first.click()
                        await page.wait_for_timeout(3000)
                        
                        await page.evaluate('''() => {
                            let selectAll = document.querySelector('thead input[type="checkbox"]');
                            if (selectAll) selectAll.click();
                            else {
                                document.querySelectorAll('tbody input[type="checkbox"]').forEach(cb => cb.click());
                            }
                        }''')
                        await page.wait_for_timeout(1000)
                        
                        salary_text = await page.evaluate("() => document.body.innerText")
                except Exception as e:
                    print(f"[WellKid] Ошибка при сборе зарплаты: {e}")

        except Exception as e:
            print(f"[{school_name}] Ошибка: {e}")
        finally:
            await browser.close()

    # Парсим JSON данные
    lessons_parsed = []
    group_topics = {}
    
    current_month = datetime.now(tz).month
    next_month_num = (current_month % 12) + 1
    
    current_earned = 0
    current_planned = 0
    next_planned = 0

    for l in lessons_raw:
        try:
            # Оба API возвращают start/end в формате "YYYY-MM-DD HH:MM:SS"
            start_str = l.get('start', '')
            end_str = l.get('end', '')
            
            if not start_str or not end_str:
                continue
            
            start_dt_moscow = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
            end_dt_moscow = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")
            
            # ПЛЮС 2 ЧАСА (Москва -> Екатеринбург)
            start_dt_ekb = start_dt_moscow + timedelta(hours=2)
            end_dt_ekb = end_dt_moscow + timedelta(hours=2)
            
            start_time = start_dt_ekb.strftime("%H:%M")
            end_time = end_dt_ekb.strftime("%H:%M")
            
            # Определяем статус (универсально для обоих API)
            status = get_status(l, api_version)
            if status == 'cancelled':
                continue
            
            # Тема: для wellkid не берем
            topic = "" if school_name == "wellkid" else l.get('topic', "").strip()
            
            title = l.get('title', '')
            title = re.sub(r'<[^>]+>', '', title)
            
            # Длительность: берём из JSON если есть, иначе из названия
            duration = l.get('duration')
            if not duration:
                duration = 90 if '90' in title else 60
            else:
                duration = int(duration)
            
            group_name = title.split('(')[0].strip()
            
            # Парсинг учеников (универсально для dict и list)
            students = parse_customers(l.get('customers', {}))
            
            lessons_parsed.append({
                "status": status,
                "date": start_dt_ekb.strftime("%d.%m.%Y"),
                "start": start_time,
                "end": end_time,
                "group": group_name,
                "students": students,
                "duration": duration,
                "topic": topic,
                "is_exact": True
            })
            
            if status == 'conducted' and topic:
                group_topics[group_name] = topic
                
            # Математика по месяцам
            lesson_date = start_dt_ekb
            cost = 1200 if duration == 90 else 800
            if school_name == 'wellkid':
                cost = 0
                # Если это ПМП/ППН или есть цифры в названии - это группа, ЗП не считаем автоматически
                if "ПМП" not in group_name and "ППН" not in group_name and not any(c.isdigit() for c in group_name):
                    cost = 400 if duration >= 60 else 200
            if lesson_date.month == current_month:
                if status == 'conducted':
                    current_earned += cost
                else:
                    current_planned += cost
            elif lesson_date.month == next_month_num:
                if status == 'planned':
                    next_planned += cost
                
        except Exception as e:
            print(f"[{school_name}] Ошибка парсинга урока: {e}")

    for l in lessons_parsed:
        if school_name != "wellkid":
            if l['status'] == 'planned':
                l['final_topic'] = "Прошлая тема: " + group_topics.get(l['group'], "(Нет данных)")
            else:
                l['final_topic'] = "Тема: " + l['topic']
        else:
            l['final_topic'] = "Урок WellKid"

    print(f"[{school_name}] Итого: {len(lessons_parsed)} уроков, заработано={current_earned}, план={current_planned}")
    return lessons_parsed, current_earned, current_planned, next_planned, salary_text

def generate_ics(lessons, filename, school_name):
    c = Calendar()
    for l in lessons:
        try:
            start_dt = tz.localize(datetime.strptime(f"{l['date']} {l['start']}", "%d.%m.%Y %H:%M"))
            end_dt = tz.localize(datetime.strptime(f"{l['date']} {l['end']}", "%d.%m.%Y %H:%M"))
            
            e = Event()
            e.name = l['group']
            e.begin = start_dt
            e.end = end_dt
            e.description = l['final_topic']
            
            safe_gr = l['group'].replace(' ', '_').lower()
            e.uid = f"{l['date']}_{l['start']}_{safe_gr}@{school_name}.s20"
            c.events.add(e)
        except: pass
                
    serialized = "".join(c.serialize_iter())
    serialized = serialized.replace("VERSION:2.0", "VERSION:2.0\\nX-PUBLISHED-TTL:PT15M\\nREFRESH-INTERVAL;VALUE=DURATION:P15M")
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(serialized)

def job():
    print(f"\n--- Запуск обновления: {datetime.now(tz).strftime('%Y-%m-%d %H:%M')} ---")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    t_data = loop.run_until_complete(scrape_school("https://tetrika.s20.online/", "auth/tetrika_state.json", "tetrika"))
    w_data = loop.run_until_complete(scrape_school("https://wellkid.s20.online/", "auth/wellkid_state.json", "wellkid"))
    
    generate_ics(t_data[0], "tetrika.ics", "tetrika")
    generate_ics(w_data[0], "wellkid.ics", "wellkid")
    
    os.makedirs("/vault/AlfaCRM/data", exist_ok=True) if os.path.exists("/vault") else None
    save_dir = "/vault/AlfaCRM/data" if os.path.exists("/vault") else "auth"
    
    report = {
        "tetrika": {
            "current_month_earned": t_data[1],
            "current_month_planned": t_data[2],
            "current_month_total": t_data[1] + t_data[2],
            "next_month_forecast": t_data[3],
            "lessons_count": len(t_data[0]),
            "lessons": t_data[0]
        },
        "wellkid": {
            "current_month_earned": w_data[1],
            "current_month_planned": w_data[2],
            "current_month_total": w_data[1] + w_data[2],
            "next_month_forecast": w_data[3],
            "salary_raw_text": w_data[4],
            "lessons_count": len(w_data[0]),
            "lessons": w_data[0]
        },
        "updated_at": datetime.now(tz).strftime('%Y-%m-%d %H:%M')
    }
    
    with open(f"{save_dir}/alfa_data_parsed.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("Данные успешно сохранены в alfa_data_parsed.json")
    
    # Запуск синхронизации Google Календаря
    try:
        google_sync.sync_calendars()
        print("Синхронизация с Google Календарем завершена.")
    except Exception as e:
        print(f"Ошибка синхронизации Google Календаря: {e}")

if __name__ == "__main__":
    job()
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    schedule.every(1).hours.do(job)
    while True:
        schedule.run_pending()
        save_dir = "/vault/AlfaCRM/data" if os.path.exists("/vault") else "auth"
        flag_path = f"{save_dir}/force_sync.flag"
        if os.path.exists(flag_path):
            try:
                os.remove(flag_path)
            except: pass
            print("\n--- ЗАПУСК ПО ЗАПРОСУ ИЗ ТГ БОТА ---")
            job()
        time.sleep(1)
