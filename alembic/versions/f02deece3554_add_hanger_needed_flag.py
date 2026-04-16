"""add_hanger_needed_flag

Revision ID: f02deece3554
Revises: bcf72847d6c9
Create Date: 2026-04-17 00:36:00.630136

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f02deece3554'
down_revision: Union[str, None] = 'bcf72847d6c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('hanger_needed', sa.Boolean(), server_default=sa.text('false'), nullable=True))


def downgrade() -> None:
    op.drop_column('orders', 'hanger_needed')
