"""Seed catalog categories

Revision ID: 9c3e2a1b7d4f
Revises: 6fc3959c181a
Create Date: 2026-08-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9c3e2a1b7d4f"
down_revision: Union[str, Sequence[str], None] = "6fc3959c181a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Начальные категории совпадают с текущим пользовательским каталогом.
CATEGORY_ROWS = (
    ("Спальная мебель", "Мебель для спальни"),
    ("Кухонная мебель", "Кухонные гарнитуры и мебель"),
    ("Мягкая мебель", "Диваны, кресла и другая мягкая мебель"),
    ("Столы и стулья", "Столы и стулья для дома"),
    ("Тумбы и комоды", "Тумбы и комоды"),
    ("Матрасы", "Матрасы для спальни"),
    ("Кровати", "Кровати разных моделей"),
    ("Шкафы", "Шкафы-купе и гардеробные"),
)


def upgrade() -> None:
    """Добавить стандартные категории каталога."""
    connection = op.get_bind()
    for name, description in CATEGORY_ROWS:
        connection.execute(
            sa.text(
                "INSERT OR IGNORE INTO categories (name, description, created_at) "
                "VALUES (:name, :description, CURRENT_TIMESTAMP)"
            ),
            {"name": name, "description": description},
        )


def downgrade() -> None:
    """Удалить только стандартные категории, созданные этой миграцией."""
    connection = op.get_bind()
    for name, _ in CATEGORY_ROWS:
        connection.execute(
            sa.text("DELETE FROM categories WHERE name = :name"),
            {"name": name},
        )
