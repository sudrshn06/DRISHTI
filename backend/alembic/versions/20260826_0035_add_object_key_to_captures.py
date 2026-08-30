"""add object_key to captures table

Revision ID: 20260826_7b01
Revises: 20260825_7a01
Create Date: 2026-08-26 00:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260826_7b01'
down_revision: Union[str, None] = '20260825_7a01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('captures', sa.Column('object_key', sa.String(length=255), nullable=True))
    op.create_index(op.f('ix_captures_object_key'), 'captures', ['object_key'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_captures_object_key'), table_name='captures')
    op.drop_column('captures', 'object_key')
