"""Удаление товара в админ-панели: выбор категории → список → подтверждение."""
from html import escape

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from database.crud import (
    delete_furniture,
    get_category_by_id,
    get_furniture_by_id,
    get_furniture_page,
)
from keyboard.admin_keyboards import (
    ADMIN_PAGE_SIZE,
    admin_main_menu,
    back_to_admin_menu,
    confirm_menu,
    furniture_list_menu,
)

from .router import _admin_welcome_text, _show_categories_for

router = Router(name="admin_furniture_delete")


@router.callback_query(F.data == "adm:delfurn")
async def delete_furniture_start(callback: CallbackQuery) -> None:
    await _show_categories_for(callback, "adm:delfurn")


@router.callback_query(F.data.startswith("adm:delfurn:"))
async def delete_furniture_list(callback: CallbackQuery) -> None:
    if not isinstance(callback.message, Message):
        return

    # Вход из списка категорий: adm:delfurn:<id>; пагинация:
    # adm:delfurn:<id>:<страница>. Без страницы начинаем с первой.
    parts = callback.data.split(":")
    category_id = parts[2]
    page = max(int(parts[3]), 0) if len(parts) > 3 else 0
    category = await get_category_by_id(int(category_id))
    if category is None:
        await callback.answer("Категория не найдена", show_alert=True)
        return

    products, total = await get_furniture_page(
        category_name=str(category.name),
        page=page,
        page_size=ADMIN_PAGE_SIZE,
    )
    if not products:
        await callback.message.edit_text(
            f"В категории «{escape(str(category.name))}» пока нет товаров.",
            reply_markup=back_to_admin_menu(),
        )
        await callback.answer()
        return

    total_pages = max((total + ADMIN_PAGE_SIZE - 1) // ADMIN_PAGE_SIZE, 1)
    await callback.message.edit_text(
        f"🗑 Товары категории «{escape(str(category.name))}»:\n"
        "Нажмите на товар, чтобы удалить его.",
        reply_markup=furniture_list_menu(products, category.id, page, total_pages),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:delp:"))
async def delete_furniture_confirm(callback: CallbackQuery) -> None:
    if not isinstance(callback.message, Message):
        return

    _, _, product_id, category_id, page = callback.data.split(":")
    product = await get_furniture_by_id(int(product_id))
    if product is None:
        await callback.answer("Товар не найден", show_alert=True)
        return

    await callback.message.edit_text(
        f"❌ Удалить товар <b>{escape(str(product.name))}</b>?\n"
        f"Категория: {escape(str(product.category_name))}.",
        reply_markup=confirm_menu(f"adm:delok:{product.id}:{category_id}:{page}"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:delok:"))
async def delete_furniture_apply(callback: CallbackQuery) -> None:
    if not isinstance(callback.message, Message):
        return

    _, _, product_id, category_id, page = callback.data.split(":")
    deleted = await delete_furniture(int(product_id))
    await callback.answer(
        "Товар удалён" if deleted else "Товар не найден",
        show_alert=not deleted,
    )
    if not deleted:
        return

    # После удаления возвращаем админа в список той же категории.
    category = await get_category_by_id(int(category_id))
    if category is None:
        await callback.message.edit_text(
            _admin_welcome_text(callback.from_user.first_name),
            reply_markup=admin_main_menu(),
        )
        return
    products, total = await get_furniture_page(
        category_name=str(category.name),
        page=int(page),
        page_size=ADMIN_PAGE_SIZE,
    )
    if not products:
        await callback.message.edit_text(
            f"В категории «{escape(str(category.name))}» больше нет товаров.",
            reply_markup=back_to_admin_menu(),
        )
        return
    total_pages = max((total + ADMIN_PAGE_SIZE - 1) // ADMIN_PAGE_SIZE, 1)
    safe_page = min(int(page), total_pages - 1)
    await callback.message.edit_text(
        f"🗑 Товары категории «{escape(str(category.name))}»:\n"
        "Нажмите на товар, чтобы удалить его.",
        reply_markup=furniture_list_menu(products, category.id, safe_page, total_pages),
    )
