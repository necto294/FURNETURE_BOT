"""Публичный фасад CRUD-функций.

Имплементация разнесена по доменам: crud_catalog.py (категории, товары,
подкатегории, пользователи) и crud_orders.py (заявки). Внешний код
импортирует всё отсюда — точка входа не менялась с момента разделения.
"""
from database.crud_catalog import (
    REQUIRED_COUNTRIES,
    REQUIRED_KITCHEN_TYPES,
    clear_subcategory,
    create_category,
    create_furniture_with_photos,
    delete_category,
    delete_furniture,
    get_admin_ids,
    get_categories,
    get_categories_with_counts,
    get_category_by_id,
    get_category_by_name,
    get_filter_values,
    get_furniture_by_id,
    get_furniture_list,
    get_furniture_page,
    get_subcategories_with_counts,
    get_user_by_telegram_id,
    upsert_user,
)
from database.crud_orders import (
    create_order,
    get_all_orders_full,
    get_order_by_id_full,
    get_order_status_counts,
    get_orders_page,
    update_order_status,
)

__all__ = [
    "REQUIRED_COUNTRIES",
    "REQUIRED_KITCHEN_TYPES",
    "clear_subcategory",
    "create_category",
    "create_furniture_with_photos",
    "create_order",
    "delete_category",
    "delete_furniture",
    "get_admin_ids",
    "get_all_orders_full",
    "get_categories",
    "get_categories_with_counts",
    "get_category_by_id",
    "get_category_by_name",
    "get_filter_values",
    "get_furniture_by_id",
    "get_furniture_list",
    "get_furniture_page",
    "get_order_by_id_full",
    "get_order_status_counts",
    "get_orders_page",
    "get_subcategories_with_counts",
    "get_user_by_telegram_id",
    "update_order_status",
    "upsert_user",
]
