from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.models.deal import DealDraftStatus


class DealDraftBase(BaseModel):
    brand_name: str | None = None
    contact_name: str | None = None
    contact_email: EmailStr | None = None
    budget: str | None = None
    deliverables: str | None = None
    usage_rights: str | None = None
    deadlines: str | None = None
    notes: str | None = None
    status: DealDraftStatus = DealDraftStatus.intake


class DealDraftOut(DealDraftBase):
    id: uuid.UUID
    thread_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DealDraftIntakeRequest(BaseModel):
    thread_id: uuid.UUID
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


class DealDraftUpdate(BaseModel):
    brand_name: str | None = None
    contact_name: str | None = None
    contact_email: EmailStr | None = None
    budget: str | None = None
    deliverables: str | None = None
    usage_rights: str | None = None
    deadlines: str | None = None
    notes: str | None = None
    status: DealDraftStatus | None = None
