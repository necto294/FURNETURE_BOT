"""drop subcategory soft delete

Revision ID: 9e046db1dbeb
Revises: 9c6920cb0ae6
Create Date: 2026-08-30 21:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9e046db1dbeb'
down_revision: Union[str, Sequence[str], None] = '9c6920cb0ae6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Переходим с «мягкого» удаления подкатегорий на полное: записи, помеченные
    is_deleted, удаляются целиком, а метка у их товаров стирается — такие
    товары уходят в раздел «Остальные» (товары без подкатегории).
    """
    connection = op.get_bind()

    # Собираем имена удалённых подкатегорий по категориям.
    deleted = connection.execute(
        sa.text("SELECT category_id, name FROM subcategories WHERE is_deleted = 1")
    ).fetchall()

    for category_id, name in deleted:
        # Метка у товаров удалённой подкатегории стирается (перенос в «Остальные»).
        connection.execute(
            sa.text("UPDATE furniture SET subcategory = NULL "
                    "WHERE category_id = :cid AND subcategory = :name"),
            {"cid": category_id, "name": name},
        )
        # Сама запись подкатегории удаляется полностью.
        connection.execute(
            sa.text("DELETE FROM subcategories WHERE id IN ("
                    "SELECT id FROM subcategories WHERE category_id = :cid AND name = :name)"),
            {"cid": category_id, "name": name},
        )

    # Убираем колонку мягкого удаления.
    op.drop_column('subcategories', 'is_deleted')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        'subcategories',
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    connection = op.get_bind()
    connection.execute(
        sa.text("UPDATE subcategories SET is_deleted = 0")
    )
    op.alter_column('subcategories', 'is_deleted', server_default=None)
