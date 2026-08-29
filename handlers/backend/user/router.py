from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InputMediaPhoto, MediaUnion, Message

from database.crud import (
    get_categories,
    get_category_by_id,
    get_country_values,
    get_filter_values,
    get_furniture_by_id,
    upsert_user,
)
from keyboard.user_keyboards import (
    CATEGORY_CONFIG,
    country_menu,
    main_menu,
    product_menu,
    subcategory_menu,
)

from .formatters import build_product_card
from .texts import START_TEXT
from .views import show_products

router = Router(name="user_catalog")


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    # Сохраняем посетителя для админки; флаг is_admin при этом не трогаем.
    if message.from_user is not None:
        await upsert_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )
    await message.answer(START_TEXT, reply_markup=main_menu(await get_categories()))


@router.callback_query(F.data.startswith("category:"))
async def category_handler(callback: CallbackQuery) -> None:
    if not isinstance(callback.message, Message) or callback.data is None:
        return

    category_id = int(callback.data.split(":", 1)[1])
    category = await get_category_by_id(category_id)
    if category is None:
        await callback.answer("Категория не найдена", show_alert=True)
        return

    category_name = str(category.name)
    category_key = next(
        (key for key, (name, _) in CATEGORY_CONFIG.items() if name == category_name),
        category_name,
    )

    # Шаг 1: подкатегории — показываем только если они реально есть у товаров.
    subcategories = await get_filter_values(category_name, "subcategory")
    if subcategories:
        await callback.message.edit_text(
            f"{category_name}\n\nВыберите подкатегорию из каталога:",
            reply_markup=subcategory_menu(category_key, subcategories),
        )
        await callback.answer()
        return

    # Шаг 2: страна. Обязательный шаг, если у категории есть товары со странами.
    countries = await get_country_values(category_name)
    if countries:
        await callback.message.edit_text(
            f"{category_name}\n\nВыберите страну производства из каталога:",
            reply_markup=country_menu(category_key, countries),
        )
        await callback.answer()
        return

    # Нет ни подкатегорий, ни стран — сразу показываем товары.
    await show_products(callback, category_key)
    await callback.answer()


@router.callback_query(F.data.startswith("filtersub:"))
async def subcategory_handler(callback: CallbackQuery) -> None:
    # Выбрана подкатегория: показываем страны, доступные именно в ней.
    if not isinstance(callback.message, Message) or callback.data is None:
        return
    await callback.answer()

    _, category_key, subcategory = callback.data.split(":", 2)
    category_name, _ = CATEGORY_CONFIG.get(category_key, (category_key, None))
    countries = await get_country_values(category_name, subcategory)
    if countries:
        await callback.message.edit_text(
            f"{category_name}\n\nВыберите страну производства из каталога:",
            reply_markup=country_menu(category_key, countries, subcategory),
        )
        return

    # В выбранной подкатегории стран нет — показываем её товары напрямую.
    await show_products(callback, category_key, subcategory=subcategory)


@router.callback_query(F.data.startswith("country:"))
async def country_handler(callback: CallbackQuery) -> None:
    if not isinstance(callback.message, Message) or callback.data is None:
        return
    await callback.answer()

    _, category_key, subcategory, country = callback.data.split(":", 3)
    await show_products(callback, category_key, subcategory=subcategory, country=country)


@router.callback_query(F.data.startswith("page:"))
async def page_handler(callback: CallbackQuery) -> None:
    if callback.data is None:
        return

    await callback.answer()
    _, category_key, page, subcategory, country = callback.data.split(":", 4)
    await show_products(
        callback,
        category_key,
        subcategory=subcategory,
        country=country,
        page=int(page),
    )


@router.callback_query(F.data == "noop")
async def noop_handler(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("product:"))
async def product_handler(callback: CallbackQuery) -> None:
    # Из callback_data восстанавливаем путь пользователя для кнопки возврата.
    if not isinstance(callback.message, Message) or callback.data is None:
        return

    _, product_id, category_key, subcategory, country, page = callback.data.split(":", 5)
    product = await get_furniture_by_id(int(product_id))

    if product is None:
        await callback.answer("Товар не найден", show_alert=True)
        return

    details = build_product_card(product, category_key)

    # Telegram принимает фотографии группой, поэтому отправляем их одним альбомом.
    if product.photos:
        media: list[MediaUnion] = [
            InputMediaPhoto(media=photo.file_id) for photo in product.photos
        ]
        await callback.message.answer_media_group(media)

    # Кнопка заявки в карточке получает id товара и контекст возврата.
    await callback.message.answer(
        details,
        reply_markup=product_menu(
            product.id,
            category_key,
            subcategory,
            country,
            int(page),
        ),
    )
    await callback.answer()


@router.callback_query(F.data == "back:main")
async def back_to_main_handler(callback: CallbackQuery) -> None:
    if not isinstance(callback.message, Message):
        return

    await callback.message.edit_text(
        START_TEXT, reply_markup=main_menu(await get_categories())
    )
    await callback.answer()
