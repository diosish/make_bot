import asyncio
import logging
from aiogram import Bot
from datetime import datetime

from config import NOTIFICATION_STATUSES, STATUS_POLL_INTERVAL
import sheets

logger = logging.getLogger(__name__)

SEND_DELAY = 0.05


async def poll_projects():
    """
    Ранее перемещала проекты между отдельными листами (Планируемые/Открытые/Закрытые).
    Эта логика избыточна — статус хранится в колонке 'статус' листа 'Проекты'.
    Функция оставлена как заглушка, чтобы не менять main.py.
    """
    while True:
        await asyncio.sleep(STATUS_POLL_INTERVAL)


async def poll_notifications(bot: Bot):

    target_statuses = list(NOTIFICATION_STATUSES.keys())

    while True:

        try:
            pending = sheets.get_pending_notifications(target_statuses)

            if pending:
                logger.info(f"Найдено уведомлений: {len(pending)}")

            for item in pending:

                user_id = item.get("telegram_user_id")
                status = item.get("status")
                project = item.get("project")

                if not user_id:
                    continue

                text = NOTIFICATION_STATUSES.get(status)
                if not text:
                    continue

                current_hour = datetime.now().hour
                user_hour = sheets.get_user_notify_hour(user_id)

                # Если время уведомлений не задано — отправляем сразу
                # Если задано — ждём нужного часа
                if user_hour is not None and user_hour != current_hour:
                    continue

                message = f"📋 <b>Проект: {project}</b>\n\n{text}"

                try:
                    await bot.send_message(
                        chat_id=int(user_id),
                        text=message,
                        parse_mode="HTML"
                    )

                    sheets.mark_notification_sent(
                        item["ws"],
                        item["row_idx"],
                        item["notif_col_idx"]
                    )

                    logger.info(
                        f"Notification sent | user={user_id} project={project} status={status}"
                    )

                    await asyncio.sleep(SEND_DELAY)

                except Exception as e:
                    logger.warning(f"Ошибка отправки уведомления user={user_id}: {e}")

        except Exception as e:
            logger.error(f"Ошибка polling: {e}")

        await asyncio.sleep(STATUS_POLL_INTERVAL)