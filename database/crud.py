from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from .engine import AsyncSessionLocal
from .models import Furniture


async def get_furniture_list(
    category_name: str,
    country: str | None = None,
    subcategory: str | None = None,
) -> list[Furniture]:
    """Вернуть товары категории с необязательной фильтрацией."""
    # Фотографии загружаются сразу, чтобы карточку можно было показать одной операцией.
    query = (
        select(Furniture)
        .options(selectinload(Furniture.photos))
        .where(Furniture.category_name == category_name)
        .order_by(Furniture.id)
    )

    # Фильтры добавляются только для выбранного пользователем режима.
    if country is not None:
        query = query.where(Furniture.country == country)
    if subcategory is not None:
        query = query.where(Furniture.subcategory == subcategory)

    async with AsyncSessionLocal() as session:
        result = await session.execute(query)
        return list(result.scalars().all())


async def get_furniture_page(
    category_name: str,
    page: int = 0,
    page_size: int = 5,
    country: str | None = None,
    subcategory: str | None = None,
) -> tuple[list[Furniture], int]:
    """Вернуть страницу товаров и общее количество совпадений."""
    filters = [Furniture.category_name == category_name]
    if country is not None:
        filters.append(Furniture.country == country)
    if subcategory is not None:
        filters.append(Furniture.subcategory == subcategory)

    offset = max(page, 0) * page_size
    count_query = select(func.count()).select_from(Furniture).where(*filters)
    items_query = (
        select(Furniture)
        .options(selectinload(Furniture.photos))
        .where(*filters)
        .order_by(Furniture.id)
        .offset(offset)
        .limit(page_size)
    )

    async with AsyncSessionLocal() as session:
        total = await session.scalar(count_query) or 0
        result = await session.execute(items_query)
        return list(result.scalars().all()), total


async def get_furniture_by_id(furniture_id: int) -> Furniture | None:
    """Вернуть товар вместе с фотографиями."""
    query = (
        select(Furniture)
        .options(selectinload(Furniture.photos))
        .where(Furniture.id == furniture_id)
    )

    async with AsyncSessionLocal() as session:
        result = await session.execute(query)
        return result.scalar_one_or_none()
