"""Начальная схема каталога, пользователей и заявок

Revision ID: d86de4abbf3e
Revises:
Create Date: 2026-08-19 20:57:49.392436

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d86de4abbf3e"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Создать все таблицы текущей схемы (ADR 0004: единая чистая ревизия)."""
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_categories_id"), "categories", ["id"], unique=False)

    op.create_table(
        "users",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column("first_name", sa.String(), nullable=True),
        sa.Column("last_name", sa.String(), nullable=True),
        sa.Column("registration_date", sa.DateTime(), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_telegram_id"), "users", ["telegram_id"], unique=True)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    op.create_table(
        "furniture",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("category_name", sa.String(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("subcategory", sa.String(), nullable=True),
        sa.Column("whatsapp_contact", sa.String(), nullable=True),
        sa.Column("telegram_contact", sa.String(), nullable=True),
        sa.Column("price", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["category_name"], ["categories.name"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_furniture_id"), "furniture", ["id"], unique=False)

    op.create_table(
        "furniture_photos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("furniture_id", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.String(), nullable=False),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["furniture_id"], ["furniture.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_furniture_photos_id"), "furniture_photos", ["id"], unique=False)

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("furniture_id", sa.Integer(), nullable=False),
        sa.Column("customer_name", sa.String(), nullable=True),
        sa.Column("customer_phone", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="new"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["furniture_id"], ["furniture.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_orders_id"), "orders", ["id"], unique=False)

    # Стандартные категории каталога (сид).
    connection = op.get_bind()
    for name, description in (
        ("Спальная мебель", "Мебель для спальни"),
        ("Кухонная мебель", "Кухонные гарнитуры и мебель"),
        ("Мягкая мебель", "Диваны, кресла и другая мягкая мебель"),
        ("Столы и стулья", "Столы и стулья для дома"),
        ("Тумбы и комоды", "Тумбы и комоды"),
        ("Матрасы", "Матрасы для спальни"),
        ("Кровати", "Кровати разных моделей"),
        ("Шкафы", "Шкафы-купе и гардеробные"),
    ):
        connection.execute(
            sa.text(
                "INSERT INTO categories (name, description, created_at) "
                "VALUES (:name, :description, CURRENT_TIMESTAMP)"
            ),
            {"name": name, "description": description},
        )


def downgrade() -> None:
    """Удалить все таблицы схемы."""
    op.drop_table("orders")
    op.drop_index(op.f("ix_furniture_photos_id"), table_name="furniture_photos")
    op.drop_table("furniture_photos")
    op.drop_index(op.f("ix_furniture_id"), table_name="furniture")
    op.drop_table("furniture")
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_index(op.f("ix_users_telegram_id"), table_name="users")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_table("users")
    op.drop_index(op.f("ix_categories_id"), table_name="categories")
    op.drop_table("categories")
