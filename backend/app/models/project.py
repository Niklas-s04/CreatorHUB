from __future__ import annotations

import enum
import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.content import ContentItem
    from app.models.product import Product

project_content_links = Table(
    "project_content_links",
    Base.metadata,
    Column(
        "project_id",
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "content_item_id",
        ForeignKey("content_items.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
)


project_product_links = Table(
    "project_product_links",
    Base.metadata,
    Column(
        "project_id",
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "product_id",
        ForeignKey("products.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
)


class ProjectStatus(str, enum.Enum):
    idea = "idea"
    planning = "planning"
    active = "active"
    on_hold = "on_hold"
    completed = "completed"
    archived = "archived"


class ProjectPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class PreviewStatus(str, enum.Enum):
    not_required = "not_required"
    pending = "pending"
    requested = "requested"
    changes_requested = "changes_requested"
    approved = "approved"


class ProjectCategory(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "project_categories"

    name: Mapped[str] = mapped_column(String(120))
    __table_args__ = (
        Index(
            "ix_project_categories_name_ci",
            func.lower(name),
            unique=True,
        ),
    )

    color: Mapped[str] = mapped_column(String(16), default="#5aa0ff")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    projects: Mapped[list["Project"]] = relationship(back_populates="category")


class Project(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "projects"

    title: Mapped[str] = mapped_column(String(256), index=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("project_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus), default=ProjectStatus.idea, index=True
    )
    priority: Mapped[ProjectPriority] = mapped_column(
        Enum(ProjectPriority), default=ProjectPriority.medium, index=True
    )
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    owner_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    brief_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirements_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes_md: Mapped[str | None] = mapped_column(Text, nullable=True)

    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    publish_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)

    preview_required: Mapped[bool] = mapped_column(Boolean, default=False)
    preview_status: Mapped[PreviewStatus] = mapped_column(
        Enum(PreviewStatus), default=PreviewStatus.not_required
    )
    preview_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    preview_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    category: Mapped[ProjectCategory | None] = relationship(back_populates="projects")
    content_items: Mapped[list["ContentItem"]] = relationship(  # noqa: F821
        secondary=project_content_links,
        back_populates="projects",
    )
    products: Mapped[list["Product"]] = relationship(  # noqa: F821
        secondary=project_product_links,
        back_populates="projects",
    )
