"""Расширяем users.telegram_id до BIGINT

telegram_id — 64-битный идентификатор Telegram; Postgres INTEGER (32 бита)
переполняется на больших ID (NumericValueOutOfRange), поэтому столбец
расширяется до BIGINT.

Revision ID: ecb821d8dbe4
Revises: e9f4b8c2d6a7
Create Date: 2026-08-28 22:59:06.860873

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "ecb821d8dbe4"
down_revision: str | Sequence[str] | None = "e9f4b8c2d6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "telegram_id",
        existing_type=sa.INTEGER(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "telegram_id",
        existing_type=sa.BigInteger(),
        type_=sa.INTEGER(),
        existing_nullable=False,
    )
