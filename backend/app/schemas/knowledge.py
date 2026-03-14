from __future__ import annotations

import uuid
from pydantic import BaseModel
from app.models.knowledge import KnowledgeDocType


class KnowledgeDocCreate(BaseModel):
    type: KnowledgeDocType
    title: str
    content: str


class KnowledgeDocUpdate(BaseModel):
    type: KnowledgeDocType | None = None
    title: str | None = None
    content: str | None = None


class KnowledgeDocOut(KnowledgeDocCreate):
    id: uuid.UUID

    class Config:
        from_attributes = True
