import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent

from config import BOT_TOKEN
from handlers import registration, vacancy, response, projects
from notifications import poll_notifications

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


async def error_handler(event: ErrorEvent):
    logger.error(f"Update caused error: {event.exception}")


async def main():

    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не задан")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher(storage=MemoryStorage())

    # handlers
    dp.include_router(registration.router)
    dp.include_router(vacancy.router)
    dp.include_router(projects.router)
    dp.include_router(response.router)

    # error handler
    dp.errors.register(error_handler)

    # background notifications
    asyncio.create_task(poll_notifications(bot))

    logger.info("Бот запущен")

    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types()
    )


if __name__ == "__main__":
    asyncio.run(main())