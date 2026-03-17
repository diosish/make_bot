import logging
from aiogram import Router, Bot
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config import ADMIN_ID, POSITIONS
import sheets

logger = logging.getLogger(__name__)
router = Router()

USAGE = (
    "📤 Формат команды:\n\n"
    "<code>/vacancy\n"
    "Должность: Event-менеджер\n"
    "Проект: Название проекта\n"
    "Текст: Описание вакансии...</code>\n\n"
    f"Доступные должности:\n" + "\n".join(f"• {p}" for p in POSITIONS)
)


def vacancy_keyboard(project: str, position: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="✋ Откликнуться",
            callback_data=f"apply:{project}:{position}"
        )
    ]])


@router.message(Command("vacancy"))
async def send_vacancy(message: Message, bot: Bot):
    if message.from_user.id != ADMIN_ID:
        return

    text = message.text or ""
    lines = text.strip().splitlines()

    # Парсим поля
    parsed = {}
    current_key = None
    current_val_lines = []

    for line in lines[1:]:  # пропускаем /vacancy
        if line.lower().startswith("должность:"):
            if current_key:
                parsed[current_key] = "\n".join(current_val_lines).strip()
            current_key = "должность"
            current_val_lines = [line.split(":", 1)[1].strip()]
        elif line.lower().startswith("проект:"):
            if current_key:
                parsed[current_key] = "\n".join(current_val_lines).strip()
            current_key = "проект"
            current_val_lines = [line.split(":", 1)[1].strip()]
        elif line.lower().startswith("текст:"):
            if current_key:
                parsed[current_key] = "\n".join(current_val_lines).strip()
            current_key = "текст"
            current_val_lines = [line.split(":", 1)[1].strip()]
        else:
            if current_key:
                current_val_lines.append(line)

    if current_key:
        parsed[current_key] = "\n".join(current_val_lines).strip()

    position = parsed.get("должность", "").strip()
    project = parsed.get("проект", "").strip()
    vacancy_text = parsed.get("текст", "").strip()

    if not position or not project or not vacancy_text:
        await message.answer(f"❌ Неверный формат.\n\n{USAGE}", parse_mode="HTML")
        return

    if position not in POSITIONS:
        await message.answer(
            f"❌ Должность <b>{position}</b> не найдена.\n\n{USAGE}",
            parse_mode="HTML"
        )
        return

    users = sheets.get_users_by_position(position)

    # Регистрируем/обновляем проект в таблице проектов
    sheets.upsert_project(project, position, vacancy_text)

    if not users:
        await message.answer(f"⚠️ Нет зарегистрированных пользователей с должностью «{position}».")
        return

    msg_text = (
        f"📢 <b>Новая вакансия!</b>\n\n"
        f"📁 <b>Проект:</b> {project}\n"
        f"💼 <b>Должность:</b> {position}\n\n"
        f"{vacancy_text}"
    )

    sent = 0
    failed = 0
    for user in users:
        try:
            await bot.send_message(
                chat_id=int(user["telegram_user_id"]),
                text=msg_text,
                parse_mode="HTML",
                reply_markup=vacancy_keyboard(project, position)
            )
            sent += 1
        except Exception as e:
            logger.warning(f"Cannot send to {user['telegram_user_id']}: {e}")
            failed += 1

    result = f"✅ Вакансия отправлена: <b>{sent}</b> получателей"
    if failed:
        result += f"\n⚠️ Не доставлено: {failed} (заблокировали бота)"
    await message.answer(result, parse_mode="HTML")
    logger.info(f"Vacancy sent: project={project}, position={position}, sent={sent}, failed={failed}")


@router.message(Command("close"))
async def close_project(message: Message):
    """Закрыть проект: /close Название проекта"""
    if message.from_user.id != ADMIN_ID:
        return
    project_name = (message.text or "").replace("/close", "").strip()
    if not project_name:
        await message.answer("Использование: <code>/close Название проекта</code>", parse_mode="HTML")
        return
    changed = sheets.set_project_status(project_name, "Закрыт")
    if changed:
        await message.answer(f"🔒 Проект <b>{project_name}</b> закрыт. Отклики больше не принимаются.", parse_mode="HTML")
    else:
        await message.answer(f"❌ Проект «{project_name}» не найден в таблице.")


@router.message(Command("open"))
async def open_project(message: Message):
    """Открыть проект: /open Название проекта"""
    if message.from_user.id != ADMIN_ID:
        return
    project_name = (message.text or "").replace("/open", "").strip()
    if not project_name:
        await message.answer("Использование: <code>/open Название проекта</code>", parse_mode="HTML")
        return
    changed = sheets.set_project_status(project_name, "Открыт")
    if changed:
        await message.answer(f"🟢 Проект <b>{project_name}</b> снова открыт.", parse_mode="HTML")
    else:
        await message.answer(f"❌ Проект «{project_name}» не найден в таблице.")
