"""Меню админ-панели и общие вспомогательные функции раздела.

Здесь живёт только навигация: вход по /admin, возврат в меню и общий
пикер категорий для действий «удалить товар/категорию/подкатегорию».
Доменные потоки разнесены по модулям categories/furniture/subcategories,
проверка прав — в access.py (middleware на родительском роутере).
"""
from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.crud import get_categories_with_counts
from handlers.backend.user.texts import HTML_SEPARATOR
from keyboard.admin_keyboards import admin_main_menu, categories_menu
from keyboard.user_keyboards import CATEGORY_CONFIG

router = Router(name="admin")


def _admin_welcome_text(first_name: str | None) -> str:
    """Приветствие с инструкцией по кнопкам панели."""
    name = escape(first_name) if first_name else "администратор"
    return (
        "🛠 <b>Панель администратора</b>\n"
        f"{HTML_SEPARATOR}\n\n"
        f"👋 Здравствуйте, <b>{name}</b>! Здесь вы управляете каталогом "
        "и получаете заявки покупателей.\n\n"
        "<b>📋 Возможности панели:</b>\n\n"
        "🪑 <b>Добавить товар</b> — пошаговое создание карточки:\n"
        "название → описание → категория → тип кухни или страна →\n"
        "контакты WhatsApp/Telegram → фото.\n\n"
        "🗑 <b>Удалить товар</b> — выберите категорию, затем товар из списка.\n\n"
        "➕ <b>Добавить категорию</b> — новый раздел главного меню каталога.\n\n"
        "❌ <b>Удалить категорию</b> — удалит её вместе со всеми товарами!\n\n"
        "🧩 <b>Подкатегории</b> — добавление и удаление подкатегорий;\n"
        "удалённая прячется в раздел «Остальные», товары не теряются.\n\n"
        "📨 <b>Заявки</b> — список заказов с именем, телефоном и сменой статуса.\n\n"
        "🛎 Каждая подтверждённая заявка придёт вам сообщением.\n\n"
        "⚠️ Удаление необратимо, поэтому панель всегда переспрашивает.\n"
        "👇 Выберите действие на клавиатуре ниже:"
    )


async def _send_admin_menu(message: Message, first_name: str | None) -> None:
    """Отправить приветствие панели отдельным сообщением."""
    await message.answer(
        _admin_welcome_text(first_name),
        reply_markup=admin_main_menu(),
    )


def _category_key(category_name: str) -> str:
    """Обратный поиск короткого ключа категории по её имени."""
    return next(
        (key for key, (name, _) in CATEGORY_CONFIG.items() if name == category_name),
        category_name,
    )


async def _show_categories_for(callback: CallbackQuery, action_prefix: str) -> None:
    """Отрисовать список категорий с числом товаров для выбранного действия."""
    if not isinstance(callback.message, Message):
        return
    items = await get_categories_with_counts()
    text = "Выберите категорию:" if items else "Сначала создайте хотя бы одну категорию."
    await callback.message.edit_text(
        text,
        reply_markup=categories_menu(items, action_prefix),
    )
    await callback.answer()


# --- Вход в админ-панель и навигация по меню ---

@router.message(Command("admin"))
async def admin_menu_command(message: Message, state: FSMContext) -> None:
    # Вход в панель сбрасывает незавершённые административные сценарии.
    await state.clear()
    first_name = message.from_user.first_name if message.from_user else None
    await _send_admin_menu(message, first_name)


@router.callback_query(F.data == "adm:menu")
async def admin_menu_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if not isinstance(callback.message, Message):
        return
    await state.clear()
    await callback.message.edit_text(
        _admin_welcome_text(callback.from_user.first_name),
        reply_markup=admin_main_menu(),
    )
    await callback.answer()


@router.callback_query(F.data == "adm:noop")
async def admin_noop_handler(callback: CallbackQuery) -> None:
    # Кнопки без действия, например счётчик страниц.
    await callback.answer()


@router.callback_query(F.data == "adm:cancel")
async def admin_cancel_handler(callback: CallbackQuery, state: FSMContext) -> None:
    # Отмена доступна в любом состоянии и возвращает в меню панели.
    if not isinstance(callback.message, Message):
        return
    await state.clear()
    await callback.message.edit_text(
        _admin_welcome_text(callback.from_user.first_name),
        reply_markup=admin_main_menu(),
    )
    await callback.answer()
