from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import (
    String,
    Integer,
    Text,
    DateTime,
    ForeignKey,
    JSON,
    func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.user import UserModel

class InspectionModel(Base):
    """
    Durable PostgreSQL ORM model for DRISHTI inspection sessions.
    Maintains clean separation from domain Pydantic schemas.
    """
    __tablename__ = "inspections"

    inspection_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    reference_date: Mapped[str] = mapped_column(String(10), nullable=False)
    product_category: Mapped[str] = mapped_column(String(100), nullable=False)
    product_origin: Mapped[str] = mapped_column(String(30), nullable=False, default="UNKNOWN")
    regulatory_product_class: Mapped[str] = mapped_column(String(30), nullable=False, default="UNKNOWN")
    date_regulatory_regime: Mapped[str] = mapped_column(String(30), nullable=False, default="UNKNOWN")
    date_package_exemption: Mapped[str] = mapped_column(String(50), nullable=False, default="UNKNOWN")
    is_electronic: Mapped[str] = mapped_column(String(30), nullable=False, default="UNKNOWN")
    package_structure: Mapped[str] = mapped_column(String(30), nullable=False, default="UNKNOWN")
    alcohol_context: Mapped[str] = mapped_column(String(30), nullable=False, default="UNKNOWN")
    
    capture_plan_id: Mapped[str] = mapped_column(String(50), nullable=False)
    capture_status: Mapped[str] = mapped_column(String(50), nullable=False, default="INCOMPLETE_INSPECTION")
    evidence_sufficiency: Mapped[str] = mapped_column(String(50), nullable=False, default="INSUFFICIENT_FOR_ABSENCE_EVALUATION")
    lifecycle_status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT")
    
    created_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    dismissed_clarifications: Mapped[list] = mapped_column(JSON, default=list)
    package_information_review: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    officer_declaration_overrides: Mapped[list] = mapped_column(JSON, default=list)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    owner: Mapped[Optional["UserModel"]] = relationship(
        "UserModel",
        back_populates="inspections",
        foreign_keys=[created_by_user_id]
    )
    captures: Mapped[List["CaptureModel"]] = relationship(
        "CaptureModel",
        back_populates="inspection",
        cascade="all, delete-orphan",
        order_by="CaptureModel.created_at"
    )
    report_snapshots: Mapped[List["ReportSnapshotModel"]] = relationship(
        "ReportSnapshotModel",
        back_populates="inspection",
        cascade="all, delete-orphan",
        order_by="ReportSnapshotModel.created_at.desc()"
    )

class CaptureModel(Base):
    """
    Durable PostgreSQL ORM model for individual package surface captures.
    """
    __tablename__ = "captures"

    capture_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    inspection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("inspections.inspection_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    view_id: Mapped[str] = mapped_column(String(30), nullable=False)
    evidence_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    image_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    object_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    media_type: Mapped[str] = mapped_column(String(30), nullable=False, default="image/jpeg")
    image_width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    image_height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACCEPTED")
    pipeline_status: Mapped[str] = mapped_column(String(30), nullable=False, default="COMPLETED")
    
    quality_assessment: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    visual_assessment: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    field_candidates: Mapped[list] = mapped_column(JSON, default=list)
    ai_analysis: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    inspection: Mapped["InspectionModel"] = relationship("InspectionModel", back_populates="captures")

class ReportSnapshotModel(Base):
    """
    Durable PostgreSQL ORM model for immutable inspection report snapshots.
    Preserves complete historical report payloads independently of future rule/OCR updates.
    """
    __tablename__ = "report_snapshots"

    report_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    inspection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("inspections.inspection_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    schema_version: Mapped[str] = mapped_column(String(10), nullable=False, default="1.0")
    generated_at: Mapped[str] = mapped_column(String(50), nullable=False)
    overall_disposition: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    disposition_reason: Mapped[str] = mapped_column(Text, nullable=False)
    summary_counts: Mapped[dict] = mapped_column(JSON, nullable=False)
    snapshot_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    inspection: Mapped["InspectionModel"] = relationship("InspectionModel", back_populates="report_snapshots")
