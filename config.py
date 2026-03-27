import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Поддержка нескольких админов
# ADMIN_IDS — строка с ID через запятую в .env (например: "944196754,123456789,987654321")
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "944196754")
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_RAW.split(",") if x.strip().isdigit()]

# Для обратной совместимости (если используется ADMIN_ID в коде)
ADMIN_ID = ADMIN_IDS[0] if ADMIN_IDS else None

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь админом."""
    return user_id in ADMIN_IDS

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
FREELANCERS_SPREADSHEET_ID = os.getenv("FREELANCERS_SPREADSHEET_ID")
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")

USERS_SHEET = "Users"
PROJECTS_SHEET = "Проекты"
FREELANCERS_SHEET = "Общая База"

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