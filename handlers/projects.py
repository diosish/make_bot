import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

import sheets

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("projects"))
async def cmd_projects(message: Message):
    user_id = message.from_user.id
    user = sheets.find_user(user_id)

    if not user:
        await message.answer("Сначала пройдите регистрацию — нажмите /start")
        return

    position = user.get("должность", "")
    projects = sheets.get_open_projects_by_position(position)

    if not projects:
        await message.answer(
            f"💼 Должность: <b>{position}</b>\n\n"
            f"На данный момент открытых вакансий для вас нет. "
            f"Вы получите уведомление, как только появится новый проект.",
            parse_mode="HTML"
        )
        return

    await message.answer(
        f"💼 Открытые проекты для <b>{position}</b>:\n\nВыберите проект, чтобы откликнуться:",
        parse_mode="HTML",
        reply_markup=_projects_keyboard(projects, position)
    )


def _projects_keyboard(projects: list[dict], position: str) -> InlineKeyboardMarkup:
    buttons = []
    for p in projects:
        name = p.get("название проекта", "")
        buttons.append([InlineKeyboardButton(
            text=f"📁 {name}",
            callback_data=f"project_detail:{name}:{position}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data.startswith("project_detail:"))
async def project_detail(callback: CallbackQuery):
    _, project_name, position = callback.data.split(":", 2)

    # Проверяем актуальность статуса
    if not sheets.is_project_open(project_name, position):
        await callback.answer("Этот проект уже закрыт.", show_alert=True)
        await callback.message.edit_reply_markup()
        return

    # Ищем описание проекта
    projects = sheets.get_open_projects_by_position(position)
    description = ""
    for p in projects:
        if p.get("название проекта") == project_name:
            description = p.get("описание", "")
            break

    text = (
        f"📁 <b>{project_name}</b>\n"
        f"💼 {position}\n\n"
    )
    if description:
        text += f"{description}\n\n"

    # Проверяем, не откликался ли уже
    user_id = callback.from_user.id
    existing = sheets.find_response(project_name, user_id)
    if existing:
        text += "✅ <i>Вы уже откликнулись на этот проект</i>"
        await callback.message.answer(text, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🚫 Отменить отклик", callback_data=f"cancel:{project_name}")
            ]])
        )
    else:
        await callback.message.answer(text, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✋ Откликнуться", callback_data=f"apply:{project_name}:{position}")
            ]])
        )

    await callback.answer()
