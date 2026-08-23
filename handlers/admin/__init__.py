"""Составление админ-роутера из доменных модулей.

Родительский роутер с меню живёт в router.py; сюда подключаются доменные
потоки и навешивается общий middleware доступа из access.py.
"""
from .access import setup_admin_access
from .categories import router as categories_router
from .furniture import router as furniture_router
from .furniture_delete import router as furniture_delete_router
from .orders import router as orders_router
from .router import router
from .subcategories import router as subcategories_router

# Порядок включения: категории → добавление товара → удаление товара →
# подкатегории → заявки.
router.include_routers(
    categories_router,
    furniture_router,
    furniture_delete_router,
    subcategories_router,
    orders_router,
)
setup_admin_access(router)

__all__ = ["router"]
