import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

import sheets

logger = logging.getLogger(__name__)
router = Router()


async def show_projects(message: Message):
    user_id = message.from_user.id
    user = sheets.find_user(user_id)

    if not user:
        await message.answer("Сначала пройдите регистрацию — нажмите /start")
        return

    position = user.get("должность", "").strip()
    groups = sheets.get_projects_grouped()

    # Нормализуем обе стороны: убираем пробелы и приводим к нижнему регистру
    def normalize(s: str) -> str:
        return s.strip().lower()

    projects = [
        p for p in groups["current"]
        if normalize(p.get("должность", "")) == normalize(position)
    ]

    logger.info(
        f"show_projects | user={user_id} position='{position}' "
        f"all_current={[p.get('должность') for p in groups['current']]} "
        f"matched={len(projects)}"
    )

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


@router.message(Command("projects"))
async def cmd_projects(message: Message):
    await show_projects(message)


@router.message(F.text == "📋 Доступные мероприятия")
async def btn_projects(message: Message):
    await show_projects(message)


def _projects_keyboard(projects: list[dict], position: str) -> InlineKeyboardMarkup:
    buttons = []
    for p in projects:
        name = p.get("название проекта", "")
        date = p.get("дата мероприятия", "")
        label = f"📁 {name}"
        if date:
            label += f"  •  📅 {date}"
        buttons.append([InlineKeyboardButton(
            text=label,
            callback_data=f"project_detail:{name}:{position}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data.startswith("project_detail:"))
async def project_detail(callback: CallbackQuery):
    _, project_name, position = callback.data.split(":", 2)

    if not sheets.is_project_open(project_name, position):
        await callback.answer("Этот проект уже закрыт.", show_alert=True)
        await callback.message.edit_reply_markup()
        return

    groups = sheets.get_projects_grouped()
    description = ""
    event_date = ""
    for p in groups["current"]:
        if p.get("название проекта") == project_name:
            description = p.get("описание", "")
            event_date = p.get("дата мероприятия", "")
            break

    text = f"📁 <b>{project_name}</b>\n💼 {position}\n"
    if event_date:
        text += f"📅 <b>Дата мероприятия:</b> {event_date}\n"
    text += "\n"
    if description:
        text += f"{description}\n\n"

    user_id = callback.from_user.id
    existing = sheets.find_response(project_name, user_id)
    if existing:
        text += "✅ <i>Вы уже откликнулись на этот проект</i>"
        await callback.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🚫 Отменить отклик", callback_data=f"cancel:{project_name}")
            ]])
        )
    else:
        await callback.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✋ Откликнуться", callback_data=f"apply:{project_name}:{position}")
            ]])
        )

    await callback.answer()


@router.message(Command("notifications"))
async def set_notifications(message: Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="09:00", callback_data="notify_9")],
            [InlineKeyboardButton(text="12:00", callback_data="notify_12")],
            [InlineKeyboardButton(text="18:00", callback_data="notify_18")],
            [InlineKeyboardButton(text="21:00", callback_data="notify_21")]
        ]
    )
    await message.answer("Выберите время уведомлений", reply_markup=kb)


@router.callback_query(F.data.startswith("notify_"))
async def save_notify_time(callback: CallbackQuery):
    hour = int(callback.data.split("_")[1])
    sheets.save_notify_time(callback.from_user.id, hour)
    await callback.message.answer(f"Уведомления будут приходить в {hour}:00")
    await callback.answer()