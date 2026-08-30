from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Все callback_data админ-части имеют префикс adm:, чтобы не пересекаться
# с колбэками пользовательского каталога.
ADMIN_PAGE_SIZE = 5


def _keyboard(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _cancel_button(text: str = "❌ Отменить") -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data="adm:cancel")


def admin_main_menu() -> InlineKeyboardMarkup:
    """Главное меню админ-панели."""
    return _keyboard(
        [
            [InlineKeyboardButton(text="🪑 Добавить товар", callback_data="adm:addfurn")],
            [InlineKeyboardButton(text="🗑 Удалить товар", callback_data="adm:delfurn")],
            [InlineKeyboardButton(text="➕ Добавить категорию", callback_data="adm:addcat")],
            [InlineKeyboardButton(text="❌ Удалить категорию", callback_data="adm:delcat")],
            [InlineKeyboardButton(text="🧩 Подкатегории", callback_data="adm:subcat")],
            [InlineKeyboardButton(text="📨 Заявки", callback_data="adm:orders")],
            [InlineKeyboardButton(text="🏠 В главное меню", callback_data="back:main")],
        ]
    )


def categories_menu(
    items: list[tuple[object, int]],
    action_prefix: str,
) -> InlineKeyboardMarkup:
    """Список категорий с количеством товаров.

    action_prefix задаёт действие: например adm:delcat или adm:delfurn.
    """
    rows = []
    for category, count in items:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{category.name} ({count})",
                    callback_data=f"{action_prefix}:{category.id}",
                )
            ]
        )
    rows.append([_cancel_button("◀️ Назад в админку")])
    return _keyboard(rows)


def countries_menu() -> InlineKeyboardMarkup:
    """Выбор страны производства при добавлении товара."""
    return _keyboard(
        [
            [InlineKeyboardButton(text="🇷🇺 Россия", callback_data="adm:country:Россия")],
            [InlineKeyboardButton(text="🇹🇷 Турция", callback_data="adm:country:Турция")],
            [_cancel_button()],
        ]
    )


def kitchen_types_menu(types: list[str]) -> InlineKeyboardMarkup:
    """Выбор подкатегории кухни; значения берутся из базы данных."""
    icons = {"Прямая": "📏", "Угловая": "📐"}
    rows = [
        [
            InlineKeyboardButton(
                text=f"{icons.get(value, '🧩')} {value}",
                callback_data=f"adm:ktype:{value}",
            )
        ]
        for value in types
    ]
    rows.append([_cancel_button()])
    return _keyboard(rows)


def subcategories_menu(
    items: list[tuple[int, str, int]],
    category_id: int,
) -> InlineKeyboardMarkup:
    """Список подкатегорий категории: удаление и добавление.

    items — кортежи (id, имя, счётчик товаров).
    """
    rows = [
        [
            InlineKeyboardButton(
                text=f"{value} ({count})",
                callback_data=f"adm:scdel:{subcategory_id}",
            )
        ]
        for subcategory_id, value, count in items
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text="➕ Добавить подкатегорию",
                callback_data=f"adm:scadd:{category_id}",
            )
        ]
    )
    rows.append([_cancel_button("◀️ Назад к категориям")])
    return _keyboard(rows)


def photos_menu() -> InlineKeyboardMarkup:
    """Меню сбора фотографий товара."""
    return _keyboard(
        [
            [InlineKeyboardButton(text="✅ Готово, сохранить", callback_data="adm:savefurn")],
            [_cancel_button()],
        ]
    )


def confirm_menu(confirm_callback: str) -> InlineKeyboardMarkup:
    """Диалог подтверждения опасного действия."""
    return _keyboard(
        [
            [
                InlineKeyboardButton(text="✅ Да, удалить", callback_data=confirm_callback),
                _cancel_button(),
            ]
        ]
    )


