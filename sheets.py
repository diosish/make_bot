import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from typing import Optional
import logging

from config import (
    GOOGLE_CREDENTIALS_FILE, SPREADSHEET_ID, FREELANCERS_SPREADSHEET_ID,
    USERS_SHEET, PROJECTS_SHEET, MAX_COMMENT_LENGTH, MAX_RATE_LENGTH, FREELANCERS_SHEET
)

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_client: Optional[gspread.Client] = None

# БАГ ИСПРАВЛЕН: был объявлен дважды, второе объявление перезаписывало первое
# и не включало колонки "активно" и "дата мероприятия"
PROJECTS_HEADERS = [
    "название проекта",
    "должность",
    "описание",
    "статус",
    "дата создания",
    "активно",
    "дата мероприятия",
]


def get_client() -> gspread.Client:
    global _client
    if _client is None:
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)
        _client = gspread.authorize(creds)
    return _client


def get_spreadsheet() -> gspread.Spreadsheet:
    return get_client().open_by_key(SPREADSHEET_ID)


def get_freelancers_spreadsheet() -> gspread.Spreadsheet:
    return get_client().open_by_key(FREELANCERS_SPREADSHEET_ID)


# ─────────────────────────────────────────
# USERS
# ─────────────────────────────────────────

def get_users_sheet() -> gspread.Worksheet:
    ss = get_spreadsheet()
    try:
        ws = ss.worksheet(USERS_SHEET)
    except gspread.exceptions.WorksheetNotFound:
        ws = ss.add_worksheet(title=USERS_SHEET, rows=1000, cols=10)
        ws.append_row(["telegram_user_id", "telegram_username", "фамилия", "имя", "должность",
                        "дата регистрации", "время уведомлений"])
    return ws


def find_user(telegram_user_id: int) -> Optional[dict]:
    ws = get_users_sheet()
    records = ws.get_all_records()
    for r in records:
        if str(r.get("telegram_user_id")) == str(telegram_user_id):
            return r
    return None


def save_user(telegram_user_id: int, username: str, last_name: str, first_name: str, position: str):
    """
    Сохраняет пользователя в таблицу Users.
    telegram_user_id и username должны быть актуальными данными из Telegram.
    """
    ws = get_users_sheet()
    records = ws.get_all_records()
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    headers = ws.row_values(1)

    # Преобразуем username в строку
    username_str = str(username) if username else ""
    # Преобразуем telegram_user_id в строку для записи
    user_id_str = str(telegram_user_id)

    logger.info(f"Saving user: id={user_id_str}, username={username_str}, name={last_name} {first_name}, position={position}")

    # Находим индекс колонки "время уведомлений" если она есть
    notify_col = None
    notify_val = ""
    if "время уведомлений" in headers:
        notify_col = headers.index("время уведомлений") + 1

    for idx, r in enumerate(records, start=2):
        if str(r.get("telegram_user_id")) == user_id_str:
            # Сохраняем значение времени уведомлений если оно есть
            if notify_col:
                try:
                    notify_val = ws.cell(idx, notify_col).value or ""
                except:
                    notify_val = ""

            # Обновляем только основные поля (A:E)
            ws.update(f"A{idx}:E{idx}", [[
                user_id_str, username_str, last_name, first_name, position
            ]])
            # Обновляем дату регистрации в колонке F
            ws.update_cell(idx, 6, now)
            # Возвращаем время уведомлений если оно было
            if notify_col and notify_val:
                ws.update_cell(idx, notify_col, notify_val)

            logger.info(f"User {user_id_str} updated")
            return

    ws.append_row([user_id_str, username_str, last_name, first_name, position, now, ""])
    logger.info(f"User {user_id_str} registered")


def get_users_by_position(position: str) -> list[dict]:
    ws = get_users_sheet()
    records = ws.get_all_records()
    return [r for r in records if r.get("должность") == position]


# БАГ ИСПРАВЛЕН: функция не была определена, вызов из projects.py падал с AttributeError
def save_notify_time(telegram_user_id: int, hour: int):
    ws = get_users_sheet()
    records = ws.get_all_records()
    headers = ws.row_values(1)

    # Убеждаемся, что колонка существует
    col_name = "время уведомлений"
    if col_name not in headers:
        new_col = len(headers) + 1
        ws.update_cell(1, new_col, col_name)
        headers.append(col_name)

    col_idx = headers.index(col_name) + 1

    for idx, r in enumerate(records, start=2):
        if str(r.get("telegram_user_id")) == str(telegram_user_id):
            ws.update_cell(idx, col_idx, hour)
            logger.info(f"Notify time saved: user={telegram_user_id} hour={hour}")
            return


