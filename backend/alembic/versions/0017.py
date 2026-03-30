"""content editorial workflow hardening

Revision ID: 0017
Revises: 0016
Create Date: 2026-03-30

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


editorialstatus = sa.Enum(
    "backlog",
    "drafting",
    "in_review",
    "changes_requested",
    "approved",
    "ready_to_publish",
    "published",
    name="editorialstatus",
)


def upgrade() -> None:
    bind = op.get_bind()
    editorialstatus.create(bind, checkfirst=True)

    op.add_column(
        "content_items",
        sa.Column(
            "editorial_status",
            postgresql.ENUM(
                "backlog",
                "drafting",
                "in_review",
                "changes_requested",
                "approved",
                "ready_to_publish",
                "published",
                name="editorialstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="backlog",
        ),
    )
    op.add_column("content_items", sa.Column("editorial_owner_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("content_items", sa.Column("editorial_owner_name", sa.String(length=128), nullable=True))
    op.add_column("content_items", sa.Column("primary_asset_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("content_items", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("content_items", sa.Column("published_by_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("content_items", sa.Column("published_by_name", sa.String(length=128), nullable=True))
    op.add_column(
        "content_items",
        sa.Column("review_cycle", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("content_items", sa.Column("last_change_summary", sa.Text(), nullable=True))

    op.create_index("ix_content_items_editorial_owner_id", "content_items", ["editorial_owner_id"], unique=False)
    op.create_index("ix_content_items_primary_asset_id", "content_items", ["primary_asset_id"], unique=False)
    op.create_index("ix_content_items_published_by_id", "content_items", ["published_by_id"], unique=False)

    op.add_column("content_tasks", sa.Column("title", sa.String(length=160), nullable=True))
    op.add_column("content_tasks", sa.Column("blocked_by_task_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("content_tasks", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_content_tasks_blocked_by_task_id", "content_tasks", ["blocked_by_task_id"], unique=False)

    op.create_table(
        "content_item_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("changed_fields", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("before_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("after_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "workflow_status",
            postgresql.ENUM(
                "draft",
                "in_review",
                "approved",
                "rejected",
                "archived",
                name="workflowstatus",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "editorial_status",
            postgresql.ENUM(
                "backlog",
                "drafting",
                "in_review",
                "changes_requested",
                "approved",
                "ready_to_publish",
                "published",
                name="editorialstatus",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "content_status",
            postgresql.ENUM(
                "idea",
                "draft",
                "recorded",
                "edited",
                "scheduled",
                "published",
                name="contentstatus",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column("changed_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("changed_by_name", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_content_item_revisions_content_item_id", "content_item_revisions", ["content_item_id"], unique=False)
    op.create_index("ix_content_item_revisions_changed_by_id", "content_item_revisions", ["changed_by_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_content_item_revisions_changed_by_id", table_name="content_item_revisions")
    op.drop_index("ix_content_item_revisions_content_item_id", table_name="content_item_revisions")
    op.drop_table("content_item_revisions")

    op.drop_index("ix_content_tasks_blocked_by_task_id", table_name="content_tasks")
    op.drop_column("content_tasks", "completed_at")
    op.drop_column("content_tasks", "blocked_by_task_id")
    op.drop_column("content_tasks", "title")

    op.drop_index("ix_content_items_published_by_id", table_name="content_items")
    op.drop_index("ix_content_items_primary_asset_id", table_name="content_items")
    op.drop_index("ix_content_items_editorial_owner_id", table_name="content_items")

    op.drop_column("content_items", "last_change_summary")
    op.drop_column("content_items", "review_cycle")
    op.drop_column("content_items", "published_by_name")
    op.drop_column("content_items", "published_by_id")
    op.drop_column("content_items", "published_at")
    op.drop_column("content_items", "primary_asset_id")
    op.drop_column("content_items", "editorial_owner_name")
    op.drop_column("content_items", "editorial_owner_id")
    op.drop_column("content_items", "editorial_status")

    bind = op.get_bind()
    editorialstatus.drop(bind, checkfirst=True)
