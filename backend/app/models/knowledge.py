from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.workflow import WorkflowStatus


class KnowledgeDocType(str, enum.Enum):
    brand_voice = "brand_voice"
    policy = "policy"
    template = "template"
    rate_card = "rate_card"


class KnowledgeSourceType(str, enum.Enum):
    internal = "internal"
    external = "external"
    customer = "customer"
    legal = "legal"
    other = "other"


class KnowledgeSourceReviewStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    needs_update = "needs_update"


class KnowledgeTrustLevel(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    verified = "verified"


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
    source_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[KnowledgeSourceType] = mapped_column(
        Enum(KnowledgeSourceType), default=KnowledgeSourceType.internal
    )
    source_review_status: Mapped[KnowledgeSourceReviewStatus] = mapped_column(
        Enum(KnowledgeSourceReviewStatus), default=KnowledgeSourceReviewStatus.pending
    )
    source_review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    origin_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    trust_level: Mapped[KnowledgeTrustLevel] = mapped_column(
        Enum(KnowledgeTrustLevel), default=KnowledgeTrustLevel.medium
    )
    is_outdated: Mapped[bool] = mapped_column(Boolean, default=False)
    outdated_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    outdated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_version: Mapped[int] = mapped_column(Integer, default=1)

    versions: Mapped[list["KnowledgeDocVersion"]] = relationship(
        back_populates="knowledge_doc", cascade="all, delete-orphan"
    )
    draft_links: Mapped[list["KnowledgeDocDraftLink"]] = relationship(
        back_populates="knowledge_doc", cascade="all, delete-orphan"
    )


class KnowledgeDocVersion(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "knowledge_doc_versions"

    knowledge_doc_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_docs.id", ondelete="CASCADE"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer)
    type: Mapped[KnowledgeDocType] = mapped_column(Enum(KnowledgeDocType), index=True)
    title: Mapped[str] = mapped_column(String(256))
    content: Mapped[str] = mapped_column(Text)
    workflow_status: Mapped[WorkflowStatus] = mapped_column(Enum(WorkflowStatus))
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[KnowledgeSourceType] = mapped_column(Enum(KnowledgeSourceType))
    source_review_status: Mapped[KnowledgeSourceReviewStatus] = mapped_column(
        Enum(KnowledgeSourceReviewStatus)
    )
    source_review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    origin_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    trust_level: Mapped[KnowledgeTrustLevel] = mapped_column(Enum(KnowledgeTrustLevel))
    is_outdated: Mapped[bool] = mapped_column(Boolean, default=False)
    outdated_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    outdated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    changed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )
    changed_by_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    change_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    knowledge_doc: Mapped[KnowledgeDoc] = relationship(back_populates="versions")


class KnowledgeDocDraftLink(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "knowledge_doc_draft_links"

    knowledge_doc_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_docs.id", ondelete="CASCADE"), index=True
    )
    email_draft_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("email_drafts.id", ondelete="CASCADE"), index=True
    )
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    linked_by_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    knowledge_doc: Mapped[KnowledgeDoc] = relationship(back_populates="draft_links")
    # Embeddings (pgvector) sind im MVP bewusst nicht enthalten.
