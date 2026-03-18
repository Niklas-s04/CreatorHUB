from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.email import EmailThread


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

    thread: Mapped["EmailThread | None"] = relationship("EmailThread", back_populates="deal_draft")
