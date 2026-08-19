# Импортируем инструменты для создания состояний (FSM)
from aiogram.fsm.state import StatesGroup, State

# Класс для состояний при создании НОВОЙ КАТЕГОРИИ
class NewCategoryStates(StatesGroup):
    name_category = State()
    description_category = State()

# Класс для состояний при добавлении НОВОЙ МЕБЕЛИ
class NewFurnitureStates(StatesGroup):
    description = State()
    category = State()
    kitchen_type = State()
    country = State()
    photos = State()

# Класс для состояний при УДАЛЕНИИ МЕБЕЛИ
class RemoveFurnitureStates(StatesGroup):
    select_furniture = State()