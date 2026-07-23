from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.content import ContentPlatform, ContentStatus, ContentType
from app.models.product import ProductStatus
from app.models.project import PreviewStatus, ProjectPriority, ProjectStatus


class ProjectCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    color: str = Field(default="#5aa0ff", pattern=r"^#[0-9a-fA-F]{6}$")
    description: str | None = None
    is_active: bool = True


class ProjectCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    description: str | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def required_patch_fields_must_not_be_null(self) -> "ProjectCategoryUpdate":
        for field in ("name", "color", "is_active"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} must not be null")
        return self


class ProjectCategoryOut(ProjectCategoryCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ProjectBase(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    category_id: uuid.UUID | None = None
    status: ProjectStatus = ProjectStatus.idea
    priority: ProjectPriority = ProjectPriority.medium
    owner_user_id: uuid.UUID | None = None
    owner_name: str | None = Field(default=None, max_length=128)
    goal: str | None = None
    brief_md: str | None = None
    requirements_md: str | None = None
    notes_md: str | None = None
    start_date: date | None = None
    due_date: date | None = None
    publish_date: date | None = None
    progress_percent: int = Field(default=0, ge=0, le=100)
    preview_required: bool = False
    preview_status: PreviewStatus = PreviewStatus.not_required
    preview_due_date: date | None = None
    preview_notes: str | None = None

    @model_validator(mode="after")
    def validate_project_dates_and_preview(self) -> "ProjectBase":
        if self.start_date and self.due_date and self.due_date < self.start_date:
            raise ValueError("Due date must not be before start date")
        if self.preview_required and self.preview_status == PreviewStatus.not_required:
            self.preview_status = PreviewStatus.pending
        if not self.preview_required:
            self.preview_status = PreviewStatus.not_required
            self.preview_due_date = None
        return self


class ProjectCreate(ProjectBase):
    content_item_ids: list[uuid.UUID] = Field(default_factory=list)
    product_ids: list[uuid.UUID] = Field(default_factory=list)


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=256)
    category_id: uuid.UUID | None = None
    status: ProjectStatus | None = None
    priority: ProjectPriority | None = None
    owner_user_id: uuid.UUID | None = None
    owner_name: str | None = Field(default=None, max_length=128)
    goal: str | None = None
    brief_md: str | None = None
    requirements_md: str | None = None
    notes_md: str | None = None
    start_date: date | None = None
    due_date: date | None = None
    publish_date: date | None = None
    progress_percent: int | None = Field(default=None, ge=0, le=100)
    preview_required: bool | None = None
    preview_status: PreviewStatus | None = None
    preview_due_date: date | None = None
    preview_notes: str | None = None

    @model_validator(mode="after")
    def required_patch_fields_must_not_be_null(self) -> "ProjectUpdate":
        for field in ("title", "status", "priority", "progress_percent", "preview_required"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} must not be null")
        return self


class ProjectContentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None
    platform: ContentPlatform
    type: ContentType
    status: ContentStatus
    planned_date: date | None
    publish_date: date | None
    readiness_score: int


class ProjectProductSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    brand: str | None
    model: str | None
    category: str | None
    status: ProductStatus


class ProjectOut(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: ProjectCategoryOut | None
    content_count: int
    product_count: int
    overdue: bool
    preview_attention_required: bool
    created_at: datetime
    updated_at: datetime


class ProjectDetailOut(ProjectOut):
    content_items: list[ProjectContentSummary]
    products: list[ProjectProductSummary]
