import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from typing import Optional
import logging

from config import (
    GOOGLE_CREDENTIALS_FILE, SPREADSHEET_ID, FREELANCERS_SPREADSHEET_ID,
    USERS_SHEET, PROJECTS_SHEET, FREELANCERS_SHEET, MAX_COMMENT_LENGTH, MAX_RATE_LENGTH
)

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_client: Optional[gspread.Client] = None


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
        ws.append_row(["telegram_user_id", "telegram_username", "фамилия", "имя", "должность", "дата регистрации"])
    return ws


def find_user(telegram_user_id: int) -> Optional[dict]:
    ws = get_users_sheet()
    records = ws.get_all_records()
    for r in records:
        if str(r.get("telegram_user_id")) == str(telegram_user_id):
            return r
    return None


def save_user(telegram_user_id: int, username: str, last_name: str, first_name: str, position: str):
    ws = get_users_sheet()
    records = ws.get_all_records()
    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    for idx, r in enumerate(records, start=2):
        if str(r.get("telegram_user_id")) == str(telegram_user_id):
            ws.update(f"A{idx}:F{idx}", [[
                telegram_user_id, username or "", last_name, first_name, position, now
            ]])
            logger.info(f"User {telegram_user_id} updated")
            return

    ws.append_row([telegram_user_id, username or "", last_name, first_name, position, now])
    logger.info(f"User {telegram_user_id} registered")


def get_users_by_position(position: str) -> list[dict]:
    ws = get_users_sheet()
    records = ws.get_all_records()
    return [r for r in records if r.get("должность") == position]



# ─────────────────────────────────────────
# ПРОЕКТЫ
# ─────────────────────────────────────────

PROJECTS_HEADERS = ["название проекта", "должность", "описание", "статус", "дата создания"]


def get_projects_sheet() -> gspread.Worksheet:
    ss = get_spreadsheet()
    try:
        ws = ss.worksheet(PROJECTS_SHEET)
    except gspread.exceptions.WorksheetNotFound:
        ws = ss.add_worksheet(title=PROJECTS_SHEET, rows=500, cols=len(PROJECTS_HEADERS))
        ws.append_row(PROJECTS_HEADERS)
    return ws


def upsert_project(project_name: str, position: str, description: str):
    """Добавляет проект если его нет, или обновляет описание если есть."""
    ws = get_projects_sheet()
    records = ws.get_all_records()
    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    for idx, r in enumerate(records, start=2):
        if r.get("название проекта") == project_name and r.get("должность") == position:
            ws.update_cell(idx, 3, description)
            return

    ws.append_row([project_name, position, description, "Открыт", now])
    logger.info(f"Project added: {project_name} / {position}")


def get_open_projects_by_position(position: str) -> list[dict]:
    """Возвращает открытые проекты для данной должности."""
    ws = get_projects_sheet()
    records = ws.get_all_records()
    return [
        r for r in records
        if r.get("должность") == position and r.get("статус", "").strip() == "Открыт"
    ]


def is_project_open(project_name: str, position: str) -> bool:
    ws = get_projects_sheet()
    records = ws.get_all_records()
    for r in records:
        if r.get("название проекта") == project_name and r.get("должность") == position:
            return r.get("статус", "").strip() == "Открыт"
    return False


def set_project_status(project_name: str, status: str) -> bool:
    """Устанавливает статус всем записям с данным названием проекта."""
    ws = get_projects_sheet()
    records = ws.get_all_records()
    changed = False
    for idx, r in enumerate(records, start=2):
        if r.get("название проекта") == project_name:
            ws.update_cell(idx, 4, status)
            changed = True
    return changed


# ─────────────────────────────────────────
# ОТКЛИКИ
# ─────────────────────────────────────────

