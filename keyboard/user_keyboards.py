from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


# Ключи категорий используются в callback_data и связывают меню с обработчиками.
CATEGORY_BUTTONS = (
    ("🛏️ Спальная мебель", "category:sleep"),
    ("🍳 Кухонная мебель", "category:kitchen"),
    ("🛋️ Мягкая мебель", "category:soft"),
    ("📚 Столы и стулья", "category:tables"),
    ("📺 Тумбы и комоды", "category:cabinets"),
    ("🛏️ Матрасы", "category:mattresses"),
    ("🛏️ Кровати", "category:beds"),
    ("📦 Шкафы", "category:wardrobes"),
)


# Для каждой категории указываем нужный дополнительный фильтр.
CATEGORY_CONFIG = {
    "sleep": ("Спальная мебель", "country"),
    "kitchen": ("Кухонная мебель", "subcategory"),
    "soft": ("Мягкая мебель", "country"),
    "tables": ("Столы и стулья", "country"),
    "cabinets": ("Тумбы и комоды", None),
    "mattresses": ("Матрасы", None),
    "beds": ("Кровати", None),
    "wardrobes": ("Шкафы", None),
}

# Эмодзи используются в заголовке карточки товара.
CATEGORY_ICONS = {
    "sleep": "🛏️",
    "kitchen": "🍳",
    "soft": "🛋️",
    "tables": "📚",
    "cabinets": "📺",
    "mattresses": "🛏️",
    "beds": "🛏️",
    "wardrobes": "📦",
}


def _keyboard(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def main_menu() -> InlineKeyboardMarkup:
    return _keyboard([[InlineKeyboardButton(text=text, callback_data=data)] for text, data in CATEGORY_BUTTONS])


def country_menu(category_key: str) -> InlineKeyboardMarkup:
    return _keyboard(
        [
            [InlineKeyboardButton(text="🇷🇺 Россия", callback_data=f"filter:{category_key}:country:Россия")],
            [InlineKeyboardButton(text="🇹🇷 Турция", callback_data=f"filter:{category_key}:country:Турция")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back:main")],
        ]
    )


def kitchen_menu() -> InlineKeyboardMarkup:
    return _keyboard(
        [
            [InlineKeyboardButton(text="📏 Прямая кухня", callback_data="filter:kitchen:subcategory:Прямая")],
            [InlineKeyboardButton(text="📐 Угловая кухня", callback_data="filter:kitchen:subcategory:Угловая")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back:main")],
        ]
    )


def products_menu(
    products: list,
    category_key: str,
    filter_type: str | None = None,
    filter_value: str | None = None,
    page: int = 0,
    total: int = 0,
) -> InlineKeyboardMarkup:
    # Контекст фильтра сохраняется в кнопке, чтобы вернуть пользователя к списку.
    rows = [
        [
            InlineKeyboardButton(
                text=product.name,
                callback_data=(
                    f"product:{product.id}:{category_key}:{filter_type or ''}:{filter_value or ''}:{page}"
                ),
            )
        ]
        for product in products
    ]
    total_pages = max((total + 4) // 5, 1)
    navigation = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                text="◀️",
                callback_data=f"page:{category_key}:{page - 1}:{filter_type or ''}:{filter_value or ''}",
            )
        )
    navigation.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page + 1 < total_pages:
        navigation.append(
            InlineKeyboardButton(
                text="▶️",
                callback_data=f"page:{category_key}:{page + 1}:{filter_type or ''}:{filter_value or ''}",
            )
        )
    if navigation:
        rows.append(navigation)
    rows.append([InlineKeyboardButton(text="◀️ В главное меню", callback_data="back:main")])
    return _keyboard(rows)


def product_menu(
    category_key: str,
    filter_type: str | None,
    filter_value: str | None,
    page: int = 0,
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="◀️ К списку товаров",
                callback_data=(
                    f"page:{category_key}:{page}:{filter_type or ''}:{filter_value or ''}"
                ),
            )
        ]
    ]
    rows.append([InlineKeyboardButton(text="🏠 В главное меню", callback_data="back:main")])
    return _keyboard(rows)