def furniture_list_menu(
    products: list,
    category_id: int,
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    """Список товаров категории для удаления с постраничной навигацией."""
    rows = [
        [
            InlineKeyboardButton(
                text=str(product.name),
                callback_data=f"adm:delp:{product.id}:{category_id}:{page}",
            )
        ]
        for product in products
    ]

    navigation = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                text="◀️",
                callback_data=f"adm:delfurn:{category_id}:{page - 1}",
            )
        )
    navigation.append(
        InlineKeyboardButton(
            text=f"{page + 1}/{max(total_pages, 1)}",
            callback_data="adm:noop",
        )
    )
    if page + 1 < total_pages:
        navigation.append(
            InlineKeyboardButton(
                text="▶️",
                callback_data=f"adm:delfurn:{category_id}:{page + 1}",
            )
        )
    if navigation:
        rows.append(navigation)
    rows.append([_cancel_button("◀️ Другая категория")])
    return _keyboard(rows)


def back_to_admin_menu() -> InlineKeyboardMarkup:
    return _keyboard(
        [[InlineKeyboardButton(text="◀️ В админку", callback_data="adm:menu")]]
    )


# Метки статусов заявки для карточки и списка.
ORDER_STATUS_LABELS = {
    "new": "🆕 Новая",
    "processing": "🔧 В работе",
    "completed": "✅ Выполнена",
    "cancelled": "🚫 Отменена",
}

# Те же метки без эмодзи — для колонки «Статус» в CSV-выгрузке.
ORDER_STATUS_CSV_LABELS = {
    "new": "Новая",
    "processing": "В работе",
    "completed": "Выполнена",
    "cancelled": "Отменена",
}


def orders_list_menu(
    orders: list,
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    """Список заявок с постраничной навигацией."""
    rows = [
        [
            InlineKeyboardButton(
                text=(
                    f"№{order.id} · "
                    f"{ORDER_STATUS_LABELS.get(order.status, order.status)} · "
                    f"{order.furniture.name if order.furniture else '?'}"
                ),
                callback_data=f"adm:order:{order.id}:{page}",
            )
        ]
        for order in orders
    ]

    navigation = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(text="◀️", callback_data=f"adm:orders:{page - 1}")
        )
    navigation.append(
        InlineKeyboardButton(
            text=f"{page + 1}/{max(total_pages, 1)}", callback_data="adm:noop"
        )
    )
    if page + 1 < total_pages:
        navigation.append(
            InlineKeyboardButton(text="▶️", callback_data=f"adm:orders:{page + 1}")
        )
    if navigation:
        rows.append(navigation)
    rows.append(
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="adm:ostats"),
            InlineKeyboardButton(text="⬇️ Экспорт CSV", callback_data="adm:oexport"),
        ]
    )
    rows.append([_cancel_button("◀️ В админку")])
    return _keyboard(rows)


def orders_stats_menu() -> InlineKeyboardMarkup:
    """Кнопки экрана статистики заявок."""
    return _keyboard(
        [
            [InlineKeyboardButton(text="⬇️ Экспорт CSV", callback_data="adm:oexport")],
            [
                InlineKeyboardButton(
                    text="◀️ К заявкам", callback_data="adm:orders"
                )
            ],
        ]
    )


def order_card_menu(order_id: int, status: str, page: int) -> InlineKeyboardMarkup:
    """Кнопки смены статуса заявки; текущий статус помечается галочкой."""
    actions = [
        ("new", "🆕 Новая"),
        ("processing", "🔧 В работу"),
        ("completed", "✅ Выполнена"),
        ("cancelled", "🚫 Отменить"),
    ]

    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for value, title in actions:
        mark = "✅ " if value == status else ""
        row.append(
            InlineKeyboardButton(
                text=f"{mark}{title}",
                callback_data=f"adm:ost:{order_id}:{value}:{page}",
            )
        )
        # По две кнопки в ряд, чтобы не слипались.
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append(
        [InlineKeyboardButton(text="◀️ К списку заявок", callback_data=f"adm:orders:{page}")]
    )
    return _keyboard(rows)
