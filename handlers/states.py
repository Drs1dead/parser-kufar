from aiogram.fsm.state import State, StatesGroup


class PromoCodeState(StatesGroup):
    waiting_code = State()


class CustomPriceState(StatesGroup):
    waiting_price = State()


class AdminPromoState(StatesGroup):
    waiting_random = State()
    waiting_manual = State()
    waiting_delete = State()


class AdminUserSearchState(StatesGroup):
    waiting_username = State()


class AdminVipGrantState(StatesGroup):
    waiting_days = State()
