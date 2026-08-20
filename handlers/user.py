from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InputMediaPhoto, Message

from database.crud import get_furniture_by_id, get_furniture_list
from keyboard.user_keyboards import (
    CATEGORY_CONFIG,
    country_menu,
    kitchen_menu,
    main_menu,
    product_menu,
    products_menu,
)

router = Router(name="user_catalog")

# Замените этот текст на приветственное сообщение проекта.
START_TEXT = "Добро пожаловать в каталог мебели!"


async def show_products(
    callback: CallbackQuery,
    category_key: str,
    filter_type: str | None = None,
    filter_value: str | None = None,
) -> None:
    category_name, _ = CATEGORY_CONFIG[category_key]
    products = await get_furniture_list(
        category_name=category_name,
        country=filter_value if filter_type == "country" else None,
        subcategory=filter_value if filter_type == "subcategory" else None,
    )

    if products:
        text = f"{category_name}\n\nВыберите товар:"
        keyboard = products_menu(products, category_key, filter_type, filter_value)
    else:
        text = f"В категории «{category_name}» пока нет товаров."
        keyboard = main_menu()

    await callback.message.edit_text(text, reply_markup=keyboard)


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    await message.answer(START_TEXT, reply_markup=main_menu())


@router.callback_query(F.data.startswith("category:"))
async def category_handler(callback: CallbackQuery) -> None:
    category_key = callback.data.split(":", 1)[1]
    category_name, filter_type = CATEGORY_CONFIG[category_key]

    if filter_type == "country":
        await callback.message.edit_text(
            f"{category_name}\n\nВыберите страну производства:",
            reply_markup=country_menu(category_key),
        )
    elif filter_type == "subcategory":
        await callback.message.edit_text(
            f"{category_name}\n\nВыберите тип кухни:",
            reply_markup=kitchen_menu(),
        )
    else:
        await show_products(callback, category_key)

    await callback.answer()


@router.callback_query(F.data.startswith("filter:"))
async def filter_handler(callback: CallbackQuery) -> None:
    _, category_key, filter_type, filter_value = callback.data.split(":", 3)
    await show_products(callback, category_key, filter_type, filter_value)
    await callback.answer()


@router.callback_query(F.data.startswith("product:"))
async def product_handler(callback: CallbackQuery) -> None:
    _, product_id, category_key, filter_type, filter_value = callback.data.split(":", 4)
    product = await get_furniture_by_id(int(product_id))

    if product is None:
        await callback.answer("Товар не найден", show_alert=True)
        return

    description = product.description or "Описание пока не добавлено."
    details = f"{product.name}\n\n{description}"
    if product.country:
        details += f"\n\nСтрана производства: {product.country}"
    if product.subcategory:
        details += f"\nТип: {product.subcategory}"

    if product.photos:
        media = [InputMediaPhoto(media=photo.file_id) for photo in product.photos]
        await callback.message.answer_media_group(media)

    await callback.message.answer(
        details,
        reply_markup=product_menu(category_key, filter_type or None, filter_value or None),
    )
    await callback.answer()


@router.callback_query(F.data == "back:main")
async def back_to_main_handler(callback: CallbackQuery) -> None:
    await callback.message.edit_text(START_TEXT, reply_markup=main_menu())
    await callback.answer()


@router.callback_query(F.data.startswith("back:category:"))
async def back_to_category_handler(callback: CallbackQuery) -> None:
    category_key = callback.data.split(":", 2)[2]
    category_name, filter_type = CATEGORY_CONFIG[category_key]

    if filter_type == "country":
        keyboard = country_menu(category_key)
        text = f"{category_name}\n\nВыберите страну производства:"
    elif filter_type == "subcategory":
        keyboard = kitchen_menu()
        text = f"{category_name}\n\nВыберите тип кухни:"
    else:
        await show_products(callback, category_key)
        await callback.answer()
        return

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()
