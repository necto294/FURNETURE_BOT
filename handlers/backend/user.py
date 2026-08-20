from html import escape

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InputMediaPhoto, MediaUnion, Message

from database.crud import get_furniture_by_id, get_furniture_list
from settings.config import ConfigBot
from keyboard.user_keyboards import (
    CATEGORY_ICONS,
    CATEGORY_CONFIG,
    country_menu,
    kitchen_menu,
    main_menu,
    product_menu,
    products_menu,
)

router = Router(name="user_catalog")

# Контакты и ссылка на соцсеть используются во всех карточках товаров.
INSTAGRAM_URL = "https://instagram.com/movsarcoder"
HTML_SEPARATOR = "<b>──────────────</b>"


def format_date(value) -> str:
    """Показать дату добавления в формате день.месяц.год."""
    return value.strftime("%d.%m.%Y") if value else "не указана"


def country_label(country: str) -> str:
    """Добавить флаг к стране, сохранённой в карточке товара."""
    flags = {"Россия": "🇷🇺", "Турция": "🇹🇷"}
    return f"{flags.get(country, '🌍')} {escape(country)}"


# Стартовое сообщение использует HTML-форматирование, включённое в main.py.
START_TEXT = """<b>🌟 Добро пожаловать в наш мебельный бот 🌟</b>

🛋️ Здесь вы найдёте стильную и качественную мебель для любого интерьера.

<b>📋 Наш каталог включает:</b>
• Спальни и матрасы
• Кухонные гарнитуры
• Мягкую мебель
• Столы и стулья
• Тумбы и комоды
• Шкафы-купе и гардеробные

<b>🛒 Как сделать заказ:</b>
1. Выберите категорию мебели.
2. Просмотрите модели.
3. Свяжитесь с нами для заказа.

<i>💬 Для оформления заказа потребуется ваше имя и номер телефона.
🔄 В любой момент можно вернуться в главное меню.</i>

<b>👇 Выберите категорию из меню ниже:</b>"""


async def show_products(
    callback: CallbackQuery,
    category_key: str,
    filter_type: str | None = None,
    filter_value: str | None = None,
) -> None:
    # Один обработчик обслуживает и обычные категории, и категории с фильтрами.
    if not isinstance(callback.message, Message):
        return

    category_name, _ = CATEGORY_CONFIG[category_key]
    products = await get_furniture_list(
        category_name=category_name,
        country=filter_value if filter_type == "country" else None,
        subcategory=filter_value if filter_type == "subcategory" else None,
    )

    if products:
        # Показываем число найденных товаров перед списком кнопок.
        text = (
            f"<b>{category_name}</b>\n\n"
            f"Показано {len(products)} из {len(products)} товаров в категории.\n\n"
            "Выберите товар:"
        )
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
    # Категория либо открывает фильтр, либо сразу загружает список товаров.
    if not isinstance(callback.message, Message) or callback.data is None:
        return

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
    if callback.data is None:
        return

    _, category_key, filter_type, filter_value = callback.data.split(":", 3)
    await show_products(callback, category_key, filter_type, filter_value)
    await callback.answer()


@router.callback_query(F.data.startswith("product:"))
async def product_handler(callback: CallbackQuery) -> None:
    # Из callback_data восстанавливаем путь пользователя для кнопки возврата.
    if not isinstance(callback.message, Message) or callback.data is None:
        return

    _, product_id, category_key, filter_type, filter_value = callback.data.split(":", 4)
    product = await get_furniture_by_id(int(product_id))

    if product is None:
        await callback.answer("Товар не найден", show_alert=True)
        return

    category_name, _ = CATEGORY_CONFIG[category_key]
    category_icon = CATEGORY_ICONS[category_key]
    description = escape(
        str(product.description)
        if product.description is not None
        else "Описание пока не добавлено."
    )
    # Собираем карточку одним HTML-сообщением после отправки фотографий.
    details = (
        f"<b>{category_icon} {escape(category_name)}</b>\n"
        f"{HTML_SEPARATOR}\n"
        f"<b>{escape(str(product.name))}</b>\n\n"
        f"{description}\n\n"
    )
    if product.subcategory is not None:
        details += f"📐 Тип мебели: {escape(str(product.subcategory))}\n"
    if product.country is not None:
        details += f"🌍 Страна производства: {country_label(str(product.country))}\n"
    # Контакты берутся из настроек, чтобы администратор мог менять их без кода.
    details += (
        f"📆 Дата добавления: {format_date(product.created_at)}\n"
        f"{HTML_SEPARATOR}\n\n"
        f"📱 WhatsApp: {escape(ConfigBot.WHATSAPP)}\n"
        f"📱 Telegram: {escape(ConfigBot.TELEGRAM)}\n\n"
        "<b>✨ Подписывайтесь на нас в Instagram</b> и будьте в курсе "
        "новинок и акций:\n"
        f"📸 <b>Instagram:</b> <a href=\"{INSTAGRAM_URL}\">{INSTAGRAM_URL}</a>"
    )

    # Telegram принимает фотографии группой, поэтому отправляем их одним альбомом.
    if product.photos:
        media: list[MediaUnion] = [
            InputMediaPhoto(media=photo.file_id) for photo in product.photos
        ]
        await callback.message.answer_media_group(media)

    await callback.message.answer(
        details,
        reply_markup=product_menu(category_key, filter_type or None, filter_value or None),
    )
    await callback.answer()


@router.callback_query(F.data == "back:main")
async def back_to_main_handler(callback: CallbackQuery) -> None:
    if not isinstance(callback.message, Message):
        return

    await callback.message.edit_text(START_TEXT, reply_markup=main_menu())
    await callback.answer()


@router.callback_query(F.data.startswith("back:category:"))
async def back_to_category_handler(callback: CallbackQuery) -> None:
    if not isinstance(callback.message, Message) or callback.data is None:
        return

    category_key = callback.data.split(":", 2)[2]
    category_name, filter_type = CATEGORY_CONFIG[category_key]

    if filter_type == "country":
        keyboard = country_menu(category_key)
        text = f"{category_name}\n\nОтлично! Теперь выберите страну производства:"
    elif filter_type == "subcategory":
        keyboard = kitchen_menu()
        text = f"{category_name}\n\nХорошо, теперь выберите тип кухни:"
    else:
        await show_products(callback, category_key)
        await callback.answer()
        return

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()
