from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from .engine import Base


# Пользователь Telegram-бота и его права доступа.
class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid4()))
    # telegram_id — 64-битный идентификатор Telegram; Postgres INTEGER (32 бита)
    # переполняется на больших ID — только BIGINT/Integer64 вмещает любой валидный.
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True)
    first_name = Column(String)
    last_name = Column(String)
    registration_date = Column(DateTime, default=datetime.now)
    is_admin = Column(Boolean, default=False, nullable=False)


# Категория, к которой относится мебель.
class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String)
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<Category(id={self.id}, name='{self.name}')>"


# Подкатегория категории. Товар ссылается на неё по имени через
# Furniture.subcategory. Удаление удаляет запись целиком, а метка у товаров
# стирается — они уходят в раздел «Остальные».
class Subcategory(Base):
    __tablename__ = "subcategories"

    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<Subcategory(id={self.id}, name='{self.name}')>"


# Контракт каталога для админ-панели: пользовательская часть читает эти поля как есть.
# category_name — точное имя из categories.name (например «Кухонная мебель»).
# country — «Россия» или «Турция»; subcategory для кухни — «Прямая» или «Угловая».
# В Telegram уходит FurniturePhoto.file_id, полученный при загрузке фото.
class Furniture(Base):
    __tablename__ = "furniture"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String)
    category_name = Column(String, ForeignKey("categories.name"), nullable=False)
    category_id = Column(Integer, nullable=False)
    country = Column(String)
    subcategory = Column(String)
    # Контакты задаёт администратор при добавлении товара.
    whatsapp_contact = Column(String)
    telegram_contact = Column(String)
    # Цена в рублях целым числом; None — «не указана».
    price = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)

    photos = relationship("FurniturePhoto", back_populates="furniture", cascade="all, delete-orphan")


# Фотография товара, сохранённая в Telegram и локально.
class FurniturePhoto(Base):
    __tablename__ = "furniture_photos"

    id = Column(Integer, primary_key=True, index=True)
    furniture_id = Column(Integer, ForeignKey("furniture.id"), nullable=False)
    file_id = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    furniture = relationship("Furniture", back_populates="photos")


# Заявка на покупку товара.
class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    furniture_id = Column(Integer, ForeignKey("furniture.id"), nullable=False)
    # Имя и телефон из формы заявки; нужны админу в разделе «Заявки».
    customer_name = Column(String)
    customer_phone = Column(String)
    status = Column(String, default="new", nullable=False)  # new, processing, completed, cancelled
    created_at = Column(DateTime, default=datetime.now)

    user = relationship("User")
    furniture = relationship("Furniture")
