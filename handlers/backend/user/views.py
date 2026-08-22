from html import escape

from aiogram.types import CallbackQuery, Message

from database.crud import get_furniture_page
from keyboard.user_keyboards import (
    CATEGORY_CONFIG,
    CATEGORY_ICONS,
    empty_catalog_menu,
    products_menu,
)

from .texts import HTML_SEPARATOR


async def show_products(
    callback: CallbackQuery,
    category_key: str,
    filter_type: str | None = None,
    filter_value: str | None = None,
    page: int = 0,
) -> None:
    if not isinstance(callback.message, Message):
        return

    category_name, _ = CATEGORY_CONFIG.get(category_key, (category_key, None))
    products, total = await get_furniture_page(
        category_name=category_name,
        page=page,
        country=filter_value if filter_type == "country" else None,
        subcategory=filter_value if filter_type == "subcategory" else None,
    )

    if products:
        # Показываем число найденных товаров перед списком кнопок.
        text = (
            f"<b>{category_name}</b>\n\n"
            f"Показано {len(products)} из {total} товаров в категории.\n\n"
            "Выберите товар:"
        )
        keyboard = products_menu(products, category_key, filter_type, filter_value, page, total)
    else:
        # Пустой результат оформляем как отдельное состояние каталога.
        category_icon = CATEGORY_ICONS.get(category_key, "🪑")
        if filter_value:
            text = (
                f"<b>{category_icon} {escape(category_name)}</b>\n"
                f"{HTML_SEPARATOR}\n\n"
                f"<i>По фильтру «{escape(str(filter_value))}» товаров пока нет.</i>\n\n"
                "Попробуйте выбрать другой вариант или вернитесь в каталог."
            )
        else:
            text = (
                f"<b>{category_icon} {escape(category_name)}</b>\n"
                f"{HTML_SEPARATOR}\n\n"
                "<i>В этой категории пока нет доступных товаров.</i>\n\n"
                "Новые модели появятся здесь после добавления в каталог."
            )
        keyboard = empty_catalog_menu()

    await callback.message.edit_text(text, reply_markup=keyboard)
