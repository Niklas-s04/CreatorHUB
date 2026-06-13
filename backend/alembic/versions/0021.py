"""content planning hub foundations

Revision ID: 0021
Revises: 0020
Create Date: 2026-04-15

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


checklistphase = sa.Enum(
    "pre_production",
    "production",
    "post_production",
    "upload",
    name="checklistphase",
)


def upgrade() -> None:
    bind = op.get_bind()
    checklistphase.create(bind, checkfirst=True)

    op.add_column(
        "content_items",
        sa.Column("platform_meta_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )
    op.add_column(
        "content_items",
        sa.Column("applied_template_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "content_items",
        sa.Column("readiness_score", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_content_items_applied_template_snapshot_id",
        "content_items",
        ["applied_template_snapshot_id"],
        unique=False,
    )

    op.add_column(
        "content_tasks",
        sa.Column("required_for_publish", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "content_tasks",
        sa.Column("can_block_publish", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "content_tasks",
        sa.Column("checklist_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_content_tasks_checklist_snapshot_id",
        "content_tasks",
        ["checklist_snapshot_id"],
        unique=False,
    )

    op.create_table(
        "content_platform_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "platform",
            postgresql.ENUM(
                "youtube",
                "shorts",
                "instagram",
                "tiktok",
                "x",
                "linkedin",
                name="contentplatform",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("schema_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
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
    )
    op.create_index(
        "ix_content_platform_profiles_platform",
        "content_platform_profiles",
        ["platform"],
        unique=False,
    )
    op.create_index(
        "ix_content_platform_profiles_owner_user_id",
        "content_platform_profiles",
        ["owner_user_id"],
        unique=False,
    )

    op.create_table(
        "content_checklist_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "applies_to_platform",
            postgresql.ENUM(
                "youtube",
                "shorts",
                "instagram",
                "tiktok",
                "x",
                "linkedin",
                name="contentplatform",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column(
            "applies_to_type",
            postgresql.ENUM(
                "review",
                "short",
                "post",
                "story",
                name="contenttype",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("is_shared", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
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
    )
    op.create_index(
        "ix_content_checklist_templates_applies_to_platform",
        "content_checklist_templates",
        ["applies_to_platform"],
        unique=False,
    )
    op.create_index(
        "ix_content_checklist_templates_applies_to_type",
        "content_checklist_templates",
        ["applies_to_type"],
        unique=False,
    )
    op.create_index(
        "ix_content_checklist_templates_owner_user_id",
        "content_checklist_templates",
        ["owner_user_id"],
        unique=False,
    )

    op.create_table(
        "content_checklist_template_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column(
            "phase",
            postgresql.ENUM(
                "pre_production",
                "production",
                "post_production",
                "upload",
                name="checklistphase",
                create_type=False,
            ),
            nullable=False,
            server_default="production",
        ),
        sa.Column(
            "priority_default",
            postgresql.ENUM(
                "low",
                "medium",
                "high",
                "critical",
                name="taskpriority",
                create_type=False,
            ),
            nullable=False,
            server_default="medium",
        ),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("due_offset_days", sa.Integer(), nullable=True),
        sa.Column("can_block_publish", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
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
        sa.ForeignKeyConstraint(["template_id"], ["content_checklist_templates.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_content_checklist_template_items_template_id",
        "content_checklist_template_items",
        ["template_id"],
        unique=False,
    )

    op.create_table(
        "content_checklist_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("snapshot_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.ForeignKeyConstraint(["template_id"], ["content_checklist_templates.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_content_checklist_snapshots_content_item_id",
        "content_checklist_snapshots",
        ["content_item_id"],
        unique=False,
    )
    op.create_index(
        "ix_content_checklist_snapshots_template_id",
        "content_checklist_snapshots",
        ["template_id"],
        unique=False,
    )
    op.create_index(
        "ix_content_checklist_snapshots_created_by_user_id",
        "content_checklist_snapshots",
        ["created_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_content_checklist_snapshots_created_by_user_id", table_name="content_checklist_snapshots")
    op.drop_index("ix_content_checklist_snapshots_template_id", table_name="content_checklist_snapshots")
    op.drop_index("ix_content_checklist_snapshots_content_item_id", table_name="content_checklist_snapshots")
    op.drop_table("content_checklist_snapshots")

    op.drop_index("ix_content_checklist_template_items_template_id", table_name="content_checklist_template_items")
    op.drop_table("content_checklist_template_items")

    op.drop_index("ix_content_checklist_templates_owner_user_id", table_name="content_checklist_templates")
    op.drop_index("ix_content_checklist_templates_applies_to_type", table_name="content_checklist_templates")
    op.drop_index("ix_content_checklist_templates_applies_to_platform", table_name="content_checklist_templates")
    op.drop_table("content_checklist_templates")

    op.drop_index("ix_content_platform_profiles_owner_user_id", table_name="content_platform_profiles")
    op.drop_index("ix_content_platform_profiles_platform", table_name="content_platform_profiles")
    op.drop_table("content_platform_profiles")

    op.drop_index("ix_content_tasks_checklist_snapshot_id", table_name="content_tasks")
    op.drop_column("content_tasks", "checklist_snapshot_id")
    op.drop_column("content_tasks", "can_block_publish")
    op.drop_column("content_tasks", "required_for_publish")

    op.drop_index("ix_content_items_applied_template_snapshot_id", table_name="content_items")
    op.drop_column("content_items", "readiness_score")
    op.drop_column("content_items", "applied_template_snapshot_id")
    op.drop_column("content_items", "platform_meta_json")

    bind = op.get_bind()
    checklistphase.drop(bind, checkfirst=True)
