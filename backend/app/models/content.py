from __future__ import annotations

import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.user import UserRole
from app.models.workflow import WorkflowStatus


class ContentPlatform(str, enum.Enum):
    youtube = "youtube"
    shorts = "shorts"
    instagram = "instagram"
    tiktok = "tiktok"
    x = "x"
    linkedin = "linkedin"


class ContentType(str, enum.Enum):
    review = "review"
    short = "short"
    post = "post"
    story = "story"


class ContentStatus(str, enum.Enum):
    idea = "idea"
    draft = "draft"
    recorded = "recorded"
    edited = "edited"
    scheduled = "scheduled"
    published = "published"


class EditorialStatus(str, enum.Enum):
    backlog = "backlog"
    drafting = "drafting"
    in_review = "in_review"
    changes_requested = "changes_requested"
    approved = "approved"
    ready_to_publish = "ready_to_publish"
    published = "published"


class ContentItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "content_items"

    product_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True
    )

    platform: Mapped[ContentPlatform] = mapped_column(
        Enum(ContentPlatform), default=ContentPlatform.youtube
    )
    type: Mapped[ContentType] = mapped_column(Enum(ContentType), default=ContentType.review)
    status: Mapped[ContentStatus] = mapped_column(Enum(ContentStatus), default=ContentStatus.idea)

    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    hook: Mapped[str | None] = mapped_column(String(256), nullable=True)
    script_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags_csv: Mapped[str | None] = mapped_column(Text, nullable=True)

    planned_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    publish_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    external_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    workflow_status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus), default=WorkflowStatus.draft
    )
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )
    reviewed_by_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    editorial_status: Mapped[EditorialStatus] = mapped_column(
        Enum(EditorialStatus), default=EditorialStatus.backlog
    )
    editorial_owner_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )
    editorial_owner_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    primary_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )
    published_by_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    review_cycle: Mapped[int] = mapped_column(Integer, default=0)
    last_change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    tasks: Mapped[list["ContentTask"]] = relationship(
        back_populates="content_item", cascade="all, delete-orphan"
    )
    revisions: Mapped[list["ContentItemRevision"]] = relationship(
        back_populates="content_item", cascade="all, delete-orphan"
    )


class TaskType(str, enum.Enum):
    script = "script"
    record = "record"
    edit = "edit"
    thumbnail = "thumbnail"
    upload = "upload"
    seo = "seo"
    crosspost = "crosspost"
    design = "design"
    publish = "publish"


class TaskStatus(str, enum.Enum):
    todo = "todo"
    doing = "doing"
    done = "done"


class TaskPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ContentTask(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "content_tasks"

    content_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_items.id", ondelete="CASCADE"), index=True
    )

    type: Mapped[TaskType] = mapped_column(Enum(TaskType), default=TaskType.record)
    title: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.todo)
    priority: Mapped[TaskPriority] = mapped_column(Enum(TaskPriority), default=TaskPriority.medium)
    assignee_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )
    assignee_role: Mapped[UserRole | None] = mapped_column(Enum(UserRole), nullable=True)

    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    blocked_by_task_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    content_item: Mapped["ContentItem"] = relationship(back_populates="tasks")

    @property
    def is_overdue(self) -> bool:
        if self.status == TaskStatus.done or self.due_date is None:
            return False
        return self.due_date < datetime.now(timezone.utc).date()


class ContentTaskView(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "content_task_views"

    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    name: Mapped[str] = mapped_column(String(120))
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False)
    filters: Mapped[dict[str, str | bool | int | None]] = mapped_column(JSON, default=dict)


class ContentItemRevision(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "content_item_revisions"

    content_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_items.id", ondelete="CASCADE"), index=True
    )
    revision_number: Mapped[int] = mapped_column(Integer)
    changed_fields: Mapped[list[str]] = mapped_column(JSON, default=list)
    before_json: Mapped[dict[str, str | int | bool | None]] = mapped_column(JSON, default=dict)
    after_json: Mapped[dict[str, str | int | bool | None]] = mapped_column(JSON, default=dict)
    workflow_status: Mapped[WorkflowStatus] = mapped_column(Enum(WorkflowStatus))
    editorial_status: Mapped[EditorialStatus] = mapped_column(Enum(EditorialStatus))
    content_status: Mapped[ContentStatus] = mapped_column(Enum(ContentStatus))
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )
    changed_by_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    content_item: Mapped[ContentItem] = relationship(back_populates="revisions")
