# Импортируем инструменты для создания состояний (FSM)
from aiogram.fsm.state import State, StatesGroup


# Класс для состояний при создании НОВОЙ КАТЕГОРИИ
class NewCategoryStates(StatesGroup):
    name_category = State()
    description_category = State()

# Класс для состояний при добавлении НОВОЙ МЕБЕЛИ
class NewFurnitureStates(StatesGroup):
    name = State()
    description = State()
    category = State()
    kitchen_type = State()
    country = State()
    whatsapp_contact = State()
    telegram_contact = State()
    photos = State()

# Класс для состояний при УДАЛЕНИИ МЕБЕЛИ
class RemoveFurnitureStates(StatesGroup):
    select_furniture = State()


# Класс для состояний при ОФОРМЛЕНИИ ЗАЯВКИ
class OrderStates(StatesGroup):
    name = State()
    phone = State()
    confirm = State()
