"""CRUD каталога и пользователей: категории, товары, подкатегории, админы.

Сессии берём через engine.AsyncSessionLocal в момент вызова — тесты
подменяют атрибут в database.engine, и обе половины CRUD это учитывают.
"""
from sqlalchemy import func, select, update
from sqlalchemy.orm import selectinload

from database import engine
from database.models import Category, Furniture, FurniturePhoto, Subcategory, User

# Эти варианты должны быть доступны до появления соответствующих товаров.
REQUIRED_COUNTRIES = ("Россия", "Турция")
REQUIRED_KITCHEN_TYPES = ("Прямая", "Угловая")

# Синтаксическое имя раздела «Остальные»: товары категории без подкатегории —
# они не имеют активной метки (подкатегория не указана или была удалена).
OTHERS_SUBCATEGORY = "__others__"


async def _get_subcategory_rows(category_id: int) -> list[Subcategory]:
    """Все записи подкатегорий категории."""
    async with engine.AsyncSessionLocal() as session:
        result = await session.execute(
            select(Subcategory)
            .where(Subcategory.category_id == category_id)
            .order_by(Subcategory.name)
        )
        return list(result.scalars().all())


async def get_active_subcategory_names(category_id: int) -> list[str]:
    """Имена подкатегорий категории для меню покупателя."""
    rows = await _get_subcategory_rows(category_id)
    return [row.name for row in rows]


async def _get_category_id(category_name: str) -> int | None:
    """Идентификатор категории по имени (для внутренних связок)."""
    async with engine.AsyncSessionLocal() as session:
        result = await session.execute(
            select(Category.id).where(Category.name == category_name)
        )
        return result.scalar_one_or_none()


def _others_condition():
    """Условие фильтра для раздела «Остальные»: товары без подкатегории."""
    return Furniture.subcategory.is_(None)


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
    filters = [Furniture.category_name == category_name]
    if country is not None:
        filters.append(Furniture.country == country)
    if subcategory == OTHERS_SUBCATEGORY:
        filters.append(_others_condition())
    elif subcategory is not None:
        filters.append(Furniture.subcategory == subcategory)

    query = (
        select(Furniture)
        .options(selectinload(Furniture.photos))
        .where(*filters)
        .order_by(Furniture.id)
    )

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
    if subcategory == OTHERS_SUBCATEGORY:
        filters.append(_others_condition())
    elif subcategory is not None:
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
    """Вернуть варианты фильтра категории.

    Для подкатегорий берём активные записи таблицы subcategories, для стран —
    уникальные значения у товаров плюс гарантированные варианты.
    """
    if filter_type == "subcategory":
        category_id = await _get_category_id(category_name)
        if category_id is None:
            return []
        values = await get_active_subcategory_names(category_id)
        if category_name == "Кухонная мебель":
            values.extend(
                kitchen_type
                for kitchen_type in REQUIRED_KITCHEN_TYPES
                if kitchen_type not in values
            )
        return sorted(values)

    # filter_type == "country": уникальные страны у товаров + гарантированные.
    query = (
        select(Furniture.country)
        .where(
            Furniture.category_name == category_name,
            Furniture.country.is_not(None),
        )
        .distinct()
        .order_by(Furniture.country)
    )
    async with engine.AsyncSessionLocal() as session:
        result = await session.execute(query)
        values = [str(value) for value in result.scalars().all()]
    values.extend(country for country in REQUIRED_COUNTRIES if country not in values)
    return sorted(values)


async def get_country_values(
    category_name: str, subcategory: str | None = None
) -> list[str]:
    """Вернуть страны, доступные товарам категории.

    При переданной активной подкатегории список сужается до стран, у которых
    в этой подкатегории есть товары. Для раздела «Остальные» — к товарам
    удалённых или неназванных подкатегорий. Гарантированные страны
    (Россия/Турция) добавляются всегда: страна выбирается для каждой категории.
    """
    query = (
        select(Furniture.country)
        .where(
            Furniture.category_name == category_name,
            Furniture.country.is_not(None),
        )
        .distinct()
        .order_by(Furniture.country)
    )
    if subcategory == OTHERS_SUBCATEGORY:
        query = query.where(_others_condition())
    elif subcategory is not None:
        query = query.where(Furniture.subcategory == subcategory)

    async with engine.AsyncSessionLocal() as session:
        result = await session.execute(query)
        values = [str(value) for value in result.scalars().all()]

    values.extend(country for country in REQUIRED_COUNTRIES if country not in values)
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


