from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from uuid import uuid4
from datetime import datetime

from .engine import Base


# Пользователь Telegram-бота и его права доступа.
class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid4()))
    telegram_id = Column(Integer, unique=True, index=True, nullable=False)
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
