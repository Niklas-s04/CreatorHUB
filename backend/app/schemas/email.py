from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.email import EmailIntent, EmailThreadMessageRole, EmailTone
from app.schemas.deal import DealDraftOut


class EmailDraftRequest(BaseModel):
    subject: str | None = None
    raw_body: str
    tone: EmailTone = EmailTone.neutral
    thread_id: uuid.UUID | None = None


class EmailRefineRequest(BaseModel):
    """Refine an existing draft by providing answers / extra notes."""

    thread_id: uuid.UUID
    draft_id: uuid.UUID
    tone: EmailTone = EmailTone.neutral
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
    tone: EmailTone
    draft_subject: str | None
    draft_body: str
    questions_to_ask: str | None
    risk_flags: str | None
    risk_score: int
    risk_checked_at: datetime | None
    approval_reason: str | None
    approved_by_id: uuid.UUID | None
    approved_by_name: str | None
    approved_at: datetime | None
    approved: bool
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


class EmailThreadDetailOut(EmailThreadOut):
    drafts: list[EmailDraftOut]
    messages: list[EmailThreadMessageOut]
    deal_draft: DealDraftOut | None