# БАГ ИСПРАВЛЕН: функция не была определена, вызов из notifications.py ломал весь polling
def get_user_notify_hour(telegram_user_id: int) -> Optional[int]:
    ws = get_users_sheet()
    records = ws.get_all_records()
    for r in records:
        if str(r.get("telegram_user_id")) == str(telegram_user_id):
            val = r.get("время уведомлений", "")
            if val != "" and val is not None:
                try:
                    return int(val)
                except (ValueError, TypeError):
                    return None
    return None


# ─────────────────────────────────────────
# ПРОЕКТЫ
# ─────────────────────────────────────────

def get_projects_sheet() -> gspread.Worksheet:
    ss = get_spreadsheet()
    try:
        ws = ss.worksheet(PROJECTS_SHEET)
    except gspread.exceptions.WorksheetNotFound:
        ws = ss.add_worksheet(title=PROJECTS_SHEET, rows=500, cols=len(PROJECTS_HEADERS))
        ws.append_row(PROJECTS_HEADERS)
    return ws


def upsert_project(project_name: str, position: str, description: str, event_date: str = ""):
    ws = get_projects_sheet()
    records = ws.get_all_records()
    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    for idx, r in enumerate(records, start=2):
        if r.get("название проекта") == project_name and r.get("должность") == position:
            ws.update(f"C{idx}:G{idx}", [[
                description,
                "Открыт",
                now,
                True,
                event_date,
            ]])
            return

    ws.append_row([
        project_name,
        position,
        description,
        "Открыт",
        now,
        True,
        event_date,
    ])


def is_project_open(project_name: str, position: str) -> bool:
    ws = get_projects_sheet()
    records = ws.get_all_records()
    for r in records:
        if r.get("название проекта") == project_name and r.get("должность") == position:
            return r.get("статус", "").strip() == "Открыт"
    return False


def set_project_status(project_name: str, status: str) -> bool:
    ws = get_projects_sheet()
    records = ws.get_all_records()
    changed = False
    for idx, r in enumerate(records, start=2):
        if r.get("название проекта") == project_name:
            ws.update_cell(idx, 4, status)
            changed = True
    return changed


def get_projects_grouped() -> dict:
    ws = get_projects_sheet()
    records = ws.get_all_records()
    now = datetime.now()

    current = []
    future = []
    archive = []

    for r in records:
        active = str(r.get("активно", "")).lower() == "true"
        date_str = r.get("дата мероприятия", "")

        if not date_str:
            archive.append(r)
            continue

        try:
            event_date = datetime.strptime(str(date_str).strip(), "%d.%m.%Y")
        except (ValueError, TypeError):
            archive.append(r)
            continue

        if not active:
            archive.append(r)
            continue

        if event_date.year == now.year and event_date.month == now.month:
            current.append(r)
        elif (event_date.year, event_date.month) > (now.year, now.month):
            future.append(r)
        else:
            archive.append(r)

    return {"current": current, "future": future, "archive": archive}


# БАГ ИСПРАВЛЕН: не было try/except при открытии листов — падало если листов нет
def move_project_by_status(project_name: str):
    sh = get_spreadsheet()

    try:
        planning_ws = sh.worksheet("Планируемые")
        open_ws = sh.worksheet("Открытые")
        closed_ws = sh.worksheet("Закрытые")
    except gspread.exceptions.WorksheetNotFound as e:
        logger.warning(f"move_project_by_status: лист не найден — {e}")
        return

    all_ws = [planning_ws, open_ws, closed_ws]

    for ws in all_ws:
        try:
            rows = ws.get_all_values()
            headers = ws.row_values(1)

            if "статус" not in headers:
                continue

            status_idx = headers.index("статус")

            for i, row in enumerate(rows[1:], start=2):
                if not row or row[0] != project_name:
                    continue

                project_type = row[status_idx] if status_idx < len(row) else ""

                if project_type == "Планируемый":
                    target = planning_ws
                elif project_type == "Открыт":
                    target = open_ws
                elif project_type == "Закрыт":
                    target = closed_ws
                else:
                    return

                if target == ws:
                    return

                target.append_row(row)
                ws.delete_rows(i)
                logger.info(f"Project moved: {project_name} → {project_type}")
                return

        except Exception as e:
            logger.error(f"move_project_by_status error on sheet {ws.title}: {e}")


