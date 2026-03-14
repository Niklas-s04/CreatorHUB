"""create deal drafts table

Revision ID: 0005_deal_drafts
Revises: 0004_asset_perceptual_hash
Create Date: 2026-03-04

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Revisionsdaten für Alembic.
revision = "0005_deal_drafts"
down_revision = "0004_asset_perceptual_hash"
branch_labels = None
depends_on = None


dealdraftstatus_enum = postgresql.ENUM(
    "intake", "review", "negotiating", "won", "lost", name="dealdraftstatus"
)
dealdraftstatus_col = postgresql.ENUM(
    "intake", "review", "negotiating", "won", "lost", name="dealdraftstatus", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    dealdraftstatus_enum.create(bind, checkfirst=True)

    op.create_table(
        "deal_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "thread_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("email_threads.id", ondelete="SET NULL"),
            nullable=True,
            unique=True,
        ),
        sa.Column("brand_name", sa.String(length=128), nullable=True),
        sa.Column("contact_name", sa.String(length=128), nullable=True),
        sa.Column("contact_email", sa.String(length=128), nullable=True),
        sa.Column("budget", sa.String(length=128), nullable=True),
        sa.Column("deliverables", sa.Text(), nullable=True),
        sa.Column("usage_rights", sa.Text(), nullable=True),
        sa.Column("deadlines", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "status",
            dealdraftstatus_col,
            nullable=False,
            server_default=sa.text("'intake'::dealdraftstatus"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("deal_drafts")
    bind = op.get_bind()
    dealdraftstatus_enum.drop(bind, checkfirst=True)
