"""CRUD заявок: создание, постраничные списки, карточка, статусы, экспорт.

Сессии берём через engine.AsyncSessionLocal в момент вызова — тесты
подменяют атрибут в database.engine, и обе половины CRUD это учитывают.
"""
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from database import engine
from database.models import Order


async def create_order(
    user_id: str,
    furniture_id: int,
    customer_name: str | None = None,
    customer_phone: str | None = None,
    status: str = "new",
) -> Order:
    """Создать новую заявку на покупку товара."""
    async with engine.AsyncSessionLocal() as session:
        order = Order(
            user_id=user_id,
            furniture_id=furniture_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            status=status,
        )
        session.add(order)
        await session.commit()
        await session.refresh(order)
        return order


async def update_order_status(order_id: int, new_status: str) -> Order | None:
    """Обновить статус заявки."""
    async with engine.AsyncSessionLocal() as session:
        order = await session.get(Order, order_id)
        if order is not None:
            order.status = new_status
            await session.commit()
            await session.refresh(order)
        return order


async def get_order_by_id_full(order_id: int) -> Order | None:
    """Вернуть заявку вместе с покупателем и товаром для карточки админа."""
    query = (
        select(Order)
        .options(selectinload(Order.user), selectinload(Order.furniture))
        .where(Order.id == order_id)
    )
    async with engine.AsyncSessionLocal() as session:
        result = await session.execute(query)
        return result.scalar_one_or_none()


async def get_orders_page(
    page: int = 0,
    page_size: int = 5,
    status: str | None = None,
) -> tuple[list[Order], int]:
    """Вернуть страницу заявок (новые сверху) и общее количество.

    Заявки загружаются вместе с покупателем и товаром.
    """
    filters = []
    if status is not None:
        filters.append(Order.status == status)

    count_query = select(func.count()).select_from(Order).where(*filters)
    items_query = (
        select(Order)
        .options(selectinload(Order.user), selectinload(Order.furniture))
        .where(*filters)
        .order_by(Order.id.desc())
        .offset(max(page, 0) * page_size)
        .limit(page_size)
    )

    async with engine.AsyncSessionLocal() as session:
        total = await session.scalar(count_query) or 0
        result = await session.execute(items_query)
        return list(result.scalars().all()), total


async def get_all_orders_full() -> list[Order]:
    """Все заявки с покупателем и товаром — для экспорта в CSV.

    Связи грузим сразу: после возврата объекты отсоединены.
    """
    query = (
        select(Order)
        .options(selectinload(Order.user), selectinload(Order.furniture))
        .order_by(Order.id.desc())
    )
    async with engine.AsyncSessionLocal() as session:
        result = await session.execute(query)
        return list(result.scalars().all())


async def get_order_status_counts() -> dict[str, int]:
    """Снимок статистики: число заявок в каждом статусе."""
    query = select(Order.status, func.count()).group_by(Order.status)
    async with engine.AsyncSessionLocal() as session:
        rows = await session.execute(query)
        return {status: int(count) for status, count in rows.all()}
