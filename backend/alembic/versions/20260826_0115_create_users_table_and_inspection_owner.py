"""create users table and inspection ownership

Revision ID: 20260826_7c01
Revises: 20260826_7b01
Create Date: 2026-08-26 01:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260826_7c01'
down_revision: Union[str, None] = '20260826_7b01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Create users table
    op.create_table(
        'users',
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=100), nullable=False),
        sa.Column('role', sa.String(length=30), server_default='INSPECTOR', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('user_id')
    )
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # 2. Add created_by_user_id column to inspections table
    op.add_column('inspections', sa.Column('created_by_user_id', sa.String(length=36), nullable=True))
    op.create_index(op.f('ix_inspections_created_by_user_id'), 'inspections', ['created_by_user_id'], unique=False)
    op.create_foreign_key(
        'fk_inspections_created_by_user_id_users',
        'inspections',
        'users',
        ['created_by_user_id'],
        ['user_id'],
        ondelete='SET NULL'
    )

def downgrade() -> None:
    # 1. Drop foreign key and column from inspections table
    op.drop_constraint('fk_inspections_created_by_user_id_users', 'inspections', type_='foreignkey')
    op.drop_index(op.f('ix_inspections_created_by_user_id'), table_name='inspections')
    op.drop_column('inspections', 'created_by_user_id')

    # 2. Drop users table
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_table('users')
