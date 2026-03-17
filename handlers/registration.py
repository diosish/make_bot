import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart

from states import RegistrationStates
from config import POSITIONS
import sheets

logger = logging.getLogger(__name__)
router = Router()


def positions_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=pos, callback_data=f"pos:{pos}")]
        for pos in POSITIONS
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


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

    await _start_registration(message, state)


@router.callback_query(F.data == "update_profile")
async def update_profile(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup()
    await _start_registration(callback.message, state)


@router.callback_query(F.data == "profile_ok")
async def profile_ok(callback: CallbackQuery):
    await callback.message.edit_reply_markup()
    await callback.message.answer("✅ Отлично! Ожидайте вакансий по вашей специальности.")


async def _start_registration(message: Message, state: FSMContext):
    await message.answer(
        "👋 Добро пожаловать в МАКЕ Поток!\n\nВыберите вашу должность:",
        reply_markup=positions_keyboard()
    )
    await state.set_state(RegistrationStates.choosing_position)


@router.callback_query(RegistrationStates.choosing_position, F.data.startswith("pos:"))
async def position_chosen(callback: CallbackQuery, state: FSMContext):
    position = callback.data.split("pos:")[1]
    await state.update_data(position=position)
    await callback.message.edit_reply_markup()
    await callback.message.answer(f"✅ Выбрано: <b>{position}</b>\n\nВведите вашу <b>фамилию</b>:", parse_mode="HTML")
    await state.set_state(RegistrationStates.entering_last_name)


@router.message(RegistrationStates.entering_last_name)
async def last_name_entered(message: Message, state: FSMContext):
    last_name = message.text.strip()
    if not last_name:
        await message.answer("Пожалуйста, введите фамилию.")
        return
    await state.update_data(last_name=last_name)
    await message.answer("Введите ваше <b>имя</b>:", parse_mode="HTML")
    await state.set_state(RegistrationStates.entering_first_name)


@router.message(RegistrationStates.entering_first_name)
async def first_name_entered(message: Message, state: FSMContext):
    first_name = message.text.strip()
    if not first_name:
        await message.answer("Пожалуйста, введите имя.")
        return

    data = await state.get_data()
    await state.clear()

    user = message.from_user
    sheets.save_user(
        telegram_user_id=user.id,
        username=user.username or "",
        last_name=data["last_name"],
        first_name=first_name,
        position=data["position"],
    )

    await message.answer(
        f"🎉 Регистрация завершена!\n\n"
        f"👤 <b>{data['last_name']} {first_name}</b>\n"
        f"💼 {data['position']}\n\n"
        f"Вы будете получать вакансии по вашей специальности.",
        parse_mode="HTML"
    )
    logger.info(f"Registered: {user.id} ({data['last_name']} {first_name}, {data['position']})")
