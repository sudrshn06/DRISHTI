from datetime import date
from typing import Optional
from sqlalchemy import String, Text, Date
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base

class RegulatoryKnowledgeChunkModel(Base):
    """
    SQLAlchemy model storing parsed regulatory Gazette and provisions chunks.
    """
    __tablename__ = "regulatory_knowledge_chunks"

    chunk_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    regulatory_domain: Mapped[str] = mapped_column(String(50), nullable=False) # "LEGAL_METROLOGY" or "FOOD_LABEL_FSSAI"
    provision_number: Mapped[str] = mapped_column(String(50), nullable=False)
    notification_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    official_source: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
