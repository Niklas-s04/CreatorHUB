from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.knowledge import KnowledgeDocType
from app.models.workflow import WorkflowStatus


class KnowledgeDocCreate(BaseModel):
    type: KnowledgeDocType
    title: str
    content: str
    workflow_status: WorkflowStatus = WorkflowStatus.draft
    review_reason: str | None = None


class KnowledgeDocUpdate(BaseModel):
    type: KnowledgeDocType | None = None
    title: str | None = None
    content: str | None = None
    workflow_status: WorkflowStatus | None = None
    review_reason: str | None = None


class KnowledgeDocOut(KnowledgeDocCreate):
    id: uuid.UUID
    reviewed_by_id: uuid.UUID | None
    reviewed_by_name: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
