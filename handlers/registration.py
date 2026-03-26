import logging
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, FSInputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State

from config import POSITIONS
import sheets

logger = logging.getLogger(__name__)
router = Router()


class Registration(StatesGroup):
    confirm_last_name = State()
    last_name = State()
    first_name = State()
    position = State()
    choose_base_action = State()  # Выбор: перенести данные или вручную


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📋 Доступные мероприятия")]],
        resize_keyboard=True,
        persistent=True
    )


def positions_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=pos, callback_data=f"pos:{pos}")]
            for pos in POSITIONS
        ]
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()

    user_id = message.from_user.id
    existing = sheets.find_user(user_id)

    if existing:
        await message.answer(
            f"👋 Вы уже зарегистрированы!\n\n"
            f"👤 <b>{existing.get('фамилия')} {existing.get('имя')}</b>\n"
            f"💼 {existing.get('должность')}\n\n"
            f"Хотите обновить данные?",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✏️ Обновить данные", callback_data="update_profile")],
                [InlineKeyboardButton(text="✅ Всё верно", callback_data="profile_ok")],
            ])
        )
        return

    photo = FSInputFile("assets/welcome.jpg")
    await message.answer_photo(
        photo=photo,
        caption=(
            "👋 Добро пожаловать в МАКЕ Поток!\n\n"
            "Здесь вы будете получать актуальные проекты.\n\n"
            "👇 Давайте зарегистрируемся"
        )
    )

    tg_last_name = message.from_user.last_name

    if tg_last_name:
        await message.answer(
            f"Ваша фамилия: <b>{tg_last_name}</b>?\n\nПодтвердите или введите другую:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Да", callback_data="ln_yes")],
                [InlineKeyboardButton(text="✏️ Изменить", callback_data="ln_edit")]
            ])
        )
        await state.update_data(last_name=tg_last_name)
        await state.set_state(Registration.confirm_last_name)
    else:
        await message.answer("Введите вашу фамилию:")
        await state.set_state(Registration.last_name)


# Подтвердить фамилию из Telegram
@router.callback_query(F.data == "ln_yes")
async def last_name_confirmed(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup()
    data = await state.get_data()
    last_name = data.get("last_name")

    if not last_name:
        await callback.message.answer("Ошибка. Введите фамилию:")
        await state.set_state(Registration.last_name)
        return

    await check_freelancer(callback.message, state)
    await callback.answer()


# БАГ ИСПРАВЛЕН: кнопка "Изменить" не имела обработчика
@router.callback_query(F.data == "ln_edit")
async def last_name_edit(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup()
    await callback.message.answer("Введите вашу фамилию:")
    await state.set_state(Registration.last_name)
    await callback.answer()


# Ввод фамилии вручную (состояние last_name)
@router.message(Registration.last_name)
async def process_last_name(message: Message, state: FSMContext):
    await state.update_data(last_name=message.text.strip())
    await check_freelancer(message, state)


# Ввод фамилии в состоянии confirm_last_name (если пользователь всё равно написал текст)
@router.message(Registration.confirm_last_name)
async def process_confirm_last_name_text(message: Message, state: FSMContext):
    await state.update_data(last_name=message.text.strip())
    await check_freelancer(message, state)


async def check_freelancer(message: Message, state: FSMContext):
    data = await state.get_data()
    last_name = data["last_name"]
    skip_search = data.get("skip_freelancer_search", False)

    # При обновлении профиля не ищем в базе фрилансеров
    if skip_search:
        await message.answer("Введите имя:")
        await state.set_state(Registration.first_name)
        return

    freelancer_data, status = sheets.search_freelancer(last_name)

    if status == "found":
        first_name = freelancer_data.get("имя", "")
        positions = freelancer_data.get("должности", [])
        position_display = ", ".join(positions) if positions else freelancer_data.get("должность", "")

        await message.answer(
            f"✅ Найдены в базе:\n\n"
            f"👤 <b>{first_name} {last_name}</b>\n"
            f"💼 <b>Тип услуги:</b> {position_display}\n\n"
            f"Что хотите сделать?",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Перенести данные", callback_data="base_use_data")],
                [InlineKeyboardButton(text="✏️ Ввести вручную", callback_data="base_enter_manual")],
            ])
        )
        await state.set_state(Registration.choose_base_action)
        return

    elif status == "not_found":
        await message.answer("❌ Вас нет в базе\nВведите имя:")
        await state.set_state(Registration.first_name)

    elif status == "multiple":
        await message.answer("⚠️ Найдено несколько совпадений\nВведите имя:")
        await state.set_state(Registration.first_name)


