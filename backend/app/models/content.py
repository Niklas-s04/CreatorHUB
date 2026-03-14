from __future__ import annotations

import enum
import uuid
from datetime import date

from sqlalchemy import String, Text, Enum, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


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


class ContentItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "content_items"

    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True)

    platform: Mapped[ContentPlatform] = mapped_column(Enum(ContentPlatform), default=ContentPlatform.youtube)
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

    tasks: Mapped[list["ContentTask"]] = relationship(back_populates="content_item", cascade="all, delete-orphan")


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


class ContentTask(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "content_tasks"

    content_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"), index=True)

    type: Mapped[TaskType] = mapped_column(Enum(TaskType), default=TaskType.record)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.todo)

    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    content_item: Mapped["ContentItem"] = relationship(back_populates="tasks")
