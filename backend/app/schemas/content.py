from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.content import (
    ContentPlatform,
    ContentStatus,
    ContentType,
    TaskPriority,
    TaskStatus,
    TaskType,
)
from app.models.user import UserRole
from app.models.workflow import WorkflowStatus


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
    workflow_status: WorkflowStatus = WorkflowStatus.draft
    review_reason: str | None = None


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
    workflow_status: WorkflowStatus | None = None
    review_reason: str | None = None


class ContentItemOut(ContentItemCreate):
    id: uuid.UUID
    reviewed_by_id: uuid.UUID | None
    reviewed_by_name: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ContentTaskCreate(BaseModel):
    content_item_id: uuid.UUID
    type: TaskType = TaskType.record
    status: TaskStatus = TaskStatus.todo
    priority: TaskPriority = TaskPriority.medium
    assignee_user_id: uuid.UUID | None = None
    assignee_role: UserRole | None = None
    due_date: date | None = None
    notes: str | None = None


class ContentTaskUpdate(BaseModel):
    type: TaskType | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assignee_user_id: uuid.UUID | None = None
    assignee_role: UserRole | None = None
    due_date: date | None = None
    notes: str | None = None


class ContentTaskOut(ContentTaskCreate):
    id: uuid.UUID
    notified_at: datetime | None = None
    escalated_at: datetime | None = None
    is_overdue: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ContentTaskViewCreate(BaseModel):
    name: str
    is_shared: bool = False
    filters: dict[str, str | bool | int | None] = Field(default_factory=dict)


class ContentTaskViewOut(ContentTaskViewCreate):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ContentTaskFilterParams(BaseModel):
    content_item_id: uuid.UUID | None = None
    assignee_user_id: uuid.UUID | None = None
    assignee_role: UserRole | None = None
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    overdue_only: bool = False

    class Config:
        from_attributes = True
