"""Имя и телефон покупателя в заявке

Ревизия устойчива к состоянию базы: таблица orders отсутствовала
в предыдущих миграциях проекта, поэтому здесь она создаётся целиком,
если её ещё нет. В существующей таблице просто добавляются колонки.

Revision ID: c4d9e7f2a8b3
Revises: f8b2d4c6a9e1
Create Date: 2026-08-22

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4d9e7f2a8b3"
down_revision: str | Sequence[str] | None = "f8b2d4c6a9e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORDERS_COLUMNS = (
    sa.Column("customer_name", sa.String(), nullable=True),
    sa.Column("customer_phone", sa.String(), nullable=True),
)


def _table_names() -> list[str]:
    return sa.inspect(op.get_bind()).get_table_names()


def _column_names(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if "orders" not in _table_names():
        # Полная схема из models.Order: раньше таблица не создавалась совсем.
        op.create_table(
            "orders",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("furniture_id", sa.Integer(), nullable=False),
            *ORDERS_COLUMNS,
            sa.Column("status", sa.String(), nullable=False, server_default="new"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["furniture_id"], ["furniture.id"]),
        )
        return

    existing_columns = _column_names("orders")
    for column in ORDERS_COLUMNS:
        if column.name not in existing_columns:
            op.add_column("orders", column.copy())


def downgrade() -> None:
    if "orders" not in _table_names():
        return

    existing_columns = _column_names("orders")
    # В обратном порядке, чтобы не зависеть от особенностей SQLite.
    for column in reversed(ORDERS_COLUMNS):
        if column.name in existing_columns:
            op.drop_column("orders", column.name)
