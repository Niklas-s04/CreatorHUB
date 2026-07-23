"""add project planning hub

Revision ID: 0026
Revises: 0025
Create Date: 2026-07-23

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None

project_status = sa.Enum(
    "idea", "planning", "active", "on_hold", "completed", "archived", name="projectstatus"
)
project_priority = sa.Enum("low", "medium", "high", "critical", name="projectpriority")
preview_status = sa.Enum(
    "not_required",
    "pending",
    "requested",
    "changes_requested",
    "approved",
    name="previewstatus",
)


def upgrade() -> None:
    op.create_table(
        "project_categories",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("color", sa.String(length=16), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_project_categories_name"), "project_categories", ["name"], unique=True)
    op.create_table(
        "projects",
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("status", project_status, nullable=False),
        sa.Column("priority", project_priority, nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("owner_name", sa.String(length=128), nullable=True),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column("brief_md", sa.Text(), nullable=True),
        sa.Column("requirements_md", sa.Text(), nullable=True),
        sa.Column("notes_md", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("publish_date", sa.Date(), nullable=True),
        sa.Column("progress_percent", sa.Integer(), nullable=False),
        sa.Column("preview_required", sa.Boolean(), nullable=False),
        sa.Column("preview_status", preview_status, nullable=False),
        sa.Column("preview_due_date", sa.Date(), nullable=True),
        sa.Column("preview_notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["project_categories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "category_id",
        "due_date",
        "owner_user_id",
        "priority",
        "publish_date",
        "status",
        "title",
    ):
        op.create_index(op.f(f"ix_projects_{column}"), "projects", [column], unique=False)
    op.create_table(
        "project_content_links",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("content_item_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id", "content_item_id"),
    )
    op.create_table(
        "project_product_links",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id", "product_id"),
    )


def downgrade() -> None:
    op.drop_table("project_product_links")
    op.drop_table("project_content_links")
    for column in (
        "title",
        "status",
        "publish_date",
        "priority",
        "owner_user_id",
        "due_date",
        "category_id",
    ):
        op.drop_index(op.f(f"ix_projects_{column}"), table_name="projects")
    op.drop_table("projects")
    op.drop_index(op.f("ix_project_categories_name"), table_name="project_categories")
    op.drop_table("project_categories")
    preview_status.drop(op.get_bind(), checkfirst=True)
    project_priority.drop(op.get_bind(), checkfirst=True)
    project_status.drop(op.get_bind(), checkfirst=True)
