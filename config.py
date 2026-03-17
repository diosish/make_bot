import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "944196754"))

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
FREELANCERS_SPREADSHEET_ID = os.getenv("FREELANCERS_SPREADSHEET_ID")
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")

USERS_SHEET = "Users"
PROJECTS_SHEET = "Проекты"
FREELANCERS_SHEET = os.getenv("FREELANCERS_SHEET", "Фрилансеры")

POSITIONS = [
    "Event-менеджер",
    "Руководитель проектов",
    "Технический директор",
    "Программный директор",
    "Специалист по отчетам",
    "Дизайнер",
    "Креатор",
]

NOTIFICATION_STATUSES = {
    "Принят": os.getenv(
        "MSG_ACCEPTED",
        "✅ Поздравляем! Вы приглашены на проект. Ожидайте дополнительной информации."
    ),
    "Отказ": os.getenv(
        "MSG_REJECTED",
        "Спасибо за отклик. К сожалению, вы не подошли."
    ),
}

STATUS_POLL_INTERVAL = int(os.getenv("STATUS_POLL_INTERVAL", "300"))

# ограничения
MAX_COMMENT_LENGTH = 500
MAX_RATE_LENGTH = 50
MAX_NAME_LENGTH = 100