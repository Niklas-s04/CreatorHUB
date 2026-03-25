"""unified workflow status and review metadata

Revision ID: 0013_unified_workflow_status
Revises: 0012_audit_logs
Create Date: 2026-03-25

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


workflowstatus = sa.Enum(
    "draft",
    "in_review",
    "approved",
    "rejected",
    "published",
    "archived",
    name="workflowstatus",
)


def _add_workflow_columns(table_name: str) -> None:
    op.add_column(
        table_name,
        sa.Column("workflow_status", workflowstatus, nullable=False, server_default="draft"),
    )
    op.add_column(table_name, sa.Column("review_reason", sa.Text(), nullable=True))
    op.add_column(table_name, sa.Column("reviewed_by_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column(table_name, sa.Column("reviewed_by_name", sa.String(length=128), nullable=True))
    op.add_column(table_name, sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        f"ix_{table_name}_reviewed_by_id",
        table_name,
        ["reviewed_by_id"],
        unique=False,
    )


def _drop_workflow_columns(table_name: str) -> None:
    op.drop_index(f"ix_{table_name}_reviewed_by_id", table_name=table_name)
    op.drop_column(table_name, "reviewed_at")
    op.drop_column(table_name, "reviewed_by_name")
    op.drop_column(table_name, "reviewed_by_id")
    op.drop_column(table_name, "review_reason")
    op.drop_column(table_name, "workflow_status")


def upgrade() -> None:
    workflowstatus.create(op.get_bind(), checkfirst=True)

    for table in ("products", "content_items", "deal_drafts", "knowledge_docs", "assets"):
        _add_workflow_columns(table)

    op.execute(
        """
        UPDATE content_items
        SET workflow_status = CASE
            WHEN status = 'published' THEN 'published'::workflowstatus
            WHEN status IN ('scheduled', 'edited', 'recorded') THEN 'in_review'::workflowstatus
            WHEN status = 'idea' THEN 'draft'::workflowstatus
            ELSE 'draft'::workflowstatus
        END
        """
    )
    op.execute(
        """
        UPDATE assets
        SET workflow_status = CASE
            WHEN review_state = 'approved' THEN 'approved'::workflowstatus
            WHEN review_state = 'rejected' THEN 'rejected'::workflowstatus
            ELSE 'in_review'::workflowstatus
        END
        """
    )
    op.execute(
        """
        UPDATE products
        SET workflow_status = CASE
            WHEN status = 'archived' THEN 'archived'::workflowstatus
            ELSE 'draft'::workflowstatus
        END
        """
    )


def downgrade() -> None:
    for table in ("assets", "knowledge_docs", "deal_drafts", "content_items", "products"):
        _drop_workflow_columns(table)

    workflowstatus.drop(op.get_bind(), checkfirst=True)
