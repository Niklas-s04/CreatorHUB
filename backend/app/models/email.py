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
    templates: Mapped[list["EmailTemplate"]] = relationship(
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


class EmailRiskLevel(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class EmailApprovalStatus(str, enum.Enum):
    not_required = "not_required"
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class EmailHandoffStatus(str, enum.Enum):
    draft = "draft"
    blocked = "blocked"
    ready_for_send = "ready_for_send"
    handed_off = "handed_off"


class EmailDraftSource(str, enum.Enum):
    ai_generate = "ai_generate"
    ai_refine = "ai_refine"
    template = "template"
    manual = "manual"


class EmailDraft(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "email_drafts"

    thread_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("email_threads.id", ondelete="CASCADE"), index=True
    )
    parent_draft_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("email_drafts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("email_templates.id", ondelete="SET NULL"), nullable=True, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    source: Mapped[EmailDraftSource] = mapped_column(
        Enum(EmailDraftSource), default=EmailDraftSource.ai_generate
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
    risk_level: Mapped[EmailRiskLevel] = mapped_column(
        Enum(EmailRiskLevel), default=EmailRiskLevel.low
    )
    risk_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=False)
    approval_status: Mapped[EmailApprovalStatus] = mapped_column(
        Enum(EmailApprovalStatus), default=EmailApprovalStatus.not_required
    )
    risk_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )
    approved_by_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    handoff_status: Mapped[EmailHandoffStatus] = mapped_column(
        Enum(EmailHandoffStatus), default=EmailHandoffStatus.draft
    )
    handoff_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    handed_off_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )
    handed_off_by_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    handed_off_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    thread: Mapped["EmailThread"] = relationship(back_populates="drafts")
    template: Mapped["EmailTemplate | None"] = relationship(back_populates="drafts")
    parent_draft: Mapped["EmailDraft | None"] = relationship(
        "EmailDraft",
        remote_side="EmailDraft.id",
        back_populates="child_drafts",
        foreign_keys=[parent_draft_id],
    )
    child_drafts: Mapped[list["EmailDraft"]] = relationship(
        "EmailDraft",
        back_populates="parent_draft",
        cascade="all",
        foreign_keys="EmailDraft.parent_draft_id",
    )
    versions: Mapped[list["EmailDraftVersion"]] = relationship(
        back_populates="draft", cascade="all, delete-orphan"
    )
    suggestions: Mapped[list["EmailDraftSuggestion"]] = relationship(
        back_populates="draft", cascade="all, delete-orphan"
    )


class EmailTemplate(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "email_templates"

    thread_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("email_threads.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    intent: Mapped[EmailIntent] = mapped_column(Enum(EmailIntent), default=EmailIntent.unknown)
    subject_template: Mapped[str | None] = mapped_column(String(256), nullable=True)
    body_template: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )
    created_by_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    thread: Mapped["EmailThread | None"] = relationship(back_populates="templates")
    drafts: Mapped[list["EmailDraft"]] = relationship(back_populates="template")


class EmailDraftVersion(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "email_draft_versions"

    draft_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("email_drafts.id", ondelete="CASCADE"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    draft_subject: Mapped[str | None] = mapped_column(String(256), nullable=True)
    draft_body: Mapped[str] = mapped_column(Text)
    tone: Mapped[EmailTone] = mapped_column(Enum(EmailTone), default=EmailTone.neutral)
    changed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )
    changed_by_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    draft: Mapped["EmailDraft"] = relationship(back_populates="versions")


class EmailDraftSuggestionType(str, enum.Enum):
    ai_draft = "ai_draft"
    ai_refine = "ai_refine"
    risk_assessment = "risk_assessment"
    template_applied = "template_applied"
    approval_decision = "approval_decision"
    handoff_decision = "handoff_decision"
    system_note = "system_note"


class EmailDraftSuggestion(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "email_draft_suggestions"

    draft_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("email_drafts.id", ondelete="CASCADE"), index=True
    )
    suggestion_type: Mapped[EmailDraftSuggestionType] = mapped_column(
        Enum(EmailDraftSuggestionType), default=EmailDraftSuggestionType.system_note
    )
    source: Mapped[str] = mapped_column(String(64), default="system")
    summary: Mapped[str | None] = mapped_column(String(256), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    decided: Mapped[bool] = mapped_column(Boolean, default=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )
    decided_by_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    draft: Mapped["EmailDraft"] = relationship(back_populates="suggestions")


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
