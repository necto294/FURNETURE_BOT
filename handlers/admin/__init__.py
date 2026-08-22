from . import orders
from .router import router

# Раздел заявок живёт в отдельном модуле с общими префиксами adm:.
router.include_router(orders.router)

__all__ = ["router"]