RESPONSE_HEADERS = [
    "название проекта", "должность", "telegram_user_id", "telegram_username",
    "фамилия", "имя", "доступность", "ставка", "комментарий",
    "найдено в базе", "данные из базы",
    "статус", "статус отклика", "дата отклика"
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
    """Возвращает номер строки если отклик уже есть, иначе None."""
    ws = get_responses_sheet(project_name)
    records = ws.get_all_records()
    for idx, r in enumerate(records, start=2):
        if str(r.get("telegram_user_id")) == str(telegram_user_id):
            status = r.get("статус отклика", "")
            if status != "Отменён":
                return idx
    return None

def move_project_by_status(project_name: str):

    sh = get_spreadsheet()

    planning_ws = sh.worksheet("Планируемые")
    open_ws = sh.worksheet("Открытые")
    closed_ws = sh.worksheet("Закрытые")

    sheets = [planning_ws, open_ws, closed_ws]

    for ws in sheets:

        rows = ws.get_all_values()

        for i, row in enumerate(rows[1:], start=2):

            if row[0] == project_name:

                headers = ws.row_values(1)
                status_idx = headers.index("статус")

                project_type = row[status_idx]

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

                logger.info(
                    f"Project moved: {project_name} → {project_type}"
                )

                return

def response_exists(user_id, project):

    ws = get_responses_sheet(project)

    rows = ws.get_all_values()

    for row in rows:

        if str(user_id) == row[2]:
            return True

    return False

def get_all_projects() -> list[str]:
    ws = get_projects_sheet()
    records = ws.get_all_records()
    return [r.get("MAKE_BOT") for r in records if r.get("MAKE_BOT")]

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
        now
    ])

    logger.info(
        f"Response saved | user={telegram_user_id} project={project_name}"
    )

def cancel_response(project_name: str, telegram_user_id: int) -> bool:
    ws = get_responses_sheet(project_name)
    records = ws.get_all_records()
    col_status_otklika = RESPONSE_HEADERS.index("статус отклика") + 1

    for idx, r in enumerate(records, start=2):
        if str(r.get("telegram_user_id")) == str(telegram_user_id):
            if r.get("статус отклика") != "Отменён":
                ws.update_cell(idx, col_status_otklika, "Отменён")
                logger.info(f"Response cancelled: {telegram_user_id} → {project_name}")
                return True
    return False


# ─────────────────────────────────────────
# БАЗА ФРИЛАНСЕРОВ
# ─────────────────────────────────────────

def search_freelancer(last_name: str) -> tuple[Optional[list], str]:
    """
    Возвращает (строка данных, статус):
      - (row, "found")           — одно совпадение
      - (None, "multiple")       — несколько совпадений
      - (None, "not_found")      — не найдено
    """
    try:
        ws = get_freelancers_spreadsheet().worksheet(FREELANCERS_SHEET)
        all_values = ws.get_all_values()
    except Exception as e:
        logger.error(f"Freelancer DB error: {e}")
        return None, "not_found"

    matches = []
    for row in all_values[1:]:  # пропускаем заголовок
        row_values = [str(v).strip() for v in row]
        # ищем фамилию в любой ячейке строки (гибко)
        if any(v.lower() == last_name.strip().lower() for v in row_values):
            matches.append(row)

    if len(matches) == 1:
        return matches[0], "found"
    elif len(matches) > 1:
        return None, "multiple"
    else:
        return None, "not_found"


# ─────────────────────────────────────────
# POLLING СТАТУСОВ ДЛЯ УВЕДОМЛЕНИЙ
# ─────────────────────────────────────────

def get_pending_notifications(target_statuses: list[str]) -> list[dict]:
    """
    Сканирует все листы откликов и возвращает строки, у которых:
    - статус совпадает с target_statuses
    - статус отклика = Активен
    - уведомление ещё не отправлено (нет отметки в доп. колонке)
    """
    ss = get_spreadsheet()
    results = []

    for ws in ss.worksheets():
        if ws.title == USERS_SHEET:
            continue
        try:
            records = ws.get_all_records()
            headers = ws.row_values(1)
            # Добавляем колонку "уведомление отправлено" если её нет
            notif_col_name = "уведомление отправлено"
            if notif_col_name not in headers:
                ws.update_cell(1, len(headers) + 1, notif_col_name)
                headers.append(notif_col_name)

            notif_col_idx = headers.index(notif_col_name) + 1

            for row_idx, r in enumerate(records, start=2):
                status = r.get("статус", "").strip()
                notif_sent = r.get("уведомление отправлено", "").strip()
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
