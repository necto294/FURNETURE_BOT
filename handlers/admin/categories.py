"""Категории в админ-панели: добавление и удаление."""
from html import escape

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.crud import (
    create_category,
    delete_category,
    get_category_by_id,
    get_category_by_name,
    get_furniture_page,
)
from keyboard.admin_keyboards import (
    admin_main_menu,
    back_to_admin_menu,
    confirm_menu,
)
from keyboard.user_keyboards import CATEGORY_ICONS
from states.states import NewCategoryStates

from .router import _admin_welcome_text, _category_key, _show_categories_for

router = Router(name="admin_categories")


# --- Добавление категории ---

@router.callback_query(F.data == "adm:addcat")
async def add_category_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not isinstance(callback.message, Message):
        return

    await callback.message.edit_text(
        "➕ <b>Новая категория</b>\n\nВведите название категории:",
    )
    await state.set_state(NewCategoryStates.name_category)
    await callback.answer()


@router.message(StateFilter(NewCategoryStates.name_category), F.text)
async def add_category_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not name:
        await message.answer("Название не может быть пустым. Попробуйте ещё раз:")
        return
    if await get_category_by_name(name):
        await message.answer(
            f"Категория «{escape(name)}» уже существует. Введите другое название:"
        )
        return

    await state.update_data(name=name)
    await state.set_state(NewCategoryStates.description_category)
    await message.answer("Описание категории (или отправьте <code>-</code>, чтобы пропустить):")


@router.message(StateFilter(NewCategoryStates.description_category), F.text)
async def add_category_description(message: Message, state: FSMContext) -> None:
    description = message.text.strip()
    data = await state.get_data()
    category = await create_category(
        name=str(data["name"]),
        description=description if description != "-" else None,
    )
    await state.clear()
    icon = CATEGORY_ICONS.get(_category_key(str(category.name)), "🪑")
    await message.answer(
        f"✅ Категория {icon} <b>{escape(str(category.name))}</b> добавлена.",
        reply_markup=back_to_admin_menu(),
    )


# Ловим всё, кроме текста, в состояниях ввода категории:
# текстовые хендлеры выше уже отработали, сюда доходит остальное.
@router.message(
    StateFilter(
        NewCategoryStates.name_category,
        NewCategoryStates.description_category,
    ),
)
async def category_wrong_input_handler(message: Message) -> None:
    await message.answer("Пожалуйста, отправьте ответ текстом.")


# --- Удаление категории ---

@router.callback_query(F.data == "adm:delcat")
async def delete_category_start(callback: CallbackQuery) -> None:
    await _show_categories_for(callback, "adm:delcat")


@router.callback_query(F.data.startswith("adm:delcat:"))
async def delete_category_confirm(callback: CallbackQuery) -> None:
    if not isinstance(callback.message, Message):
        return

    category = await get_category_by_id(int(callback.data.split(":")[2]))
    if category is None:
        await callback.answer("Категория не найдена", show_alert=True)
        return

    _, total = await get_furniture_page(category_name=str(category.name), page_size=1)
    await callback.message.edit_text(
        f"❌ Удалить категорию <b>{escape(str(category.name))}</b>?\n\n"
        f"Вместе с ней будут удалены товары: <b>{total}</b>.",
        reply_markup=confirm_menu(f"adm:delcatok:{category.id}"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:delcatok:"))
async def delete_category_apply(callback: CallbackQuery) -> None:
    if not isinstance(callback.message, Message):
        return

    deleted = await delete_category(int(callback.data.split(":")[2]))
    await callback.answer(
        "Категория удалена" if deleted else "Категория не найдена",
        show_alert=not deleted,
    )
    if deleted:
        await callback.message.edit_text(
            _admin_welcome_text(callback.from_user.first_name),
            reply_markup=admin_main_menu(),
        )
