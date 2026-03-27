import logging
from aiogram import Router, Bot, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from config import ADMIN_IDS, POSITIONS, is_admin
import sheets

logger = logging.getLogger(__name__)
router = Router()


# FSM для добавления вакансии
class AddVacancy(StatesGroup):
    waiting_position = State()
    waiting_project = State()
    waiting_date = State()
    waiting_text = State()
    waiting_notify = State()  # Выбор: уведомить пользователей или нет


USAGE = (
    "📤 Формат команды:\n\n"
    "<code>/vacancy\n"
    "Должность: Event-менеджер\n"
    "Проект: Название проекта\n"
    "Дата: 15.04.2026\n"
    "Текст: Описание вакансии...</code>\n\n"
    f"Доступные должности:\n" + "\n".join(f"• {p}" for p in POSITIONS)
)


def admin_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить вакансию")],
        ],
        resize_keyboard=True,
        persistent=True
    )


def positions_keyboard_admin() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=pos, callback_data=f"admin_pos:{pos}")]
        for pos in POSITIONS
    ]
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def vacancy_keyboard(project: str, position: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="✋ Откликнуться",
            callback_data=f"apply:{project}:{position}"
        )
    ]])


# ─────────────────────────────────────────
# АДМИН-ПАНЕЛЬ
# ─────────────────────────────────────────

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "🔧 <b>Панель администратора</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )


@router.message(F.text == "➕ Добавить вакансию")
async def start_add_vacancy(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    await state.clear()
    await message.answer(
        "📋 <b>Добавление вакансии</b>\n\n"
        "Выберите должность:",
        parse_mode="HTML",
        reply_markup=positions_keyboard_admin()
    )
    await state.set_state(AddVacancy.waiting_position)


@router.callback_query(AddVacancy.waiting_position, F.data.startswith("admin_pos:"))
async def admin_position_selected(callback: CallbackQuery, state: FSMContext):
    position = callback.data.split("admin_pos:")[1]
    await state.update_data(position=position)
    await callback.message.edit_reply_markup()
    await callback.message.answer(
        f"✅ Выбрано: <b>{position}</b>\n\n"
        f"Введите название проекта:",
        parse_mode="HTML"
    )
    await state.set_state(AddVacancy.waiting_project)
    await callback.answer()


@router.callback_query(AddVacancy.waiting_position, F.data == "admin_cancel")
@router.callback_query(AddVacancy.waiting_project, F.data == "admin_cancel")
@router.callback_query(AddVacancy.waiting_date, F.data == "admin_cancel")
@router.callback_query(AddVacancy.waiting_text, F.data == "admin_cancel")
@router.callback_query(AddVacancy.waiting_notify, F.data == "admin_cancel")
async def admin_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_reply_markup()
    await callback.message.answer("❌ Отменено")
    await callback.answer()


@router.message(AddVacancy.waiting_project)
async def admin_project_entered(message: Message, state: FSMContext):
    await state.update_data(project=message.text.strip())
    await message.answer(
        "📅 Введите дату мероприятия (в формате ДД.ММ.ГГГГ) или пропустите:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⏭️ Пропустить", callback_data="admin_skip_date")
        ]])
    )
    await state.set_state(AddVacancy.waiting_date)


@router.callback_query(AddVacancy.waiting_project, F.data == "admin_skip_date")
async def admin_skip_date(callback: CallbackQuery, state: FSMContext):
    await state.update_data(date="")
    await callback.message.edit_reply_markup()
    await callback.message.answer("📝 Введите текст вакансии:")
    await state.set_state(AddVacancy.waiting_text)
    await callback.answer()


@router.message(AddVacancy.waiting_date)
async def admin_date_entered(message: Message, state: FSMContext):
    date = message.text.strip()
    if date.lower() in ["пропустить", "-", ""]:
        date = ""
    await state.update_data(date=date)
    await message.answer("📝 Введите текст вакансии:")
    await state.set_state(AddVacancy.waiting_text)


@router.message(AddVacancy.waiting_text)
async def admin_text_entered(message: Message, state: FSMContext, bot: Bot):
    text = message.text.strip()
    await state.update_data(text=text)
    
    await message.answer(
        "📬 <b>Отправить уведомления пользователям?</b>\n\n"
        f"Должность: {await get_position_from_state(state)}\n"
        f"Проект: {await get_project_from_state(state)}\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, отправить", callback_data="notify_yes")],
            [InlineKeyboardButton(text="❌ Нет, сохранить без отправки", callback_data="notify_no")],
            [InlineKeyboardButton(text="⏭️ Отмена", callback_data="admin_cancel")],
        ])
    )
    await state.set_state(AddVacancy.waiting_notify)


