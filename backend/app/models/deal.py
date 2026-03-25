from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.email import EmailThread
from app.models.workflow import WorkflowStatus


class DealDraftStatus(str, enum.Enum):
    intake = "intake"
    review = "review"
    negotiating = "negotiating"
    won = "won"
    lost = "lost"


class DealDraft(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "deal_drafts"

    thread_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("email_threads.id", ondelete="SET NULL"), unique=True, nullable=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True
    )

    brand_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(128), nullable=True)

    budget: Mapped[str | None] = mapped_column(String(128), nullable=True)
    deliverables: Mapped[str | None] = mapped_column(Text, nullable=True)
    usage_rights: Mapped[str | None] = mapped_column(Text, nullable=True)
    deadlines: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[DealDraftStatus] = mapped_column(
        Enum(DealDraftStatus), default=DealDraftStatus.intake
    )
    checklist: Mapped[list[dict[str, str | bool]] | None] = mapped_column(JSON, nullable=True)
    workflow_status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus), default=WorkflowStatus.draft
    )
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )
    reviewed_by_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    thread: Mapped["EmailThread | None"] = relationship(back_populates="deal_draft")
