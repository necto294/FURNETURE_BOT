from aiogram.fsm.state import StatesGroup, State


class NewCategoryStates(StatesGroup):
    name_category = State()
    description_category = State()


class NewFurnitureStates(StatesGroup):
    description = State()
    category = State()
    kitchen_type = State()
    country = State()
    photos = State()


class RemoveFurnitureStates(StatesGroup):
    select_furniture = State()