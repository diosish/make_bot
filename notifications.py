import asyncio
import logging
from aiogram import Bot

from config import NOTIFICATION_STATUSES, STATUS_POLL_INTERVAL
import sheets

logger = logging.getLogger(__name__)


async def poll_notifications(bot: Bot):
    """Фоновая задача: каждые N секунд проверяет статусы в Sheets и шлёт уведомления."""
    target_statuses = list(NOTIFICATION_STATUSES.keys())

    while True:
        try:
            pending = sheets.get_pending_notifications(target_statuses)

            for item in pending:
                user_id = item.get("telegram_user_id")
                status = item.get("status")
                project = item.get("project")

                if not user_id:
                    continue

                text = NOTIFICATION_STATUSES.get(status, "")
                if not text:
                    continue

                full_text = f"📋 <b>Проект: {project}</b>\n\n{text}"

                try:
                    await bot.send_message(
                        chat_id=int(user_id),
                        text=full_text,
                        parse_mode="HTML"
                    )
                    sheets.mark_notification_sent(
                        item["ws"], item["row_idx"], item["notif_col_idx"]
                    )
                    logger.info(f"Notification sent: user={user_id}, status={status}, project={project}")
                except Exception as e:
                    logger.warning(f"Failed to notify {user_id}: {e}")

        except Exception as e:
            logger.error(f"Polling error: {e}")

        await asyncio.sleep(STATUS_POLL_INTERVAL)
