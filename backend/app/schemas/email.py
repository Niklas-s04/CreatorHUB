from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.ai_settings import CreatorAiTone
from app.models.email import (
    EmailApprovalStatus,
    EmailDraftSource,
    EmailDraftSuggestionType,
    EmailHandoffStatus,
    EmailIntent,
    EmailRiskLevel,
    EmailThreadMessageRole,
    EmailTone,
)
from app.schemas.deal import DealDraftOut


class EmailDraftRequest(BaseModel):
    subject: str | None = None
    raw_body: str
    tone: EmailTone = EmailTone.neutral
    thread_id: uuid.UUID | None = None
    template_id: uuid.UUID | None = None
    creator_profile_id: uuid.UUID | None = None


class EmailRefineRequest(BaseModel):
    """Refine an existing draft by providing answers / extra notes."""

    thread_id: uuid.UUID
    draft_id: uuid.UUID
    tone: EmailTone = EmailTone.neutral
    template_id: uuid.UUID | None = None
    creator_profile_id: uuid.UUID | None = None
    # Liste aus Frage-Antwort-Paaren.
    qa: list[dict[str, str]] = []
    # Optionaler freier Zusatzhinweis.
    note: str | None = None


class EmailThreadOut(BaseModel):
    id: uuid.UUID
    subject: str | None
    raw_body: str
    detected_intent: EmailIntent
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EmailDraftOut(BaseModel):
    id: uuid.UUID
    thread_id: uuid.UUID
    parent_draft_id: uuid.UUID | None
    template_id: uuid.UUID | None
    version_number: int
    source: EmailDraftSource
    tone: EmailTone
    draft_subject: str | None
    draft_body: str
    questions_to_ask: str | None
    risk_flags: str | None
    risk_score: int
    risk_level: EmailRiskLevel
    risk_summary: str | None
    approval_required: bool
    approval_status: EmailApprovalStatus
    risk_checked_at: datetime | None
    approval_reason: str | None
    approved_by_id: uuid.UUID | None
    approved_by_name: str | None
    approved_at: datetime | None
    approved: bool
    handoff_status: EmailHandoffStatus
    handoff_note: str | None
    handed_off_by_id: uuid.UUID | None
    handed_off_by_name: str | None
    handed_off_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EmailThreadMessageOut(BaseModel):
    id: uuid.UUID
    thread_id: uuid.UUID
    role: EmailThreadMessageRole
    content: str | None
    payload: dict[str, Any] | None
    created_at: datetime

    class Config:
        from_attributes = True


class EmailDraftApprovalRequest(BaseModel):
    approved: bool
    reason: str | None = None


class EmailDraftManualUpdateRequest(BaseModel):
    draft_subject: str | None = None
    draft_body: str | None = None
    tone: EmailTone | None = None
    change_reason: str | None = None


class EmailDraftHandoffRequest(BaseModel):
    status: EmailHandoffStatus
    note: str | None = None


class EmailTemplateCreate(BaseModel):
    name: str
    intent: EmailIntent = EmailIntent.unknown
    subject_template: str | None = None
    body_template: str
    active: bool = True
    thread_id: uuid.UUID | None = None


class EmailTemplateUpdate(BaseModel):
    name: str | None = None
    intent: EmailIntent | None = None
    subject_template: str | None = None
    body_template: str | None = None
    active: bool | None = None


class EmailTemplateOut(BaseModel):
    id: uuid.UUID
    thread_id: uuid.UUID | None
    name: str
    intent: EmailIntent
    subject_template: str | None
    body_template: str
    active: bool
    created_by_id: uuid.UUID | None
    created_by_name: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EmailDraftVersionOut(BaseModel):
    id: uuid.UUID
    draft_id: uuid.UUID
    version_number: int
    draft_subject: str | None
    draft_body: str
    tone: EmailTone
    changed_by_id: uuid.UUID | None
    changed_by_name: str | None
    change_reason: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EmailDraftSuggestionOut(BaseModel):
    id: uuid.UUID
    draft_id: uuid.UUID
    suggestion_type: EmailDraftSuggestionType
    source: str
    summary: str | None
    payload: dict[str, Any] | None
    decided: bool
    decided_at: datetime | None
    decided_by_id: uuid.UUID | None
    decided_by_name: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EmailKnowledgeEvidenceOut(BaseModel):
    draft_id: uuid.UUID
    knowledge_doc_id: uuid.UUID
    knowledge_doc_title: str
    knowledge_doc_type: str
    linked_at: datetime
    linked_by_name: str | None


class EmailThreadDetailOut(EmailThreadOut):
    drafts: list[EmailDraftOut]
    messages: list[EmailThreadMessageOut]
    templates: list[EmailTemplateOut]
    draft_versions: list[EmailDraftVersionOut]
    draft_suggestions: list[EmailDraftSuggestionOut]
    knowledge_evidence: list[EmailKnowledgeEvidenceOut]
    deal_draft: DealDraftOut | None


class CreatorAiProfileInput(BaseModel):
    profile_name: str
    is_active: bool = True
    clear_name: str
    artist_name: str
    channel_link: str
    themes: list[str]
    platforms: list[str]
    short_description: str | None = None
    tone: CreatorAiTone = CreatorAiTone.neutral
    target_audience: str | None = None
    language_code: str = "de"
    content_focus: list[str] = Field(default_factory=list)


class CreatorAiProfileOut(BaseModel):
    id: uuid.UUID
    owner_user_id: uuid.UUID | None
    profile_name: str
    is_global_default: bool
    is_active: bool
    clear_name: str
    artist_name: str
    channel_link: str
    themes: list[str]
    platforms: list[str]
    short_description: str | None
    tone: CreatorAiTone
    target_audience: str | None
    language_code: str
    content_focus: list[str]
    created_by_id: uuid.UUID | None
    created_by_name: str | None
    updated_by_id: uuid.UUID | None
    updated_by_name: str | None
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CreatorAiSettingsPreviewOut(BaseModel):
    source: str
    profile_id: uuid.UUID | None
    profile_name: str | None
    missing_required: list[str]
    applied_settings: dict[str, Any]
