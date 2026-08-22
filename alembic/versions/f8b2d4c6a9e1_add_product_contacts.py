"""Контакты товара вместо общих констант из .env

Revision ID: f8b2d4c6a9e1
Revises: 9c3e2a1b7d4f
Create Date: 2026-08-22

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f8b2d4c6a9e1"
down_revision: str | Sequence[str] | None = "9c3e2a1b7d4f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Контактные номера теперь индивидуальны для каждого товара.
    op.add_column("furniture", sa.Column("whatsapp_contact", sa.String(), nullable=True))
    op.add_column("furniture", sa.Column("telegram_contact", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("furniture", "telegram_contact")
    op.drop_column("furniture", "whatsapp_contact")
