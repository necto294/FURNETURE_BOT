"""Подкатегории в админ-панели: просмотр и снятие меток у товаров."""
from html import escape

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from database.crud import (
    REQUIRED_KITCHEN_TYPES,
    clear_subcategory,
    get_category_by_id,
    get_subcategories_with_counts,
)
from keyboard.admin_keyboards import confirm_menu, subcategories_menu

from .router import _filter_type, _show_categories_for

router = Router(name="admin_subcategories")


@router.callback_query(F.data == "adm:subcat")
async def subcategory_start(callback: CallbackQuery) -> None:
    await _show_categories_for(callback, "adm:subcat")


@router.callback_query(F.data.startswith("adm:subcat:"))
async def subcategory_list(callback: CallbackQuery) -> None:
    if not isinstance(callback.message, Message):
        return

    category = await get_category_by_id(int(callback.data.split(":")[2]))
    if category is None:
        await callback.answer("Категория не найдена", show_alert=True)
        return

    items = await get_subcategories_with_counts(str(category.name))
    if _filter_type(str(category.name)) == "subcategory":
        # Гарантированные типы кухни («Прямая», «Угловая») показываем,
        # даже пока ни один товар не получил такую метку.
        known = dict(items)
        for required in REQUIRED_KITCHEN_TYPES:
            known.setdefault(required, 0)
        items = sorted(known.items())
    text = (
        f"🧩 Подкатегории «{escape(str(category.name))}»:\n\n"
        "Удаление убирает метку у товаров, сами товары остаются в каталоге."
        if items
        else f"У категории «{escape(str(category.name))}» пока нет подкатегорий.\n\n"
        "Новая появляется сама, когда при добавлении товара вводят новый тип."
    )
    await callback.message.edit_text(
        text,
        reply_markup=subcategories_menu(items, category.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:scdel:"))
async def subcategory_delete_confirm(callback: CallbackQuery) -> None:
    if not isinstance(callback.message, Message):
        return

    _, _, category_id, position = callback.data.split(":")
    category = await get_category_by_id(int(category_id))
    if category is None:
        await callback.answer("Категория не найдена", show_alert=True)
        return

    items = await get_subcategories_with_counts(str(category.name))
    index = int(position)
    if index >= len(items):
        await callback.answer("Подкатегория не найдена", show_alert=True)
        return

    value, count = items[index]
    if count == 0:
        # Гарантированный тип кухни без товаров удалять не из чего.
        await callback.answer("На товарах такой метки нет", show_alert=True)
        return
    await callback.message.edit_text(
        f"❌ Убрать подкатегорию «{escape(value)}»\n"
        f"у товаров категории «{escape(str(category.name))}»?\n\n"
        f"Метку потеряют товары: <b>{count}</b>.",
        reply_markup=confirm_menu(f"adm:scdelok:{category.id}:{index}"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:scdelok:"))
async def subcategory_delete_apply(callback: CallbackQuery) -> None:
    if not isinstance(callback.message, Message):
        return

    _, _, category_id, position = callback.data.split(":")
    category = await get_category_by_id(int(category_id))
    if category is None:
        await callback.answer("Категория не найдена", show_alert=True)
        return

    items = await get_subcategories_with_counts(str(category.name))
    index = int(position)
    if index >= len(items):
        await callback.answer("Подкатегория не найдена", show_alert=True)
        return

    value, _count = items[index]
    updated = await clear_subcategory(str(category.name), value)
    await callback.answer(f"Обновлено товаров: {updated}")
    # Показываем обновлённый список подкатегорий.
    items = await get_subcategories_with_counts(str(category.name))
    await callback.message.edit_text(
        f"🧩 Подкатегории «{escape(str(category.name))}»:\n\n"
        "Удаление убирает метку у товаров, сами товары остаются в каталоге.",
        reply_markup=subcategories_menu(items, category.id),
    )
