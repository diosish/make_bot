from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    choosing_position = State()
    entering_last_name = State()
    entering_first_name = State()


class VacancyStates(StatesGroup):
    waiting_position = State()
    waiting_project = State()
    waiting_text = State()


class ResponseStates(StatesGroup):
    choosing_availability = State()
    entering_rate = State()
    entering_comment = State()
