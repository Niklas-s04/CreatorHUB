from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.knowledge import (
    KnowledgeDocType,
    KnowledgeSourceReviewStatus,
    KnowledgeSourceType,
    KnowledgeTrustLevel,
)
from app.models.workflow import WorkflowStatus


class KnowledgeDocCreate(BaseModel):
    type: KnowledgeDocType
    title: str
    content: str
    workflow_status: WorkflowStatus = WorkflowStatus.draft
    review_reason: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    source_type: KnowledgeSourceType = KnowledgeSourceType.internal
    source_review_status: KnowledgeSourceReviewStatus = KnowledgeSourceReviewStatus.pending
    source_review_note: str | None = None
    origin_summary: str | None = None
    trust_level: KnowledgeTrustLevel = KnowledgeTrustLevel.medium
    is_outdated: bool = False
    outdated_reason: str | None = None


class KnowledgeDocUpdate(BaseModel):
    type: KnowledgeDocType | None = None
    title: str | None = None
    content: str | None = None
    workflow_status: WorkflowStatus | None = None
    review_reason: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    source_type: KnowledgeSourceType | None = None
    source_review_status: KnowledgeSourceReviewStatus | None = None
    source_review_note: str | None = None
    origin_summary: str | None = None
    trust_level: KnowledgeTrustLevel | None = None
    is_outdated: bool | None = None
    outdated_reason: str | None = None


class KnowledgeDocVersionOut(BaseModel):
    id: uuid.UUID
    version_number: int
    type: KnowledgeDocType
    title: str
    content: str
    workflow_status: WorkflowStatus
    review_reason: str | None
    source_name: str | None
    source_url: str | None
    source_type: KnowledgeSourceType
    source_review_status: KnowledgeSourceReviewStatus
    source_review_note: str | None
    origin_summary: str | None
    trust_level: KnowledgeTrustLevel
    is_outdated: bool
    outdated_reason: str | None
    outdated_at: datetime | None
    changed_by_id: uuid.UUID | None
    changed_by_name: str | None
    change_note: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class KnowledgeDocDraftLinkOut(BaseModel):
    id: uuid.UUID
    email_draft_id: uuid.UUID
    linked_at: datetime
    linked_by_name: str | None

    class Config:
        from_attributes = True


class KnowledgeDocOut(KnowledgeDocCreate):
    id: uuid.UUID
    current_version: int
    reviewed_by_id: uuid.UUID | None
    reviewed_by_name: str | None
    reviewed_at: datetime | None
    outdated_at: datetime | None
    created_at: datetime
    updated_at: datetime
    versions: list[KnowledgeDocVersionOut] = Field(default_factory=list)
    draft_links: list[KnowledgeDocDraftLinkOut] = Field(default_factory=list)

    class Config:
        from_attributes = True