@router.message(Registration.first_name)
async def process_first_name(message: Message, state: FSMContext):
    await state.update_data(first_name=message.text.strip())
    await message.answer("Выберите должность:", reply_markup=positions_keyboard())
    await state.set_state(Registration.position)


@router.callback_query(Registration.position, F.data.startswith("pos:"))
async def process_position(callback: CallbackQuery, state: FSMContext):
    position = callback.data.split("pos:")[1]
    await state.update_data(position=position)
    await callback.message.answer(f"✅ Выбрано: {position}")
    await finish_registration(callback, state)
    await callback.answer()


async def finish_registration(event, state: FSMContext):
    data = await state.get_data()
    user = event.from_user

    sheets.save_user(
        telegram_user_id=user.id,
        username=user.username,
        last_name=data["last_name"],
        first_name=data["first_name"],
        position=data["position"]
    )

    msg = event.message if hasattr(event, "message") else event

    await msg.answer(
        "🎉 Регистрация завершена!\n\nНажмите кнопку ниже, чтобы посмотреть доступные мероприятия.",
        reply_markup=main_keyboard()
    )
    await state.clear()


@router.callback_query(F.data == "update_profile")
async def update_profile(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup()
    # При обновлении профиля не ищем в базе фрилансеров
    await callback.message.answer("Введите фамилию:")
    await state.set_state(Registration.last_name)
    await state.update_data(skip_freelancer_search=True)
    await callback.answer()


@router.callback_query(F.data == "profile_ok")
async def profile_ok(callback: CallbackQuery):
    await callback.message.edit_reply_markup()
    await callback.message.answer("✅ Отлично! Ожидайте вакансий.", reply_markup=main_keyboard())
    await callback.answer()


# Обработчики выбора действия с базой
@router.callback_query(Registration.choose_base_action, F.data == "base_use_data")
async def use_base_data(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup()
    
    data = await state.get_data()
    last_name = data["last_name"]
    freelancer_data, _ = sheets.search_freelancer(last_name)
    
    first_name = freelancer_data.get("имя", "")
    positions = freelancer_data.get("должности", [])
    position = positions[0] if positions else ""
    
    await callback.message.answer(
        f"✅ Данные перенесены:\n"
        f"👤 {first_name} {last_name}\n"
        f"💼 {position}\n\n"
        f"Регистрация завершена",
        reply_markup=main_keyboard()
    )
    
    await state.update_data(
        first_name=first_name,
        position=position,
        freelancer_row=freelancer_data.get("raw", []),
        found_in_base="Да"
    )
    
    # Используем callback.from_user для актуальных данных
    await finish_registration_with_user(callback, state, callback.from_user)
    await callback.answer()


async def finish_registration_with_user(event, state: FSMContext, user):
    """Сохраняет пользователя с явной передачей данных из Telegram."""
    data = await state.get_data()
    
    sheets.save_user(
        telegram_user_id=user.id,
        username=user.username,
        last_name=data["last_name"],
        first_name=data["first_name"],
        position=data["position"]
    )
    
    await event.message.answer(
        "🎉 Регистрация завершена!\n\nНажмите кнопку ниже, чтобы посмотреть доступные мероприятия.",
        reply_markup=main_keyboard()
    )
    await state.clear()


@router.callback_query(Registration.choose_base_action, F.data == "base_enter_manual")
async def enter_manual_data(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup()
    await callback.message.answer("Введите имя:")
    await state.set_state(Registration.first_name)
    await callback.answer()