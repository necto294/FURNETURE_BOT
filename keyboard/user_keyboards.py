from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

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


def main_menu(categories: list) -> InlineKeyboardMarkup:
    """Построить главное меню из категорий, загруженных из базы."""
    rows = []
    for category in categories:
        category_name = str(category.name)
        category_key = next(
            (key for key, (name, _) in CATEGORY_CONFIG.items() if name == category_name),
            category_name,
        )
        icon = CATEGORY_ICONS.get(category_key, "🪑")
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{icon} {category_name}",
                    callback_data=f"category:{category.id}",
                )
            ]
        )
    return _keyboard(rows)


def empty_catalog_menu() -> InlineKeyboardMarkup:
    """Показать кнопку возврата к каталогу после пустого результата."""
    return _keyboard(
        [
            [
                InlineKeyboardButton(
                    text="🏠 Вернуться в каталог",
                    callback_data="back:main",
                )
            ]
        ]
    )


def subcategory_menu(category_key: str, values: list[str]) -> InlineKeyboardMarkup:
    """Выбор подкатегории: после него открывается шаг страны."""
    rows = []
    for value in values:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"📐 {value}",
                    callback_data=f"filtersub:{category_key}:{value}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back:main")])
    return _keyboard(rows)


def country_menu(
    category_key: str,
    countries: list[str],
    subcategory: str = "",
) -> InlineKeyboardMarkup:
    """Выбор страны; подкатегория (если выбрана) вшита в кнопку для фильтра."""
    rows = []
    for value in countries:
        icon = "🇷🇺" if value == "Россия" else "🇹🇷" if value == "Турция" else "🌍"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{icon} {value}",
                    callback_data=f"country:{category_key}:{subcategory}:{value}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back:main")])
    return _keyboard(rows)


def products_menu(
    products: list,
    category_key: str,
    subcategory: str = "",
    country: str = "",
    page: int = 0,
    total: int = 0,
) -> InlineKeyboardMarkup:
    # Контекст фильтра сохраняется в кнопке, чтобы вернуть пользователя к списку.
    rows = [
        [
            InlineKeyboardButton(
                text=product.name,
                callback_data=(
                    f"product:{product.id}:{category_key}:{subcategory}:{country}:{page}"
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
                callback_data=f"page:{category_key}:{page - 1}:{subcategory}:{country}",
            )
        )
    navigation.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page + 1 < total_pages:
        navigation.append(
            InlineKeyboardButton(
                text="▶️",
                callback_data=f"page:{category_key}:{page + 1}:{subcategory}:{country}",
            )
        )
    if navigation:
        rows.append(navigation)
    rows.append([InlineKeyboardButton(text="◀️ В главное меню", callback_data="back:main")])
    return _keyboard(rows)


def product_menu(
    product_id: int,
    category_key: str,
    subcategory: str = "",
    country: str = "",
    page: int = 0,
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="◀️ К списку товаров",
                callback_data=(
                    f"page:{category_key}:{page}:{subcategory}:{country}"
                ),
            )
        ]
    ]
    # Кнопка заявки несёт id товара, чтобы FSM знал, что оформляем.
    rows.append(
        [
            InlineKeyboardButton(
                text="📩 Отправить заявку",
                callback_data=f"order:{product_id}",
            )
        ]
    )
    rows.append([InlineKeyboardButton(text="🏠 В главное меню", callback_data="back:main")])
    return _keyboard(rows)


def cancel_order_menu() -> InlineKeyboardMarkup:
    """Показать кнопку отмены во время ввода имени или телефона."""
    # Один и тот же callback гасит FSM в любом состоянии заявки.
    return _keyboard(
        [
            [
                InlineKeyboardButton(
                    text="❌ Отменить заявку",
                    callback_data="order:cancel",
                )
            ]
        ]
    )


def order_confirmation_menu() -> InlineKeyboardMarkup:
    """Подтвердить или отменить оформленную заявку."""
    return _keyboard(
        [
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data="order:confirm",
                ),
                InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data="order:cancel",
                ),
            ]
        ]
    )


def back_to_main_menu() -> InlineKeyboardMarkup:
    """Одна кнопка для возврата в главное меню после завершения заявки."""
    return _keyboard(
        [
            [
                InlineKeyboardButton(
                    text="🏠 В главное меню",
                    callback_data="back:main",
                )
            ]
        ]
    )
