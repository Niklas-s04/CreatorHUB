from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.content import (
    ChecklistPhase,
    ContentPlatform,
    ContentStatus,
    ContentType,
    EditorialStatus,
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
    platform_meta_json: dict[str, Any] = Field(default_factory=dict)
    planned_date: date | None = None
    publish_date: date | None = None
    external_url: str | None = None
    workflow_status: WorkflowStatus = WorkflowStatus.draft
    review_reason: str | None = None
    editorial_status: EditorialStatus = EditorialStatus.backlog
    editorial_owner_id: uuid.UUID | None = None
    editorial_owner_name: str | None = None
    primary_asset_id: uuid.UUID | None = None
    last_change_summary: str | None = None


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
    platform_meta_json: dict[str, Any] | None = None
    planned_date: date | None = None
    publish_date: date | None = None
    external_url: str | None = None
    workflow_status: WorkflowStatus | None = None
    review_reason: str | None = None
    editorial_status: EditorialStatus | None = None
    editorial_owner_id: uuid.UUID | None = None
    editorial_owner_name: str | None = None
    primary_asset_id: uuid.UUID | None = None
    last_change_summary: str | None = None


class ContentItemRevisionOut(BaseModel):
    id: uuid.UUID
    revision_number: int
    changed_fields: list[str]
    before_json: dict[str, str | int | bool | None]
    after_json: dict[str, str | int | bool | None]
    workflow_status: WorkflowStatus
    editorial_status: EditorialStatus
    content_status: ContentStatus
    review_reason: str | None
    change_summary: str | None
    changed_by_id: uuid.UUID | None
    changed_by_name: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class ContentItemOut(ContentItemCreate):
    id: uuid.UUID
    reviewed_by_id: uuid.UUID | None
    reviewed_by_name: str | None
    reviewed_at: datetime | None
    published_at: datetime | None
    published_by_id: uuid.UUID | None
    published_by_name: str | None
    review_cycle: int
    applied_template_snapshot_id: uuid.UUID | None = None
    readiness_score: int = 0
    asset_count: int = 0
    approved_asset_count: int = 0
    pending_asset_count: int = 0
    revisions: list[ContentItemRevisionOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ContentTaskCreate(BaseModel):
    content_item_id: uuid.UUID
    type: TaskType = TaskType.record
    title: str | None = None
    status: TaskStatus = TaskStatus.todo
    priority: TaskPriority = TaskPriority.medium
    assignee_user_id: uuid.UUID | None = None
    assignee_role: UserRole | None = None
    due_date: date | None = None
    blocked_by_task_id: uuid.UUID | None = None
    required_for_publish: bool = False
    can_block_publish: bool = False
    checklist_snapshot_id: uuid.UUID | None = None
    notes: str | None = None


class ContentTaskUpdate(BaseModel):
    type: TaskType | None = None
    title: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assignee_user_id: uuid.UUID | None = None
    assignee_role: UserRole | None = None
    due_date: date | None = None
    blocked_by_task_id: uuid.UUID | None = None
    required_for_publish: bool | None = None
    can_block_publish: bool | None = None
    checklist_snapshot_id: uuid.UUID | None = None
    notes: str | None = None


class ContentTaskOut(ContentTaskCreate):
    id: uuid.UUID
    notified_at: datetime | None = None
    escalated_at: datetime | None = None
    completed_at: datetime | None = None
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


class ContentPlatformProfileCreate(BaseModel):
    platform: ContentPlatform
    name: str
    schema_json: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    is_system: bool = False


class ContentPlatformProfileUpdate(BaseModel):
    name: str | None = None
    schema_json: dict[str, Any] | None = None
    is_active: bool | None = None


class ContentPlatformProfileOut(BaseModel):
    id: uuid.UUID
    platform: ContentPlatform
    name: str
    schema_json: dict[str, Any]
    is_active: bool
    is_system: bool
    owner_user_id: uuid.UUID | None
    version: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ContentChecklistTemplateItemCreate(BaseModel):
    title: str
    phase: ChecklistPhase = ChecklistPhase.production
    required: bool = True
    priority_default: TaskPriority = TaskPriority.medium
    due_offset_days: int | None = None
    can_block_publish: bool = False
    sort_order: int = 0


class ContentChecklistTemplateItemOut(ContentChecklistTemplateItemCreate):
    id: uuid.UUID
    template_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ContentChecklistTemplateCreate(BaseModel):
    name: str
    description: str | None = None
    applies_to_platform: ContentPlatform | None = None
    applies_to_type: ContentType | None = None
    is_shared: bool = False
    is_system: bool = False
    items: list[ContentChecklistTemplateItemCreate] = Field(default_factory=list)


class ContentChecklistTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    applies_to_platform: ContentPlatform | None = None
    applies_to_type: ContentType | None = None
    is_shared: bool | None = None
    items: list[ContentChecklistTemplateItemCreate] | None = None


class ContentChecklistTemplateOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    applies_to_platform: ContentPlatform | None
    applies_to_type: ContentType | None
    is_shared: bool
    is_system: bool
    owner_user_id: uuid.UUID | None
    version: int
    items: list[ContentChecklistTemplateItemOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ContentTemplateApplyRequest(BaseModel):
    template_id: uuid.UUID
    merge_mode: str = "replace"
    keep_done_tasks: bool = False


class ContentTemplateApplyResult(BaseModel):
    item: ContentItemOut
    created_tasks_count: int
    warnings: list[str] = Field(default_factory=list)


class ContentPlanningViewOut(BaseModel):
    item: ContentItemOut
    tasks: list[ContentTaskOut]
    open_task_count: int
    required_open_count: int
    readiness_score: int
    publish_ready: bool
    blockers: list[str] = Field(default_factory=list)
