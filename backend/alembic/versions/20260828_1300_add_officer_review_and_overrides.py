"""add durable officer package review and declaration overrides

Revision ID: 20260828_stage15
Revises: 20260828_gemini1
Create Date: 2026-08-28 13:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260828_stage15"
down_revision: Union[str, None] = "20260828_gemini1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("inspections", sa.Column("package_information_review", sa.JSON(), nullable=True))
    op.add_column(
        "inspections",
        sa.Column("officer_declaration_overrides", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )


def downgrade() -> None:
    op.drop_column("inspections", "officer_declaration_overrides")
    op.drop_column("inspections", "package_information_review")