# ─────────────────────────────────────────
# ОТКЛИКИ
# ─────────────────────────────────────────

RESPONSE_HEADERS = [
    "название проекта", "должность", "telegram_user_id", "telegram_username",
    "фамилия", "имя", "доступность", "ставка", "комментарий",
    "найдено в базе", "данные из базы",
    "статус", "статус отклика", "дата отклика",
]


def get_responses_sheet(project_name: str) -> gspread.Worksheet:
    ss = get_spreadsheet()
    safe_name = project_name[:100]
    try:
        ws = ss.worksheet(safe_name)
    except gspread.exceptions.WorksheetNotFound:
        ws = ss.add_worksheet(title=safe_name, rows=1000, cols=len(RESPONSE_HEADERS))
        ws.append_row(RESPONSE_HEADERS)
    return ws


def find_response(project_name: str, telegram_user_id: int) -> Optional[int]:
    """Возвращает номер строки если активный отклик уже есть, иначе None."""
    ws = get_responses_sheet(project_name)
    records = ws.get_all_records()
    for idx, r in enumerate(records, start=2):
        if str(r.get("telegram_user_id")) == str(telegram_user_id):
            if r.get("статус отклика", "") != "Отменён":
                return idx
    return None


def save_response(
    project_name: str,
    position: str,
    telegram_user_id: int,
    username: str,
    last_name: str,
    first_name: str,
    availability: str,
    rate: str,
    comment: str,
    freelancer_row: Optional[list],
    found_in_base: str,
):
    ws = get_responses_sheet(project_name)

    if len(comment) > MAX_COMMENT_LENGTH:
        comment = comment[:MAX_COMMENT_LENGTH]
    if len(rate) > MAX_RATE_LENGTH:
        rate = rate[:MAX_RATE_LENGTH]

    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    base_data = " | ".join(str(v) for v in freelancer_row) if freelancer_row else ""

    ws.append_row([
        project_name,
        position,
        telegram_user_id,
        username or "",
        last_name,
        first_name,
        availability,
        rate,
        comment,
        found_in_base,
        base_data,
        "",
        "Активен",
        now,
    ])
    logger.info(f"Response saved | user={telegram_user_id} project={project_name}")


def cancel_response(project_name: str, telegram_user_id: int) -> bool:
    ws = get_responses_sheet(project_name)
    records = ws.get_all_records()
    col_idx = RESPONSE_HEADERS.index("статус отклика") + 1

    for idx, r in enumerate(records, start=2):
        if str(r.get("telegram_user_id")) == str(telegram_user_id):
            if r.get("статус отклика") != "Отменён":
                ws.update_cell(idx, col_idx, "Отменён")
                logger.info(f"Response cancelled: {telegram_user_id} → {project_name}")
                return True
    return False


# ─────────────────────────────────────────
# POLLING СТАТУСОВ ДЛЯ УВЕДОМЛЕНИЙ
# ─────────────────────────────────────────

def get_pending_notifications(target_statuses: list[str]) -> list[dict]:
    ss = get_spreadsheet()
    results = []

    # БАГ ИСПРАВЛЕН: теперь исключаем и PROJECTS_SHEET, а не только USERS_SHEET
    skip_titles = {USERS_SHEET, PROJECTS_SHEET}

    for ws in ss.worksheets():
        if ws.title in skip_titles:
            continue
        try:
            records = ws.get_all_records()
            headers = ws.row_values(1)

            notif_col_name = "уведомление отправлено"
            if notif_col_name not in headers:
                needed_col = len(headers) + 1
                if needed_col > ws.col_count:
                    ws.add_cols(needed_col - ws.col_count)
                ws.update_cell(1, needed_col, notif_col_name)
                headers.append(notif_col_name)

            notif_col_idx = headers.index(notif_col_name) + 1

            for row_idx, r in enumerate(records, start=2):
                status = r.get("статус", "").strip()
                notif_sent = str(r.get("уведомление отправлено", "")).strip()
                active = r.get("статус отклика", "").strip()

                if status in target_statuses and not notif_sent and active == "Активен":
                    results.append({
                        "sheet": ws.title,
                        "row_idx": row_idx,
                        "notif_col_idx": notif_col_idx,
                        "telegram_user_id": r.get("telegram_user_id"),
                        "status": status,
                        "project": r.get("название проекта", ws.title),
                        "ws": ws,
                    })
        except Exception as e:
            logger.error(f"Error scanning sheet {ws.title}: {e}")

    return results


