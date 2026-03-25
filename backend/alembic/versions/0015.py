"""task assignment priority and saved views

Revision ID: 0015_task_assignment_views
Revises: 0014
Create Date: 2026-03-25

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


taskpriority = sa.Enum("low", "medium", "high", "critical", name="taskpriority")


def upgrade() -> None:
    taskpriority.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "content_tasks",
        sa.Column("priority", taskpriority, nullable=False, server_default="medium"),
    )
    op.add_column(
        "content_tasks",
        sa.Column("assignee_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "content_tasks",
        sa.Column(
            "assignee_role",
            postgresql.ENUM("admin", "editor", "viewer", name="userrole", create_type=False),
            nullable=True,
        ),
    )
    op.add_column("content_tasks", sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("content_tasks", sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_content_tasks_assignee_user_id", "content_tasks", ["assignee_user_id"], unique=False)

    op.create_table(
        "content_task_views",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("is_shared", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("filters", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("timezone('utc', now())")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("timezone('utc', now())")),
    )
    op.create_index("ix_content_task_views_user_id", "content_task_views", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_content_task_views_user_id", table_name="content_task_views")
    op.drop_table("content_task_views")

    op.drop_index("ix_content_tasks_assignee_user_id", table_name="content_tasks")
    op.drop_column("content_tasks", "escalated_at")
    op.drop_column("content_tasks", "notified_at")
    op.drop_column("content_tasks", "assignee_role")
    op.drop_column("content_tasks", "assignee_user_id")
    op.drop_column("content_tasks", "priority")

    taskpriority.drop(op.get_bind(), checkfirst=True)
