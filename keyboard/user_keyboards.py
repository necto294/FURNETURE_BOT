from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


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
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=product.name,
                callback_data=(
                    f"product:{product.id}:{category_key}:{filter_type or ''}:{filter_value or ''}"
                ),
            )
        ]
        for product in products
    ]
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back:main")])
    return _keyboard(rows)


def product_menu(category_key: str, filter_type: str | None, filter_value: str | None) -> InlineKeyboardMarkup:
    rows = []
    if filter_type and filter_value:
        rows.append(
            [
                InlineKeyboardButton(
                    text="◀️ К списку товаров",
                    callback_data=f"filter:{category_key}:{filter_type}:{filter_value}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="🏠 В главное меню", callback_data="back:main")])
    return _keyboard(rows)
