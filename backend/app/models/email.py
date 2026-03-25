from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.deal import DealDraft


class EmailIntent(str, enum.Enum):
    sponsoring = "sponsoring"
    support = "support"
    collab = "collab"
    shipping = "shipping"
    refund = "refund"
    unknown = "unknown"


class EmailThread(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "email_threads"

    subject: Mapped[str | None] = mapped_column(String(256), nullable=True)
    raw_body: Mapped[str] = mapped_column(Text)
    detected_intent: Mapped[EmailIntent] = mapped_column(
        Enum(EmailIntent), default=EmailIntent.unknown
    )

    drafts: Mapped[list["EmailDraft"]] = relationship(
        back_populates="thread", cascade="all, delete-orphan"
    )
    messages: Mapped[list["EmailThreadMessage"]] = relationship(
        back_populates="thread", cascade="all, delete-orphan"
    )
    deal_draft: Mapped["DealDraft | None"] = relationship(
        "DealDraft", back_populates="thread", uselist=False
    )


class EmailTone(str, enum.Enum):
    short = "short"
    neutral = "neutral"
    friendly = "friendly"
    firm = "firm"


class EmailDraft(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "email_drafts"

    thread_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("email_threads.id", ondelete="CASCADE"), index=True
    )
    tone: Mapped[EmailTone] = mapped_column(Enum(EmailTone), default=EmailTone.neutral)

    draft_subject: Mapped[str | None] = mapped_column(String(256), nullable=True)
    draft_body: Mapped[str] = mapped_column(Text)

    questions_to_ask: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Als JSON-String gespeichert.
    risk_flags: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Als JSON-String gespeichert.
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    risk_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )
    approved_by_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)

    thread: Mapped["EmailThread"] = relationship(back_populates="drafts")


class EmailThreadMessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"
    system = "system"


class EmailThreadMessage(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "email_thread_messages"

    thread_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("email_threads.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[EmailThreadMessageRole] = mapped_column(
        Enum(EmailThreadMessageRole), default=EmailThreadMessageRole.user
    )
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    thread: Mapped["EmailThread"] = relationship(back_populates="messages")
