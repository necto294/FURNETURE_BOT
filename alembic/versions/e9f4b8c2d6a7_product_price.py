"""Цена товара

Revision ID: e9f4b8c2d6a7
Revises: c4d9e7f2a8b3
Create Date: 2026-08-22

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e9f4b8c2d6a7"
down_revision: str | Sequence[str] | None = "c4d9e7f2a8b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Цена в рублях целым числом; пусто — «не указана».
    op.add_column("furniture", sa.Column("price", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("furniture", "price")
