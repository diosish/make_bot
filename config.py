import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "944196754"))

# Google Sheets
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")          # Новая таблица (Users + Отклики)
FREELANCERS_SPREADSHEET_ID = os.getenv("FREELANCERS_SPREADSHEET_ID")  # База фрилансеров
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")

# Листы
USERS_SHEET = "Users"
PROJECTS_SHEET = "Проекты"
FREELANCERS_SHEET = os.getenv("FREELANCERS_SHEET", "Фрилансеры")  # название листа в базе фрилансеров

# Должности
POSITIONS = [
    "Event-менеджер",
    "Руководитель проектов",
    "Технический директор",
    "Программный директор",
    "Специалист по отчетам",
    "Дизайнер",
    "Креатор",
]

# Статусы уведомлений (заполнить перед запуском)
NOTIFICATION_STATUSES = {
    "Принят": os.getenv("MSG_ACCEPTED", "✅ Поздравляем! Вы приглашены на проект. Ожидайте дополнительной информации от организаторов."),
    "Отказ":  os.getenv("MSG_REJECTED", "Спасибо за отклик. К сожалению, на этот раз вы не подошли для данного проекта. Ждём вас на следующих!"),
}

# Интервал проверки статусов (секунды)
STATUS_POLL_INTERVAL = int(os.getenv("STATUS_POLL_INTERVAL", "300"))