async def get_position_from_state(state: FSMContext) -> str:
    data = await state.get_data()
    return data.get("position", "")


async def get_project_from_state(state: FSMContext) -> str:
    data = await state.get_data()
    return data.get("project", "")


@router.callback_query(AddVacancy.waiting_notify, F.data == "notify_yes")
async def notify_users_yes(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.message.edit_reply_markup()
    
    data = await state.get_data()
    await state.clear()
    
    position = data.get("position", "")
    project = data.get("project", "")
    event_date = data.get("date", "")
    text = data.get("text", "")
    
    # Сохраняем проект
    sheets.upsert_project(project, position, text, event_date)
    
    # Отправляем вакансию пользователям
    users = sheets.get_users_by_position(position)
    
    if not users:
        await callback.message.answer(
            f"⚠️ Нет зарегистрированных пользователей с должностью «{position}».\n\n"
            f"Проект сохранён в таблицу.",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    msg_text = (
        f"📢 <b>Новая вакансия!</b>\n\n"
        f"📁 <b>Проект:</b> {project}\n"
        f"💼 <b>Должность:</b> {position}\n"
    )
    if event_date:
        msg_text += f"📅 <b>Дата мероприятия:</b> {event_date}\n"
    msg_text += f"\n{text}"
    
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
    await callback.message.answer(result, parse_mode="HTML")
    logger.info(f"Vacancy sent: project={project}, position={position}, sent={sent}, failed={failed}")
    await callback.answer()


@router.callback_query(AddVacancy.waiting_notify, F.data == "notify_no")
async def notify_users_no(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup()
    
    data = await state.get_data()
    await state.clear()
    
    position = data.get("position", "")
    project = data.get("project", "")
    event_date = data.get("date", "")
    text = data.get("text", "")
    
    # Сохраняем проект без отправки
    sheets.upsert_project(project, position, text, event_date)
    
    await callback.message.answer(
        f"✅ Проект <b>{project}</b> сохранён в таблицу.\n\n"
        f"💼 Должность: {position}\n"
        f"📅 Дата: {event_date or 'не указана'}\n\n"
        f"⚠️ Уведомления не отправлены.",
        parse_mode="HTML"
    )
    logger.info(f"Project saved (no notify): project={project}, position={position}")
    await callback.answer()


@router.message(Command("vacancy"))
async def send_vacancy(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        return

    text = message.text or ""
    lines = text.strip().splitlines()

    parsed = {}
    current_key = None
    current_val_lines = []

    for line in lines[1:]:  # пропускаем /vacancy
        lower = line.lower()
        if lower.startswith("должность:"):
            if current_key:
                parsed[current_key] = "\n".join(current_val_lines).strip()
            current_key = "должность"
            current_val_lines = [line.split(":", 1)[1].strip()]
        elif lower.startswith("проект:"):
            if current_key:
                parsed[current_key] = "\n".join(current_val_lines).strip()
            current_key = "проект"
            current_val_lines = [line.split(":", 1)[1].strip()]
        elif lower.startswith("дата:"):
            if current_key:
                parsed[current_key] = "\n".join(current_val_lines).strip()
            current_key = "дата"
            current_val_lines = [line.split(":", 1)[1].strip()]
        elif lower.startswith("текст:"):
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
    event_date = parsed.get("дата", "").strip()
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
    sheets.upsert_project(project, position, vacancy_text, event_date)

    if not users:
        await message.answer(f"⚠️ Нет зарегистрированных пользователей с должностью «{position}».")
        return

    msg_text = (
        f"📢 <b>Новая вакансия!</b>\n\n"
        f"📁 <b>Проект:</b> {project}\n"
        f"💼 <b>Должность:</b> {position}\n"
    )
    if event_date:
        msg_text += f"📅 <b>Дата мероприятия:</b> {event_date}\n"
    msg_text += f"\n{vacancy_text}"

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
    if not is_admin(message.from_user.id):
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
    if not is_admin(message.from_user.id):
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