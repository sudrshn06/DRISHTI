"""add Gemini Stage 1 capture analysis audit data

Revision ID: 20260828_gemini1
Revises: 7e1846d85f45
Create Date: 2026-08-28 09:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260828_gemini1"
down_revision: Union[str, None] = "7e1846d85f45"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("captures", sa.Column("ai_analysis", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("captures", "ai_analysis")