async def get_subcategories_with_counts(category_name: str) -> list[tuple[int, str, int]]:
    """Вернуть подкатегории категории: (id, имя, счётчик товаров).

    Список строится по таблице subcategories, к которому добавляются метки,
    встречающиеся у товаров, но ещё не внесённые в таблицу (legacy-данные).
    """
    category_id = await _get_category_id(category_name)
    if category_id is None:
        return []
    rows = await _get_subcategory_rows(category_id)

    query = (
        select(Furniture.subcategory, func.count(Furniture.id))
        .where(
            Furniture.category_name == category_name,
            Furniture.subcategory.is_not(None),
        )
        .group_by(Furniture.subcategory)
    )
    async with engine.AsyncSessionLocal() as session:
        result = await session.execute(query)
        counts = {str(value): int(count) for value, count in result.all()}

    items = [
        (row.id, row.name, counts.get(row.name, 0))
        for row in rows
    ]
    # Метки у товаров, которых ещё нет в таблице, добавляем.
    existing = {name for _, name, _ in items}
    for name, count in counts.items():
        if name not in existing:
            items.append((0, name, count))
    return sorted(items, key=lambda item: item[1])


async def get_others_count(category_name: str) -> int:
    """Сколько товаров попадёт в раздел «Остальные» категории.

    «Остальные» — товары категории без подкатегории. Раздел показывается
    только там, где есть записи подкатегорий (он дополняет их): у категории
    без подкатегорий все товары видны по стране напрямую.
    """
    category_id = await _get_category_id(category_name)
    if category_id is None:
        return 0
    rows = await _get_subcategory_rows(category_id)
    if not rows:
        return 0
    async with engine.AsyncSessionLocal() as session:
        count_query = (
            select(func.count())
            .select_from(Furniture)
            .where(
                Furniture.category_name == category_name,
                _others_condition(),
            )
        )
        return int(await session.scalar(count_query) or 0)


async def create_subcategory(category_id: int, name: str) -> Subcategory:
    """Создать подкатегорию; при существующей — вернуть её (уникальна по категории)."""
    async with engine.AsyncSessionLocal() as session:
        result = await session.execute(
            select(Subcategory).where(
                Subcategory.category_id == category_id,
                Subcategory.name == name,
            )
        )
        subcategory = result.scalar_one_or_none()
        if subcategory is None:
            subcategory = Subcategory(category_id=category_id, name=name)
            session.add(subcategory)
            await session.commit()
            await session.refresh(subcategory)
        return subcategory


async def get_subcategory_by_id(subcategory_id: int) -> Subcategory | None:
    """Найти подкатегорию по идентификатору."""
    async with engine.AsyncSessionLocal() as session:
        return await session.get(Subcategory, subcategory_id)


async def delete_subcategory(subcategory_id: int) -> int:
    """Полностью удалить подкатегорию и перенести её товары в «Остальные».

    Метка у товаров подкатегории стирается (уходят в раздел «Остальные»),
    сама запись удаляется целиком. Возвращает число перенесённых товаров.
    """
    async with engine.AsyncSessionLocal() as session:
        subcategory = await session.get(Subcategory, subcategory_id)
        if subcategory is None:
            return 0
        result = await session.execute(
            update(Furniture)
            .where(
                Furniture.category_id == subcategory.category_id,
                Furniture.subcategory == subcategory.name,
            )
            .values(subcategory=None)
        )
        count = int(getattr(result, "rowcount", 0))
        await session.delete(subcategory)
        await session.commit()
        return count


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
