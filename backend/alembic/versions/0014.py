"""deal checklist link and email approval metadata

Revision ID: 0014_deal_email_flow_links
Revises: 0013
Create Date: 2026-03-25

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("deal_drafts", sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("deal_drafts", sa.Column("checklist", sa.JSON(), nullable=True))
    op.create_index("ix_deal_drafts_product_id", "deal_drafts", ["product_id"], unique=False)
    op.create_foreign_key(
        "fk_deal_drafts_product_id_products",
        "deal_drafts",
        "products",
        ["product_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("email_drafts", sa.Column("risk_score", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("email_drafts", sa.Column("risk_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("email_drafts", sa.Column("approval_reason", sa.Text(), nullable=True))
    op.add_column("email_drafts", sa.Column("approved_by_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("email_drafts", sa.Column("approved_by_name", sa.String(length=128), nullable=True))
    op.add_column("email_drafts", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_email_drafts_approved_by_id", "email_drafts", ["approved_by_id"], unique=False)

    op.execute(
        """
        UPDATE email_drafts
        SET risk_score = CASE
            WHEN risk_flags IS NULL OR risk_flags = '' OR risk_flags = '[]' THEN 0
            ELSE 1
        END,
        risk_checked_at = COALESCE(updated_at, created_at, timezone('utc', now()))
        """
    )


def downgrade() -> None:
    op.drop_index("ix_email_drafts_approved_by_id", table_name="email_drafts")
    op.drop_column("email_drafts", "approved_at")
    op.drop_column("email_drafts", "approved_by_name")
    op.drop_column("email_drafts", "approved_by_id")
    op.drop_column("email_drafts", "approval_reason")
    op.drop_column("email_drafts", "risk_checked_at")
    op.drop_column("email_drafts", "risk_score")

    op.drop_constraint("fk_deal_drafts_product_id_products", "deal_drafts", type_="foreignkey")
    op.drop_index("ix_deal_drafts_product_id", table_name="deal_drafts")
    op.drop_column("deal_drafts", "checklist")
    op.drop_column("deal_drafts", "product_id")
