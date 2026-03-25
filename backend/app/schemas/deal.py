from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.models.deal import DealDraftStatus
from app.models.workflow import WorkflowStatus


class DealDraftBase(BaseModel):
    product_id: uuid.UUID | None = None
    brand_name: str | None = None
    contact_name: str | None = None
    contact_email: EmailStr | None = None
    budget: str | None = None
    deliverables: str | None = None
    usage_rights: str | None = None
    deadlines: str | None = None
    notes: str | None = None
    status: DealDraftStatus = DealDraftStatus.intake
    checklist: list[dict[str, str | bool]] | None = None
    workflow_status: WorkflowStatus = WorkflowStatus.draft
    review_reason: str | None = None


class DealDraftOut(DealDraftBase):
    id: uuid.UUID
    thread_id: uuid.UUID | None
    reviewed_by_id: uuid.UUID | None
    reviewed_by_name: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DealDraftIntakeRequest(BaseModel):
    thread_id: uuid.UUID
    product_id: uuid.UUID | None = None
    auto_extract: bool = True
    brand_name: str | None = None
    contact_name: str | None = None
    contact_email: EmailStr | None = None
    budget: str | None = None
    deliverables: str | None = None
    usage_rights: str | None = None
    deadlines: str | None = None
    notes: str | None = None
    status: DealDraftStatus | None = None
    checklist: list[dict[str, str | bool]] | None = None
    workflow_status: WorkflowStatus | None = None
    review_reason: str | None = None


class DealDraftUpdate(BaseModel):
    product_id: uuid.UUID | None = None
    brand_name: str | None = None
    contact_name: str | None = None
    contact_email: EmailStr | None = None
    budget: str | None = None
    deliverables: str | None = None
    usage_rights: str | None = None
    deadlines: str | None = None
    notes: str | None = None
    status: DealDraftStatus | None = None
    checklist: list[dict[str, str | bool]] | None = None
    workflow_status: WorkflowStatus | None = None
    review_reason: str | None = None