def mark_notification_sent(ws: gspread.Worksheet, row_idx: int, notif_col_idx: int):
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    ws.update_cell(row_idx, notif_col_idx, now)


# ─────────────────────────────────────────
# БАЗА ФРИЛАНСЕРОВ
# ─────────────────────────────────────────

def _clean_cell_value(value: str) -> str:
    """
    Очищает значение ячейки Google Sheets от артефактов выпадающих списков.
    Удаляет кавычки, лишние пробелы, символы переноса строк.
    """
    if not value:
        return ""
    cleaned = str(value).strip().strip('"').strip("'").strip()
    cleaned = cleaned.replace("\n", " ").replace("\r", "").replace("\t", " ")
    while "  " in cleaned:
        cleaned = cleaned.replace("  ", " ")
    return cleaned.strip()


def _parse_position_value(value: str) -> list[str]:
    """
    Парсит значение должности/типа услуги.
    Может быть одно значение или несколько (через запятую/точку с запятой).
    Возвращает список должностей.
    """
    cleaned = _clean_cell_value(value)
    if not cleaned:
        return []
    # Разделяем по запятой, точке с запятой или переносу строки
    separators = [",", ";", "/", "\n"]
    parts = [cleaned]
    for sep in separators:
        new_parts = []
        for p in parts:
            new_parts.extend(p.split(sep))
        parts = new_parts
    # Очищаем каждое значение
    return [p.strip() for p in parts if p.strip()]


def search_freelancer(last_name: str) -> tuple[Optional[dict], str]:
    """
    Ищет фрилансера по фамилии в таблице FREELANCERS_SHEET.
    Автоматически определяет столбцы: фамилия, имя, должность (Тип услуги).
    Возвращает кортеж: (словарь_с_данными, статус).
    Статус: "found" — найдено 1 совпадение, "multiple" — несколько, "not_found" — нет.
    """
    try:
        ws = get_freelancers_spreadsheet().worksheet(FREELANCERS_SHEET)
        rows = ws.get_all_values()
    except Exception as e:
        logger.error(f"Freelancer DB error: {e}")
        return None, "not_found"

    if not rows:
        return None, "not_found"

    # Определяем индексы столбцов по заголовкам (первая строка)
    headers = [h.strip().lower() for h in rows[0]]

    last_name_idx = None
    first_name_idx = None
    position_idx = None

    for i, h in enumerate(headers):
        if h in ("фамилия", "last name", "lastname", "surname"):
            last_name_idx = i
        elif h in ("имя", "first name", "firstname", "name"):
            first_name_idx = i
        # Ищем "Тип услуги" вместо "Тип занятости"
        elif h in ("должность", "тип услуги", "type of service", "position", "занятость", "услуга"):
            position_idx = i

    # Если не нашли столбец с фамилией — ищем по первому столбцу
    if last_name_idx is None:
        last_name_idx = 0

    matches = []
    search_name = last_name.strip().lower()

    for row in rows[1:]:
        if len(row) > last_name_idx:
            row_last_name = _clean_cell_value(row[last_name_idx]).lower()
            if row_last_name == search_name:
                matches.append(row)

    if len(matches) == 1:
        row = matches[0]
        # Получаем должность и парсим возможные несколько значений
        position_raw = row[position_idx] if position_idx is not None and len(row) > position_idx else ""
        positions = _parse_position_value(position_raw)
        
        # Возвращаем словарь с данными, очищая значения
        result = {
            "фамилия": _clean_cell_value(row[last_name_idx]) if len(row) > last_name_idx else "",
            "имя": _clean_cell_value(row[first_name_idx]) if first_name_idx is not None and len(row) > first_name_idx else "",
            "должность": positions[0] if positions else "",  # первое значение
            "должности": positions,  # все значения списком
            "raw": row,  # полная строка для совместимости
        }
        return result, "found"
    elif len(matches) > 1:
        return None, "multiple"
    else:
        return None, "not_found"