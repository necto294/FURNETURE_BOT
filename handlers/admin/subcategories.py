"""Подкатегории в админ-панели: просмотр, добавление и удаление.

Удаление полностью убирает подкатегорию, а её товары переносятся в раздел
«Остальные» у покупателя.
"""
from html import escape

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.crud import (
    create_subcategory,
    delete_subcategory,
    get_category_by_id,
    get_subcategories_with_counts,
    get_subcategory_by_id,
)
from keyboard.admin_keyboards import confirm_menu, subcategories_menu
from states.states import NewSubcategoryStates

from .router import _show_categories_for

router = Router(name="admin_subcategories")


async def _subcategory_payload(category_id: int) -> tuple[str, object] | None:
    """Собрать текст и клавиатуру списка подкатегорий категории."""
    category = await get_category_by_id(category_id)
    if category is None:
        return None
    items = await get_subcategories_with_counts(str(category.name))
    text = (
        f"🧩 Подкатегории «{escape(str(category.name))}»:\n\n"
        "Удаление переносит товары в раздел «Остальные»; сами товары не теряются."
    )
    return text, subcategories_menu(items, category.id)


async def _show_subcategory_list(callback, category_id: int) -> None:
    """Показать список подкатегорий категории с действиями (в callback-сообщении)."""
    payload = await _subcategory_payload(category_id)
    if payload is None:
        await callback.answer("Категория не найдена", show_alert=True)
        return
    text, markup = payload
    await callback.edit_text(text, reply_markup=markup)


@router.callback_query(F.data == "adm:subcat")
async def subcategory_start(callback: CallbackQuery) -> None:
    await _show_categories_for(callback, "adm:subcat")


@router.callback_query(F.data.startswith("adm:subcat:"))
async def subcategory_list(callback: CallbackQuery) -> None:
    if not isinstance(callback.message, Message):
        return
    category_id = int(callback.data.split(":")[2])
    await _show_subcategory_list(callback.message, category_id)
    await callback.answer()


# --- Добавление подкатегории ---

@router.callback_query(F.data.startswith("adm:scadd:"))
async def subcategory_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not isinstance(callback.message, Message):
        return

    category_id = int(callback.data.split(":")[2])
    category = await get_category_by_id(category_id)
    if category is None:
        await callback.answer("Категория не найдена", show_alert=True)
        return

    await state.update_data(category_id=category.id)
    await state.set_state(NewSubcategoryStates.name_subcategory)
    await callback.message.edit_text(
        f"➕ Новая подкатегория для «{escape(str(category.name))}»\n\n"
        "Введите название подкатегории:",
    )
    await callback.answer()


@router.message(StateFilter(NewSubcategoryStates.name_subcategory), F.text)
async def subcategory_add_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not name:
        await message.answer("Название не может быть пустым. Попробуйте ещё раз:")
        return

    data = await state.get_data()
    await create_subcategory(int(data["category_id"]), name)
    await state.clear()
    await message.answer(f"✅ Подкатегория «{escape(name)}» добавлена.")
    payload = await _subcategory_payload(int(data["category_id"]))
    if payload is not None:
        text, markup = payload
        await message.answer(text, reply_markup=markup)


# --- Удаление подкатегории ---

@router.callback_query(F.data.startswith("adm:scdel:"))
async def subcategory_delete_confirm(callback: CallbackQuery) -> None:
    if not isinstance(callback.message, Message):
        return

    subcategory = await get_subcategory_by_id(int(callback.data.split(":")[2]))
    if subcategory is None:
        await callback.answer("Подкатегория не найдена", show_alert=True)
        return
    await callback.message.edit_text(
        f"❌ Удалить подкатегорию «{escape(subcategory.name)}»?\n\n"
        "Её товары не удалятся, а перейдут в раздел «Остальные».",
        reply_markup=confirm_menu(f"adm:scdelok:{subcategory.id}"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:scdelok:"))
async def subcategory_delete_apply(callback: CallbackQuery) -> None:
    if not isinstance(callback.message, Message):
        return

    subcategory = await get_subcategory_by_id(int(callback.data.split(":")[2]))
    if subcategory is None:
        await callback.answer("Подкатегория не найдена", show_alert=True)
        return

    affected = await delete_subcategory(subcategory.id)
    await callback.answer(f"Перемещено в «Остальные»: {affected}")
    await _show_subcategory_list(callback.message, subcategory.category_id)
