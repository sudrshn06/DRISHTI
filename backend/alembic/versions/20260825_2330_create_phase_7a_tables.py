"""create phase 7a persistence tables

Revision ID: 20260825_7a01
Revises: f156a4d52ffd
Create Date: 2026-08-25 23:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260825_7a01'
down_revision: Union[str, None] = 'f156a4d52ffd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Create inspections table
    op.create_table(
        'inspections',
        sa.Column('inspection_id', sa.String(length=36), nullable=False),
        sa.Column('reference_date', sa.String(length=10), nullable=False),
        sa.Column('product_category', sa.String(length=100), nullable=False),
        sa.Column('product_origin', sa.String(length=30), nullable=False, server_default='UNKNOWN'),
        sa.Column('regulatory_product_class', sa.String(length=30), nullable=False, server_default='UNKNOWN'),
        sa.Column('date_regulatory_regime', sa.String(length=30), nullable=False, server_default='UNKNOWN'),
        sa.Column('date_package_exemption', sa.String(length=50), nullable=False, server_default='UNKNOWN'),
        sa.Column('is_electronic', sa.String(length=30), nullable=False, server_default='UNKNOWN'),
        sa.Column('package_structure', sa.String(length=30), nullable=False, server_default='UNKNOWN'),
        sa.Column('alcohol_context', sa.String(length=30), nullable=False, server_default='UNKNOWN'),
        sa.Column('capture_plan_id', sa.String(length=50), nullable=False),
        sa.Column('capture_status', sa.String(length=50), nullable=False, server_default='INCOMPLETE_INSPECTION'),
        sa.Column('evidence_sufficiency', sa.String(length=50), nullable=False, server_default='INSUFFICIENT_FOR_ABSENCE_EVALUATION'),
        sa.Column('lifecycle_status', sa.String(length=30), nullable=False, server_default='IN_PROGRESS'),
        sa.Column('dismissed_clarifications', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('inspection_id')
    )

    # 2. Create captures table
    op.create_table(
        'captures',
        sa.Column('capture_id', sa.String(length=36), nullable=False),
        sa.Column('inspection_id', sa.String(length=36), nullable=False),
        sa.Column('view_id', sa.String(length=30), nullable=False),
        sa.Column('evidence_id', sa.String(length=36), nullable=True),
        sa.Column('image_sha256', sa.String(length=64), nullable=False),
        sa.Column('media_type', sa.String(length=30), nullable=False, server_default='image/jpeg'),
        sa.Column('image_width', sa.Integer(), nullable=True),
        sa.Column('image_height', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='ACCEPTED'),
        sa.Column('pipeline_status', sa.String(length=30), nullable=False, server_default='COMPLETED'),
        sa.Column('quality_assessment', sa.JSON(), nullable=True),
        sa.Column('visual_assessment', sa.JSON(), nullable=True),
        sa.Column('field_candidates', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['inspection_id'], ['inspections.inspection_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('capture_id')
    )
    op.create_index(op.f('ix_captures_inspection_id'), 'captures', ['inspection_id'], unique=False)
    op.create_index(op.f('ix_captures_image_sha256'), 'captures', ['image_sha256'], unique=False)

    # 3. Create report_snapshots table
    op.create_table(
        'report_snapshots',
        sa.Column('report_id', sa.String(length=36), nullable=False),
        sa.Column('inspection_id', sa.String(length=36), nullable=False),
        sa.Column('schema_version', sa.String(length=10), nullable=False, server_default='1.0'),
        sa.Column('generated_at', sa.String(length=50), nullable=False),
        sa.Column('overall_disposition', sa.String(length=64), nullable=False),
        sa.Column('disposition_reason', sa.Text(), nullable=False),
        sa.Column('summary_counts', sa.JSON(), nullable=False),
        sa.Column('snapshot_payload', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['inspection_id'], ['inspections.inspection_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('report_id')
    )
    op.create_index(op.f('ix_report_snapshots_inspection_id'), 'report_snapshots', ['inspection_id'], unique=False)
    op.create_index(op.f('ix_report_snapshots_overall_disposition'), 'report_snapshots', ['overall_disposition'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_report_snapshots_overall_disposition'), table_name='report_snapshots')
    op.drop_index(op.f('ix_report_snapshots_inspection_id'), table_name='report_snapshots')
    op.drop_table('report_snapshots')
    
    op.drop_index(op.f('ix_captures_image_sha256'), table_name='captures')
    op.drop_index(op.f('ix_captures_inspection_id'), table_name='captures')
    op.drop_table('captures')
    
    op.drop_table('inspections')
