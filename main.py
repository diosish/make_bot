import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from handlers import registration, vacancy, response, projects
from notifications import poll_notifications

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не задан в .env")

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # Подключаем роутеры
    dp.include_router(registration.router)
    dp.include_router(vacancy.router)
    dp.include_router(projects.router)
    dp.include_router(response.router)

    # Запускаем фоновую проверку уведомлений
    asyncio.create_task(poll_notifications(bot))

    logger.info("Бот запущен ✅")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
