from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from .engine import AsyncSessionLocal
from .models import Category, Furniture, Order, User


# Эти варианты должны быть доступны до появления соответствующих товаров.
REQUIRED_COUNTRIES = ("Россия", "Турция")
REQUIRED_KITCHEN_TYPES = ("Прямая", "Угловая")


async def upsert_user(
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
) -> User:
    """Создать пользователя по telegram_id или обновить его имя. is_admin не меняем."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
            )
            session.add(user)
        else:
            user.username = username
            user.first_name = first_name
            user.last_name = last_name

        await session.commit()
        await session.refresh(user)
        return user


async def get_user_by_telegram_id(telegram_id: int) -> User | None:
    """Найти пользователя по идентификатору Telegram."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()


async def get_categories() -> list[Category]:
    """Вернуть категории каталога в порядке их добавления."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Category).order_by(Category.id))
        return list(result.scalars().all())


async def get_category_by_id(category_id: int) -> Category | None:
    """Найти категорию по идентификатору из callback-кнопки."""
    async with AsyncSessionLocal() as session:
        return await session.get(Category, category_id)


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


async def get_filter_values(category_name: str, filter_type: str) -> list[str]:
    """Вернуть уникальные значения фильтра, сохранённые у товаров категории."""
    # Выбираем колонку фильтра динамически, но только из разрешённых полей модели.
    column = (
        Furniture.country
        if filter_type == "country"
        else Furniture.subcategory
    )
    query = (
        select(column)
        .where(Furniture.category_name == category_name, column.is_not(None))
        .distinct()
        .order_by(column)
    )

    async with AsyncSessionLocal() as session:
        result = await session.execute(query)
        values = [str(value) for value in result.scalars().all()]

    if filter_type == "country":
        values.extend(country for country in REQUIRED_COUNTRIES if country not in values)
    elif filter_type == "subcategory" and category_name == "Кухонная мебель":
        values.extend(
            kitchen_type
            for kitchen_type in REQUIRED_KITCHEN_TYPES
            if kitchen_type not in values
        )

    return sorted(values)


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


async def create_order(
    user_id: str,
    furniture_id: int,
    status: str = "new",
) -> Order:
    """Создать новую заявку на покупку товара."""
    from .models import Order
    async with AsyncSessionLocal() as session:
        order = Order(
            user_id=user_id,
            furniture_id=furniture_id,
            status=status,
        )
        session.add(order)
        await session.commit()
        await session.refresh(order)
        return order


async def get_order_by_id(order_id: int) -> Order | None:
    """Найти заявку по идентификатору."""
    from .models import Order
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Order).where(Order.id == order_id))
        return result.scalar_one_or_none()


async def get_user_orders(
    user_id: str,
    status: str | None = None,
) -> list[Order]:
    """Вернуть список заявок пользователя, опционально отфильтрованных по статусу."""
    from .models import Order
    async with AsyncSessionLocal() as session:
        query = select(Order).where(Order.user_id == user_id)
        if status is not None:
            query = query.where(Order.status == status)
        result = await session.execute(query)
        return list(result.scalars().all())


async def update_order_status(order_id: int, new_status: str) -> Order | None:
    """Обновить статус заявки."""
    from .models import Order
    async with AsyncSessionLocal() as session:
        order = await session.get(Order, order_id)
        if order is not None:
            order.status = new_status
            await session.commit()
            await session.refresh(order)
        return order
