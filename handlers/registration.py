import asyncio
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


# Запускает синхронный sheets-вызов в отдельном потоке, не блокируя event loop
async def _run(func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()

    user_id = message.from_user.id
    existing = await _run(sheets.find_user, user_id)

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

    # Сохраняем user_id в state — чтобы не терять его при вызовах через callback.message
    await state.update_data(
        telegram_user_id=message.from_user.id,
        username=message.from_user.username or "",
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


@router.callback_query(F.data == "ln_yes")
async def last_name_confirmed(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup()
    data = await state.get_data()
    last_name = data.get("last_name")

    if not last_name:
        await callback.message.answer("Ошибка. Введите фамилию:")
        await state.set_state(Registration.last_name)
        await callback.answer()
        return

    await check_freelancer(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "ln_edit")
async def last_name_edit(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup()
    await callback.message.answer("Введите вашу фамилию:")
    await state.set_state(Registration.last_name)
    await callback.answer()


@router.message(Registration.last_name)
async def process_last_name(message: Message, state: FSMContext):
    # Обновляем user_id на случай если state был создан без него
    await state.update_data(
        last_name=message.text.strip(),
        telegram_user_id=message.from_user.id,
        username=message.from_user.username or "",
    )
    await check_freelancer(message, state)


@router.message(Registration.confirm_last_name)
async def process_confirm_last_name_text(message: Message, state: FSMContext):
    await state.update_data(
        last_name=message.text.strip(),
        telegram_user_id=message.from_user.id,
        username=message.from_user.username or "",
    )
    await check_freelancer(message, state)

async def check_freelancer(message: Message, state: FSMContext):
    data = await state.get_data()
    last_name = data["last_name"]
    
    try:
        freelancer_row, status = await _run(sheets.search_freelancer, last_name)
    except Exception as e:
        logger.error(f"check_freelancer error: {e}")
        await message.answer("⚠️ Ошибка при проверке базы. Попробуйте позже.")
        return

    if status == "found":
        # ВАЖНО: Проверьте индексы! В коде стоит [0] и [6].
        # Убедитесь, что в таблице фрилансеров: 
        # Колонка 0 (первая) = Имя
        # Колонка 6 (седьмая) = Должность
        # Если структура другая, бот будет присылать неверные данные или упадет с IndexError
        try:
            first_name = freelancer_row[0]
            position = freelancer_row[6]
        except IndexError:
            logger.error(f"Структура строки фрилансера не соответствует ожидаемой: {freelancer_row}")
            await message.answer("⚠️ Ошибка формата данных в базе. Обратитесь к админу.")
            return

        await message.answer(
            f"✅ Найдены в базе:\n"
            f"👤 {first_name} {last_name}\n"
            f"💼 {position}\n\n"
            f"Регистрация завершена"
        )
        await state.update_data(first_name=first_name, position=position)
        await finish_registration(message, state)

    elif status == "not_found":
        await message.answer("❌ Вас нет в базе\nВведите имя: ")
        await state.set_state(Registration.first_name)

    elif status == "multiple":
        await message.answer("⚠️ Найдено несколько совпадений\nВведите имя: ")
        await state.set_state(Registration.first_name)


@router.message(Registration.first_name)
async def process_first_name(message: Message, state: FSMContext):
    await state.update_data(
        first_name=message.text.strip(),
        telegram_user_id=message.from_user.id,
        username=message.from_user.username or "",
    )
    await message.answer("Выберите должность:", reply_markup=positions_keyboard())
    await state.set_state(Registration.position)


@router.callback_query(Registration.position, F.data.startswith("pos:"))
async def process_position(callback: CallbackQuery, state: FSMContext):
    position = callback.data.split("pos:")[1]
    await state.update_data(position=position)
    await callback.message.answer(f"✅ Выбрано: {position}")
    await finish_registration(callback.message, state)
    await callback.answer()


async def finish_registration(message: Message, state: FSMContext):
    data = await state.get_data()

    # Берём user_id из state — не из message.from_user, чтобы не получить бота
    telegram_user_id = data.get("telegram_user_id")
    username = data.get("username", "")

    if not telegram_user_id:
        logger.error("finish_registration: telegram_user_id отсутствует в state!")
        await message.answer("Произошла ошибка. Пожалуйста, начните регистрацию заново — /start")
        await state.clear()
        return

    await _run(
        sheets.save_user,
        telegram_user_id,
        username,
        data["last_name"],
        data["first_name"],
        data["position"],
    )

    await message.answer(
        "🎉 Регистрация завершена!\n\nНажмите кнопку ниже, чтобы посмотреть доступные мероприятия.",
        reply_markup=main_keyboard()
    )
    await state.clear()


@router.callback_query(F.data == "update_profile")
async def update_profile(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup()
    # Сохраняем user_id сразу
    await state.update_data(
        telegram_user_id=callback.from_user.id,
        username=callback.from_user.username or "",
    )
    await callback.message.answer("Введите фамилию:")
    await state.set_state(Registration.last_name)
    await callback.answer()


@router.callback_query(F.data == "profile_ok")
async def profile_ok(callback: CallbackQuery):
    await callback.message.edit_reply_markup()
    await callback.message.answer("✅ Отлично! Ожидайте вакансий.", reply_markup=main_keyboard())
    await callback.answer()
