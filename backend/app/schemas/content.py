from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel

from app.models.content import ContentPlatform, ContentStatus, ContentType, TaskStatus, TaskType


class ContentItemCreate(BaseModel):
    product_id: uuid.UUID | None = None
    platform: ContentPlatform = ContentPlatform.youtube
    type: ContentType = ContentType.review
    status: ContentStatus = ContentStatus.idea
    title: str | None = None
    hook: str | None = None
    script_md: str | None = None
    description_md: str | None = None
    tags_csv: str | None = None
    planned_date: date | None = None
    publish_date: date | None = None
    external_url: str | None = None


class ContentItemUpdate(BaseModel):
    product_id: uuid.UUID | None = None
    platform: ContentPlatform | None = None
    type: ContentType | None = None
    status: ContentStatus | None = None
    title: str | None = None
    hook: str | None = None
    script_md: str | None = None
    description_md: str | None = None
    tags_csv: str | None = None
    planned_date: date | None = None
    publish_date: date | None = None
    external_url: str | None = None


class ContentItemOut(ContentItemCreate):
    id: uuid.UUID

    class Config:
        from_attributes = True


class ContentTaskCreate(BaseModel):
    content_item_id: uuid.UUID
    type: TaskType = TaskType.record
    status: TaskStatus = TaskStatus.todo
    due_date: date | None = None
    notes: str | None = None


class ContentTaskUpdate(BaseModel):
    type: TaskType | None = None
    status: TaskStatus | None = None
    due_date: date | None = None
    notes: str | None = None


class ContentTaskOut(ContentTaskCreate):
    id: uuid.UUID

    class Config:
        from_attributes = True
