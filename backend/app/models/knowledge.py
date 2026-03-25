from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.workflow import WorkflowStatus


class KnowledgeDocType(str, enum.Enum):
    brand_voice = "brand_voice"
    policy = "policy"
    template = "template"
    rate_card = "rate_card"


class KnowledgeDoc(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "knowledge_docs"

    type: Mapped[KnowledgeDocType] = mapped_column(Enum(KnowledgeDocType), index=True)
    title: Mapped[str] = mapped_column(String(256))
    content: Mapped[str] = mapped_column(Text)
    workflow_status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus), default=WorkflowStatus.draft
    )
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )
    reviewed_by_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Embeddings (pgvector) sind im MVP bewusst nicht enthalten.
