"""CRUD каталога и пользователей: категории, товары, подкатегории, админы.

Сессии берём через engine.AsyncSessionLocal в момент вызова — тесты
подменяют атрибут в database.engine, и обе половины CRUD это учитывают.
"""
from sqlalchemy import func, select, update
from sqlalchemy.orm import selectinload

from database import engine
from database.models import Category, Furniture, FurniturePhoto, User

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
    async with engine.AsyncSessionLocal() as session:
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
    async with engine.AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()


async def get_categories() -> list[Category]:
    """Вернуть категории каталога в порядке их добавления."""
    async with engine.AsyncSessionLocal() as session:
        result = await session.execute(select(Category).order_by(Category.id))
        return list(result.scalars().all())


async def get_category_by_id(category_id: int) -> Category | None:
    """Найти категорию по идентификатору из callback-кнопки."""
    async with engine.AsyncSessionLocal() as session:
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

    async with engine.AsyncSessionLocal() as session:
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

    async with engine.AsyncSessionLocal() as session:
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

    async with engine.AsyncSessionLocal() as session:
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

    async with engine.AsyncSessionLocal() as session:
        result = await session.execute(query)
        return result.scalar_one_or_none()


async def get_category_by_name(name: str) -> Category | None:
    """Проверить уникальность имени категории перед созданием."""
    async with engine.AsyncSessionLocal() as session:
        result = await session.execute(select(Category).where(Category.name == name))
        return result.scalar_one_or_none()


async def create_category(name: str, description: str | None = None) -> Category:
    """Добавить категорию каталога."""
    async with engine.AsyncSessionLocal() as session:
        category = Category(name=name, description=description)
        session.add(category)
        await session.commit()
        await session.refresh(category)
        return category


async def get_categories_with_counts() -> list[tuple[Category, int]]:
    """Вернуть категории с числом товаров для админ-меню."""
    query = (
        select(Category, func.count(Furniture.id))
        .outerjoin(Furniture, Furniture.category_name == Category.name)
        .group_by(Category.id)
        .order_by(Category.id)
    )
    async with engine.AsyncSessionLocal() as session:
        result = await session.execute(query)
        return [(category, int(count)) for category, count in result.all()]


async def delete_category(category_id: int) -> bool:
    """Удалить категорию вместе с её товарами и фотографиями."""
    async with engine.AsyncSessionLocal() as session:
        category = await session.get(Category, category_id)
        if category is None:
            return False

        # Каскад на уровне ORM: сначала загружаем товары вместе с фото.
        result = await session.execute(
            select(Furniture)
            .options(selectinload(Furniture.photos))
            .where(Furniture.category_name == category.name)
        )
        for product in result.scalars().all():
            await session.delete(product)
        await session.delete(category)
        await session.commit()
        return True


async def create_furniture_with_photos(
    name: str,
    description: str | None,
    category_name: str,
    category_id: int,
    country: str | None = None,
    subcategory: str | None = None,
    whatsapp_contact: str | None = None,
    telegram_contact: str | None = None,
    price: int | None = None,
    photos: list[tuple[str, str]] | None = None,
) -> Furniture:
    """Создать товар и его фотографии одной транзакцией.

    Каждый элемент photos — пара (file_id, file_path).
    """
    async with engine.AsyncSessionLocal() as session:
        product = Furniture(
            name=name,
            description=description,
            category_name=category_name,
            category_id=category_id,
            country=country,
            subcategory=subcategory,
            whatsapp_contact=whatsapp_contact,
            telegram_contact=telegram_contact,
            price=price,
        )
        for file_id, file_path in photos or []:
            product.photos.append(
                FurniturePhoto(file_id=file_id, file_path=file_path)
            )
        session.add(product)
        await session.commit()
        # refresh() не загружает связи: без этой выборки обращение к
        # product.photos после закрытия сессии упадёт с DetachedInstanceError.
        result = await session.execute(
            select(Furniture)
            .options(selectinload(Furniture.photos))
            .where(Furniture.id == product.id)
        )
        return result.scalar_one()


async def delete_furniture(furniture_id: int) -> bool:
    """Удалить товар вместе с фотографиями."""
    async with engine.AsyncSessionLocal() as session:
        result = await session.execute(
            select(Furniture)
            .options(selectinload(Furniture.photos))
            .where(Furniture.id == furniture_id)
        )
        product = result.scalar_one_or_none()
        if product is None:
            return False

        await session.delete(product)
        await session.commit()
        return True


async def get_subcategories_with_counts(category_name: str) -> list[tuple[str, int]]:
    """Вернуть подкатегории категории с числом занимаемых товаров."""
    query = (
        select(Furniture.subcategory, func.count(Furniture.id))
        .where(
            Furniture.category_name == category_name,
            Furniture.subcategory.is_not(None),
        )
        .group_by(Furniture.subcategory)
        .order_by(Furniture.subcategory)
    )
    async with engine.AsyncSessionLocal() as session:
        result = await session.execute(query)
        return [(str(value), int(count)) for value, count in result.all()]


async def clear_subcategory(category_name: str, value: str) -> int:
    """Убрать подкатегорию у всех товаров; сами товары остаются в каталоге."""
    query = (
        update(Furniture)
        .where(Furniture.category_name == category_name, Furniture.subcategory == value)
        .values(subcategory=None)
    )
    async with engine.AsyncSessionLocal() as session:
        result = await session.execute(query)
        await session.commit()
        return int(getattr(result, "rowcount", 0))


async def get_admin_ids() -> list[int]:
    """Telegram-идентификаторы всех администраторов для рассылки заявок."""
    async with engine.AsyncSessionLocal() as session:
        result = await session.execute(
            select(User.telegram_id).where(User.is_admin.is_(True))
        )
        return [int(telegram_id) for telegram_id in result.scalars().all()]
