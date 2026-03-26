import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from states import ResponseStates
import sheets

logger = logging.getLogger(__name__)
router = Router()


def availability_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да", callback_data="avail:Да"),
        InlineKeyboardButton(text="❌ Нет", callback_data="avail:Нет"),
        InlineKeyboardButton(text="🔸 Частично", callback_data="avail:Частично"),
    ]])


def skip_keyboard(callback_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Пропустить →", callback_data=callback_data)
    ]])


# ─── Начало отклика ───────────────────────────────────────────────

@router.callback_query(F.data.startswith("apply:"))
async def apply_start(callback: CallbackQuery, state: FSMContext):
    _, project, position = callback.data.split(":", 2)

    user_id = callback.from_user.id
    user_data = sheets.find_user(user_id)

    if not user_data:
        await callback.answer("Сначала пройдите регистрацию — нажмите /start", show_alert=True)
        return

    existing_row = sheets.find_response(project, user_id)
    if existing_row:
        await callback.answer("Вы уже откликались на эту вакансию!", show_alert=True)
        return

    if not sheets.is_project_open(project, position):
        await callback.answer("Этот проект закрыт, отклики больше не принимаются.", show_alert=True)
        return

    await state.update_data(
        project=project,
        position=position,
        last_name=user_data.get("фамилия", ""),
        first_name=user_data.get("имя", ""),
        username=callback.from_user.username or "",
    )

    await callback.message.answer(
        f"📝 <b>Отклик на проект: {project}</b>\n\n"
        f"Вы доступны в даты проекта?",
        parse_mode="HTML",
        reply_markup=availability_keyboard()
    )
    await state.set_state(ResponseStates.choosing_availability)
    await callback.answer()


# ─── Доступность ─────────────────────────────────────────────────

@router.callback_query(ResponseStates.choosing_availability, F.data.startswith("avail:"))
async def availability_chosen(callback: CallbackQuery, state: FSMContext):
    availability = callback.data.split("avail:")[1]
    await callback.message.edit_reply_markup()

    # Если недоступен — отменяем отклик
    if availability == "Нет":
        data = await state.get_data()
        project = data.get("project", "")
        await state.clear()
        await callback.message.answer(
            f"❌ Отклик на проект <b>{project}</b> отменён — вы указали, что недоступны в даты мероприятия.",
            parse_mode="HTML"
        )
        await callback.answer()
        return

    await state.update_data(availability=availability)

    await callback.message.answer(
        f"✅ Доступность: <b>{availability}</b>\n\n"
        f"Укажите вашу ставку на проект (или пропустите):",
        parse_mode="HTML",
        reply_markup=skip_keyboard("skip_rate")
    )
    await state.set_state(ResponseStates.entering_rate)
    await callback.answer()


# ─── Ставка ──────────────────────────────────────────────────────

@router.message(ResponseStates.entering_rate)
async def rate_entered(message: Message, state: FSMContext):
    await state.update_data(rate=message.text.strip())
    await _ask_comment(message, state)


@router.callback_query(ResponseStates.entering_rate, F.data == "skip_rate")
async def rate_skipped(callback: CallbackQuery, state: FSMContext):
    await state.update_data(rate="")
    await callback.message.edit_reply_markup()
    await _ask_comment(callback.message, state)
    await callback.answer()


async def _ask_comment(message: Message, state: FSMContext):
    await message.answer(
        "Добавьте комментарий (или пропустите):",
        reply_markup=skip_keyboard("skip_comment")
    )
    await state.set_state(ResponseStates.entering_comment)


# ─── Комментарий ─────────────────────────────────────────────────

@router.message(ResponseStates.entering_comment)
async def comment_entered(message: Message, state: FSMContext):
    await state.update_data(comment=message.text.strip())
    await _finalize_response(message, state)


@router.callback_query(ResponseStates.entering_comment, F.data == "skip_comment")
async def comment_skipped(callback: CallbackQuery, state: FSMContext):
    await state.update_data(comment="")
    await callback.message.edit_reply_markup()
    await _finalize_response(callback.message, state)
    await callback.answer()


# ─── Сохранение отклика ──────────────────────────────────────────

async def _finalize_response(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    last_name = data.get("last_name", "")
    project = data["project"]
    position = data["position"]

    freelancer_row, match_status = sheets.search_freelancer(last_name)

    if match_status == "found":
        found_label = "Да"
    elif match_status == "multiple":
        found_label = "несколько совпадений"
    else:
        found_label = "Нет"

    sheets.save_response(
        project_name=project,
        position=position,
        telegram_user_id=message.chat.id,
        username=data.get("username", ""),
        last_name=last_name,
        first_name=data.get("first_name", ""),
        availability=data.get("availability", ""),
        rate=data.get("rate", ""),
        comment=data.get("comment", ""),
        freelancer_row=freelancer_row,
        found_in_base=found_label,
    )

    summary = (
        f"✅ <b>Отклик принят!</b>\n\n"
        f"📁 Проект: {project}\n"
        f"💼 Должность: {position}\n"
        f"📅 Доступность: {data.get('availability')}\n"
    )
    if data.get("rate"):
        summary += f"💰 Ставка: {data['rate']}\n"
    if data.get("comment"):
        summary += f"💬 Комментарий: {data['comment']}\n"

    await message.answer(
        summary,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🚫 Отменить отклик",
                callback_data=f"cancel:{project}"
            )
        ]])
    )
    logger.info(f"Response saved: user={message.chat.id}, project={project}, base={found_label}")


# ─── Отмена отклика ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("cancel:"))
async def cancel_response(callback: CallbackQuery):
    project = callback.data.split("cancel:")[1]
    user_id = callback.from_user.id

    cancelled = sheets.cancel_response(project, user_id)

    if cancelled:
        await callback.message.edit_reply_markup()
        await callback.message.answer(f"🚫 Отклик на проект <b>{project}</b> отменён.", parse_mode="HTML")
        logger.info(f"Response cancelled: user={user_id}, project={project}")
    else:
        await callback.answer("Активный отклик не найден.", show_alert=True)

    await callback.answer()